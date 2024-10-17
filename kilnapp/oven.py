import threading
import time
import datetime
import logging
import log_throttling

from settings import config
from plugins import hookimpl, plugin_manager
from .ovenState import OvenState
from .firing_profile import Firing_Profile
from .board import Board

log = logging.getLogger(__name__)
log_throttle = config.get('general.logging.throttle', 60)

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

        self.restart = config.get('general.restart.enable', True)
        self.time_step = config.get('oven.duty_cycle')
        self.seek_start = config.get('oven.seek_start', False)
        self.must_catchup = config.get('oven.must_catch_up', True)
        self.control_window = config.get_temp('oven.pid_control_window',
                                              'Need to specify PID control window in settings')[0]
        self.reset()

    def reset(self, firing_profile: Firing_Profile=None, runtime: int=0) -> None:
        self.state = OvenState(firing_profile, runtime)

    def pidstats(self):
        return self.state.pid.get()

    @staticmethod
    def getOven():
        if config.get('general.simulate', False):
            log.warning("this is a simulation")
            return SimulatedOven()
        else:
            log.warning("this is a real kiln")
            return RealOven()

    def thermocouple_temperature(self) -> float:
        #temp = self.board.thermocouple.temperature()
        #self.state.set_temperature(temp)
        temp = self.state.temperature
        return temp

    def run_profile(self, firing_profile, startat=0):
        log.debug('run_profile run on thread' + threading.current_thread().name)

        runtime = startat * 60
        if selt.seek_start and self.state.idling() and startat == 0:
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
        if self.must_catch_up:
            temp = self.thermocouple_temperature()
            # kiln too cold, wait for it to heat up
            if self.state.target - temp > self.control_window:
                log_throttling.by_time(log, interval=log_throttle).warn(
                        "kiln must catch up, too cold, shifting schedule")
                self.update_start_time()
                self.state.catchup()
            # kiln too hot, wait for it to cool down
            elif temp - self.state.target > self.control_window:
                log_throttling.by_time(log, interval=log_throttle).warn(
                        "kiln must catch up, too hot, shifting schedule")
                self.update_start_time()
                self.state.catchup()
            else:
                self.state.caughtup()

    def remove_automatic_restart_state(self):
        self.state.delete()

    def save_automatic_restart_state(self):
        # only save state if the feature is enabled
        if self.restart:
            return self.state.store()
        return False

    def automatic_restart(self) -> bool:
        # only automatic restart if the feature is enabled
        if not self.restart:
            return False
        if self.state.too_old():
            duplog.warning("automatic restart not possible. state file does not exist or is too old.")
            return False

        try:
            laststate = self.state.load()
        except EOFError:
            duplog.warning("Saved state corrupt: restart not possible.")
            return False
        except FileNotFoundError:
            duplog.warning("Saved state missing: restart not possible.")
            return False

        if not laststate.running():
            duplog.warning("automatic restart not possible. state = {}".format(
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
        self.t_env = config.get_temp('oven.simulation.t_env')[0]
        self.c_heat = config.get('oven.simulation.c_heat')
        self.c_oven = config.get('oven.simulation.c_oven')
        self.p_heat = config.get('oven.simulation.p_heat')
        self.R_o_nocool = config.get('oven.simulation.R_o_nocool')
        self.R_ho_noair = config.get('oven.simulation.R_ho_noair')
        self.R_ho = self.R_ho_noair
        self.speedup_factor = config.get('oven.simulation.speedup_factor', 1)

        # set temps to the temp of the surrounding environment
        self.t = self.t_env     # Temp of oven
        self.t_h = self.t_env   # Temp of heating element

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
