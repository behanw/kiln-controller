import datetime
import json
import os
import pickle
import re
import time
import logging
import log_throttling
import config

log = logging.getLogger(__name__)

class JsonSerialize(object):
    def to_json(self) -> str:
        return json.dumps(self.get())

    def __repr__(self) -> str:
        return self.to_json()


class HeatRate(JsonSerialize):
    '''HeatRate is the heating rate in degrees/hour over the last configured
    number of samples.
    '''
    def __init__(self):
        self.heat_rate = 0
        self.heat_rate_temps = []

        self.samples = 60
        try:
            self.samples = config.heat_rate_samples
        except AttributeError:
            pass

    def get(self) -> str:
        return self.heat_rate

    def set(self, runtime: int, temp: float) -> None:
        # arbitrary number of samples
        # the time this covers changes based on a few things
        self.heat_rate_temps.append((runtime, temp))

        # drop oldest temps to keep samples samples
        #log.info("*** Numtemps = {}".format(self.samples))
        self.heat_rate_temps = self.heat_rate_temps[-self.samples:]
        (time1, temp1) = (self.heat_rate_temps[0])
        (time2, temp2) = (self.heat_rate_temps[-1])
        if time2 > time1:
            self.heat_rate = ((temp2 - temp1) / (time2 - time1)) * 3600

        #log_throttling.by_time(log, interval=config.log_throttle).info(
        #        "(time, temp) ({}, {}) -> ({}, {}) {} ({}, {}) -> {}".format(
        #        runtime, temp, time1, temp1, len(self.heat_rate_temps),
        #        time2, temp2, self.heat_rate))


class PID(JsonSerialize):
    def __init__(self, kp: float=config.pid_kp, ki: float=config.pid_ki, kd: float=config.pid_kd):
        self.lastNow = datetime.datetime.now()
        self.time = 0
        self.timeDelta = 0
        self.setpoint = 0
        self.ispoint = 0
        self.lastErr = 0
        self.errDelta = 0
        self.pterm = 0
        self.iterm = 0
        self.dterm = 0
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.rawOutput = 0
        self.output = 0

        try:
            self.throttle_below_temp = config.throttle_below_temp
            self.throttle_percent = config.throttle_percent / 100
            self.throttle = True
        except AttributeError:
            self.throttle = False

    def get(self):
        return {
            'time': self.time,
            'timeDelta': self.timeDelta,
            'setpoint': self.setpoint,
            'ispoint': self.ispoint,
            'err': self.lastErr,
            'errDelta': self.errDelta,
            'p': self.pterm,
            'i': self.iterm,
            'd': self.dterm,
            'kp': self.kp,
            'ki': self.ki,
            'kd': self.kd,
            'pid': self.rawOutput,
            'out': self.output,
        }

    def compute(self, setpoint, ispoint, now):
        # FIX - this was using a really small window where the PID control
        # takes effect from -1 to 1. I changed this to various numbers and
        # settled on -50 to 50 and then divide by 50 at the end. This results in
        # a larger PID control window and much more accurate control...  instead
        # of what used to be binary on/off control.

        self.time = time.mktime(now.timetuple())
        self.timeDelta = (now - self.lastNow).total_seconds()
        self.setpoint = setpoint
        self.ispoint = ispoint
        error = setpoint - ispoint

        # This removes the need for config.stop_integral_windup
        # it turns the controller into a binary on/off switch
        # any time it's outside the window defined by
        # config.pid_control_window
        self.errDelta = 0
        if error < (-config.pid_control_window):
            log_throttling.by_time(log, interval=config.log_throttle).warn(
                    "Kiln outside pid control window, max cooling")
            output = 0
            # it is possible to set self.iterm=0 here and also below
            # but I dont think its needed
        elif error > (1 * config.pid_control_window):
            log_throttling.by_time(log, interval=config.log_throttle).warn(
                    "Kiln outside pid control window, max heating")
            if self.throttle and setpoint <= self.throttle_below_temp:
                output = self.throttle_percent
                log_throttling.by_time(log, interval=config.log_throttle).warn(
                        "max heating throttled at {}% below {} degrees to prevent overshoot"
                        .format(config.throttle_percent, self.throttle_below_temp))
            else:
                output = 1
        else:
            self.iterm += error * self.timeDelta / self.ki
            self.errDelta = (error - self.lastErr) / self.timeDelta
            self.dterm = self.kd * self.errDelta
            output = self.kp * error + self.iterm + self.kd * self.errDelta
            window_size = 100
            self.rawOutput = sorted([-window_size, output, window_size])[1]
            output = self.rawOutput / window_size

        self.lastNow = now
        self.lastErr = error
        self.pterm = self.kp * error

        # no active cooling
        self.output = max(output, 0)

        return self.output


try:
    # Global, because if a class variable, it can't be used as a default argument
    state_directory = config.automatic_restart_state_directory
except AttributeError:
    try:
        state_directory = config.topdir
    except AttributeError:
        state_directory = os.path.abspath(os.path.dirname(__file__), '..')
state_file = os.path.abspath(os.path.join(state_directory, 'state.pkl'))
log.info("Looking for restart info at {}".format(state_file))

class OvenState(JsonSerialize):
    prefix = "ext_"
    minutes_too_old = config.automatic_restart_window

    def __init__(self, firing_profile=None, runtime=0, scale=1):
        self.idle()
        # The firing profile dictates what the temperature should be at a
        # relative time.
        # Total time is length of firing profile in seconds under ideal circumstances
        if firing_profile:
            self.profile = firing_profile
            self.totaltime = self.profile.get_duration() if self.profile else 0
        else:
            self.profile = None
            self.totaltime = 0
        # Start time is the absolute time when the firing profile started
        self.set_start_time(0)
        # Run time is the absolute time where we are in the firing profile
        self.runtime = runtime
        # Speedup factor is used for simulation and testing
        self.speedup_factor = scale
        # Indicates that we're behind in the firing profile
        self.catching_up = False

        # Target temp from firing profile at runtime
        self.target = 0
        # Thermocouple temperature
        self.temperature = 0
        # Whether or not heat is enabled
        self.heat = 0
        # Current averate heat rate
        #self.heat_rate = HeatRate()
        self.heat_rate = 0
        # PID controller
        self.pid = PID()

        # Current power rate, currency and cost of firing
        self.kwh_rate = config.kwh_rate
        self.currency_type = config.currency_type
        self.cost = 0

    def set(self, key: str, value: str) -> None:
        self.__dict__[self.prefix + key] = value

    def get(self, key: str=None) -> dict:
        if key:
            return self.__dict__[prefix + key]
        else:
            #self.heat_rate.set(self.runtime, self.temperature)
            #self.rate = round(self.heat_rate.get())
            state = {
                'state': self.state,
                'profile': self.profile.name if self.profile else None,
                'pidstats': self.pid.get(),
                #'start_time': self.start_time,
                'runtime': round(self.runtime ,2),
                'totaltime': self.totaltime,
                'temperature': round(self.temperature),
                'target': round(self.target),
                'heat': self.heat,
                'heat_rate': self.heat_rate,
                'catching_up': self.catching_up,
                'kwh_rate': self.kwh_rate,
                'currency_type': self.currency_type,
                'cost': round(self.cost, 2),
            }
            for key, value in self.__dict__.items():
                if key.startswith(self.prefix):
                    state[key] = value
            log.debug(state)
            return state

    def get_time(self):
        return {
                'start_time': self.start_time,
                'runtime': self.runtime,
                'totaltime': self.totaltime,
                }

    def log_heat_state(self, heat_on_time, heat_off_time):
        try:
            log_throttling.by_time(log, interval=config.log_throttle).debug("temp={:.2f}, target={:.2f}, error={:.2f}, pid={:.2f}, p={:.2f}, i={:.2f}, d={:.2f}, heat_on={:.2f}, heat_off={:.2f}, run_time={:.2f}, total_time={:.2f}, time_left={:.2f}".format(
                self.pid.ispoint, self.pid.setpoint, self.pid.lastErr, self.pid.rawOutput,
                self.pid.pterm, self.pid.iterm, self.pid.dterm,
                heat_on_time, heat_off_time, self.runtime, self.totaltime,
                self.totaltime - self.runtime))
        except KeyError:
            pass


    def delete(self, filename: str=state_file) -> None:
        os.remove(filename)

    def store(self, filename: str=state_file) -> bool:
        with open(filename, 'wb') as outfile:
            return pickle.dump(self, outfile)

    @staticmethod
    def load(filename: str=state_file) -> bool:
        with open(filename, 'rb') as infile:
            return pickle.load(infile)

    def too_old(self) -> bool:
        try:
            now = time.time()
            status_age = os.path.getmtime(state_file)
            minutes_age = (now - status_age) / 60
            return minutes_age > self.minutes_too_old
        except FileNotFoundError:
            return True

    def getstate(self):
        return self.state

    def idle(self):
        self.state = "IDLE"
    def idling(self) -> bool:
        return self.state == "IDLE"

    def pause(self):
        self.state = "PAUSED"
    def paused(self) -> bool:
        return self.state == "PAUSED"

    def resume(self):
        self.state = "RUNNING"
    def running(self) -> bool:
        return self.state == "RUNNING"

    def finished(self) -> bool:
        return self.runtime > self.totaltime
    def set_start_time(self, value):
        self.start_time = value
    def set_runtime(self, runtime):
        #log.info("runtime: {}".format(round(runtime, 2)))
        self.runtime = runtime
        #self.heat_rate.set(runtime, self.temperature)
    def get_runtime(self):
        return self.runtime
    def get_totaltime(self):
        return self.totaltime


    def catchup(self):
        self.catching_up = True
    def caughtup(self):
        self.catching_up = False

    def heat_on(self, value):
        self.heat = value
    def heat_off(self):
        self.heat = 0
    def set_temperatures(self, meta):
        #log.info("meta: {}".format(meta))
        for key in ['temperature', 'heat_rate', 'thermocouples']:
            #log.info("key: {}".format(key))
            #log.info("key[{}]: {}".format(key, meta[key]))
            if key in meta:
                #log.info("key[{}]: {}".format(key, meta[key]))
                self.__dict__[key] = meta[key]
        #log.info("temp: {}".format(self.temperature))
    #def set_temperature(self, temp: float) -> float:
    #    #self.temperature = temp;
    #    #self.heat_rate.set(self.runtime, temp)
    #    #return temp
    #    pass
#
    def get_cost(self):
        return "{}{:.2f}".format(self.currency_type, self.cost)
    def update_cost(self):
        if self.heat:
            self.cost += (self.kwh_rate * config.kw_elements) * ((self.heat)/3600)

    def update_target_temp(self):
        self.target = self.profile.get_target_temperature(self.runtime) if self.profile else 0

    def pid_compute(self, temp: float, now: datetime.datetime) -> tuple:
        pid = self.pid.compute(self.target, temp, now)
        time_step = config.sensor_time_wait
        heat_on_time = time_step * pid
        heat_off_time = time_step * (1 - pid)

        # For the front end to display if the heat is on
        if heat_on_time > 0:
            self.heat_on(heat_on_time)
        else:
            self.heat_off()

        self.log_heat_state(heat_on_time, heat_off_time)

        return (heat_on_time, heat_off_time, pid)
