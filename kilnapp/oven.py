import threading
import time
import datetime
import logging
import log_throttling
import config

from .plugins import hookimpl, plugin_manager
from .ovenState import OvenState
from .firing_profile import Firing_Profile
from .board import Board

import pluggy

log = logging.getLogger(__name__)

class DupFilter(object):
    def __init__(self):
        self.msgs = set()

    def filter(self, record):
        rv = record.msg not in self.msgs
        self.msgs.add(record.msg)
        return rv

class Duplogger():
    def __init__(self):
        self.log = logging.getLogger("{}.dupfree".format(__name__))
        dup_filter = DupFilter()
        self.log.addFilter(dup_filter)
    def logref(self):
        return self.log

duplog = Duplogger().logref()

class FiringProfileEnded(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class Oven(threading.Thread):
    '''parent oven class. this has all the common code
       for either a real or simulated oven'''
    def __init__(self):
        threading.Thread.__init__(self)
        self.board = Board.get()
        self.daemon = True
        self.time_step = config.sensor_time_wait
        self.reset()

    def reset(self, firing_profile: Firing_Profile=None, runtime: int=0) -> None:
        self.state = OvenState(firing_profile, runtime)

    def pidstats(self):
        return self.state.pid.get()

    @staticmethod
    def getOven():
        if config.simulate == True:
            log.warn("this is a simulation")
            return SimulatedOven()
        else:
            log.warn("this is a real kiln")
            return RealOven()

    def thermocouple_temperature(self) -> float:
        #temp = self.board.thermocouple.temperature()
        #self.state.set_temperature(temp)
        temp = self.state.temperature

        '''reset if the temperature is way TOO HOT, or other critical errors detected'''
        if (temp >= config.emergency_shutoff_temp):
            log.critical("Emergency!!! temperature too high")
            self.hook.failure(info={
                "reason": "Emergency!!! temperature too high",
                "pattern": "fail2"
                })
            if config.ignore_temp_too_high == False:
                self.abort_run()

        elif self.board.thermocouple.status.over_error_limit():
            log.critical("Emergency!!! too many errors in a short period")
            self.hook.failure(info={
                "reason": "Emergency!!! too many errors in a short period",
                "pattern": "fail3"
                })
            if config.ignore_tc_too_many_errors == False:
                self.abort_run()

        return temp

    def run_profile(self, firing_profile, startat=0):
        log.debug('run_profile run on thread' + threading.current_thread().name)

        runtime = startat * 60
        if config.seek_start and self.state.idling() and startat == 0:
            temp = self.thermocouple_temperature()
            runtime += firing_profile.get_start_from_temperature(temp)
        self.reset(firing_profile, runtime)
        self.state.set_start_time(datetime.datetime.now() - datetime.timedelta(seconds=startat * 60))

        self.state.resume()
        log.info("Starting firing profile {} at {} minutes".format(
            self.state.profile.name, round(startat, 2)))

        time.sleep(1)
        self.ovenwatcher.record(self.state.profile) ### FIXME?

    def end_run(self):
        self.reset()
        self.remove_automatic_restart_state()

    def abort_run(self):
        name = self.state.profile.name
        self.end_run()
        raise FiringProfileEnded("Finished firing profile {}".format(name))

    def reset_if_finished(self):
        if self.state.finished():
            log.info("Firing Profile ended: shutting down (total cost = {})".format(
                self.state.get_cost()))
            self.abort_run()

    def update_start_time(self, scale=1):
        self.state.set_start_time(datetime.datetime.now() \
                - datetime.timedelta(milliseconds = self.state.runtime * 1000 / scale))

    def update_runtime(self, scale=1):
        runtime_delta = datetime.datetime.now() - self.state.start_time
        if runtime_delta.total_seconds() < 0:
            runtime_delta = datetime.timedelta(0)
        #log.info("start_time: {}  runtime_delta: {}".format(self.state.start_time, runtime_delta.total_seconds()))
        self.state.set_runtime(runtime_delta.total_seconds() * scale)
        self.state.update_target_temp()

    def kiln_must_catch_up(self):
        '''shift the whole schedule forward in time by one time_step
        to wait for the kiln to catch up'''
        if config.kiln_must_catch_up == True:
            temp = self.thermocouple_temperature()
            # kiln too cold, wait for it to heat up
            if self.state.target - temp > config.pid_control_window:
                log_throttling.by_time(log, interval=config.log_throttle).warn(
                        "kiln must catch up, too cold, shifting schedule")
                self.update_start_time()
                self.state.catchup()
            # kiln too hot, wait for it to cool down
            elif temp - self.state.target > config.pid_control_window:
                log_throttling.by_time(log, interval=config.log_throttle).warn(
                        "kiln must catch up, too hot, shifting schedule")
                self.update_start_time()
                self.state.catchup()
            else:
                self.state.caughtup()

    def remove_automatic_restart_state(self):
        self.state.delete()

    def save_automatic_restart_state(self):
        # only save state if the feature is enabled
        if config.automatic_restarts:
            return self.state.store()
        return False

    def automatic_restart(self) -> bool:
        # only automatic restart if the feature is enabled
        if not config.automatic_restarts:
            return False
        if self.state.too_old():
            duplog.warn("automatic restart not possible. state file does not exist or is too old.")
            return False

        try:
            laststate = self.state.load()
        except EOFError:
            duplog.warn("Saved state corrupt: restart not possible.")
            return False
        except FileNotFoundError:
            duplog.warn("Saved state missing: restart not possible.")
            return False

        if not laststate.running():
            duplog.warn("automatic restart not possible. state = {}".format(
                self.state.getstate()))
            return False

        self.state = laststate
        # FIXME Should probably recalculate runtime and start_time?

        self.state.resume()
        startat = laststate.runtime / 60
        log.info("Automatically restarting firing profile {} at {} minutes".format(
            self.state.profile.name, round(startat, 2)))
        time.sleep(1)
        self.ovenwatcher.record(self.state.profile) ### FIXME?
        return True

    def set_ovenwatcher(self,watcher):
        log.debug("ovenwatcher set in oven class")
        self.ovenwatcher = watcher

    def calculate_heat_on_off(self, now: datetime.datetime) -> tuple:
        return self.state.pid_compute(self.thermocouple_temperature(), now)

    def run(self):
        self.automatic_restart()
        while True:
            log.debug('Oven running on ' + threading.current_thread().name)
            plugin_manager.hook.activity()
            if self.state.idling():
                time.sleep(1)
            else:
                try:
                    if self.state.paused():
                        self.update_start_time()
                    elif self.state.running():
                        self.state.update_cost()
                        self.save_automatic_restart_state()
                        self.kiln_must_catch_up()
                    else:
                        log.info("*** State: {}".format(self.state.getstate()))
                        continue
                    self.update_runtime()
                    self.heat_then_cool()
                    self.reset_if_finished()
                except FiringProfileEnded as e:
                    log.info(e)


class RealOven(Oven):

    def __init__(self):
        # call parent init
        Oven.__init__(self)

        # start thread
        self.start()

    def reset(self, firing_profile: Firing_Profile=None, runtime: int=0) -> None:
        super().reset(firing_profile, runtime)
        self.board.output.cool(0)

    def heat_then_cool(self):
        (heat_on_time, heat_off_time, pid) = self.calculate_heat_on_off(datetime.datetime.now())

        if heat_on_time:
            self.board.output.heat(heat_on_time)
        if heat_off_time:
            self.board.output.cool(heat_off_time)


class SimulatedOven(Oven):

    def __init__(self):
        self.t_env = config.sim_t_env
        self.c_heat = config.sim_c_heat
        self.c_oven = config.sim_c_oven
        self.p_heat = config.sim_p_heat
        self.R_o_nocool = config.sim_R_o_nocool
        self.R_ho_noair = config.sim_R_ho_noair
        self.R_ho = self.R_ho_noair
        self.speedup_factor = config.sim_speedup_factor

        # set temps to the temp of the surrounding environment
        self.t = config.sim_t_env  # deg C or F temp of oven
        self.t_h = self.t_env #deg C temp of heating element

        super().__init__()

        self.update_start_time()

        # start thread
        self.start()
        log.info("SimulatedOven started")

    # runtime is in sped up time, start_time is actual time of day
    def update_start_time(self):
        return super().update_start_time(self.speedup_factor)

    def update_runtime(self):
        super().update_runtime(self.speedup_factor)

    def heating_energy(self, pid):
        """Using pid here simulates the element being on for
        only part of the time_step"""
        self.Q_h = self.p_heat * self.time_step * pid

    def temp_changes(self):
        #temperature change of heat element by heating
        self.t_h += self.Q_h / self.c_heat

        #energy flux heat_el -> oven
        self.p_ho = (self.t_h - self.t) / self.R_ho

        #temperature change of oven and heating element
        self.t += self.p_ho * self.time_step / self.c_oven
        self.t_h -= self.p_ho * self.time_step / self.c_heat

        #temperature change of oven by cooling to environment
        self.p_env = (self.t - self.t_env) / self.R_o_nocool
        self.t -= self.p_env * self.time_step / self.c_oven
        self.board.thermocouple.simulated_temperature = self.t

    def heat_then_cool(self):
        now_simulator = self.state.start_time + datetime.timedelta(milliseconds = self.state.runtime * 1000)
        (heat_on, heat_off, pid) = self.calculate_heat_on_off(now_simulator)

        self.heating_energy(pid)
        self.temp_changes()
        log.info("simulation: -> {}W heater: {.0f} -> {}W oven: {:.0f} -> {}W env".format(
                 int(self.p_heat * pid), self.t_h, round(self.p_ho), self.t, round(self.p_env)))

        # we don't actually spend time heating & cooling during
        # a simulation, so sleep.
        time.sleep(self.time_step / self.speedup_factor)
