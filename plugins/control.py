import logging
import time

from settings import config, InvalidSettingError

log = logging.getLogger("plugins." + __name__)

from plugins import hookimpl, KilnPlugin, plugin_manager

def get_oven_elements():
    return config.get('oven.element').keys()

time_step = config.get_time_in_unit('oven.duty_cycle', 's')

base = 'plugins.control.'
seek_start = config.get(base + 'seek_start', False)
control_window = config.get_temp(base + 'pid_control_window',
                                      'Need to specify PID control window in settings')[0]
must_catchup = config.get(base + 'must_catch_up', True)
throttle_below_temp = config.get_temp(base + 'throttle_below_temp')[0]
throttle_percent = config.get_percent(base + 'throttle_percent')

class PID(object):
    def __init__(self, kp: float, ki: float, kd: float):
        self.lastNow = datetime.datetime.now()
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.time = 0
        self.timeDelta = 0
        self.setpoint = 0
        self.ispoint = 0
        self.lastErr = 0
        self.errDelta = 0
        self.pterm = 0
        self.iterm = 0
        self.dterm = 0
        self.rawOutput = 0
        self.output = 0

        try:
            self.throttle_below_temp = config.get_temp('oven.throttle_below_temp')[0]
            self.throttle_percent = config.get_percent('oven.throttle_percent')
            self.throttle = True
        except NoSettingError:
            self.throttle = False

        self.control_window = config.get_temp('oven.pid_control_window')[0]

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

        self.errDelta = 0
        if error < -self.control_window:
            log_throttling.by_time(log, interval=log_throttle).warn(
                    "Kiln outside pid control window, max cooling")
            output = 0
            # it is possible to set self.iterm=0 here and also below
            # but I dont think its needed
        elif error > self.control_window:
            log_throttling.by_time(log, interval=log_throttle).warn(
                    "Kiln outside pid control window, max heating")
            if self.throttle and setpoint <= self.throttle_below_temp:
                output = self.throttle_percent
                log_throttling.by_time(log, interval=log_throttle).warn(
                        "max heating throttled at {}% below {} degrees to prevent overshoot"
                        .format(self.throttle_percent, self.throttle_below_temp))
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

# Thermocouple:
# - Current temp
# - Confidence
# - Runtime? (Timestamp)

# hook.get_time -> Thermocouple -> hook.temperature_reading
# hook.temperature_reading -> Controller -> hook.heat
# hook.heat -> Heater -> hook.add_cost
# hook.start_firing -> Controller
# hook.abort_firing -> Controller

# Controller:
# - Profile, State
# - Start_time, Runtime, TotalTime
# - Target temp, Catchup
# - Pidstats (deprecated, used currently instead of heat)

# Heater: (relay plugin)
# - Heat, and Heat_rate
# - kwh_rate, currency_type, cost

class Controller(KilnPlugin):
    '''This represents a GPIO output that controls a solid
    state relay to turn the kiln elements on and off.
    '''
    def __init__(self, name):
        super().__init__(__name__)
        self.active = False
        self.pidname = name
        base = 'plugins.control.pid.' + name

        kp = config.get(base + '.parameters.kp', 10)
        ki = config.get(base + '.parameters.ki', 80)
        kd = config.get(base + '.parameters.kd', 220.83497910261562)
        self.thermocouples = config.get(base + '.thermocouple', None,
                '{} missing thermocouple definition in controler'.format(name))
        self.relays = config.get(base + '.relay', None,
                '{} missing relay definition in controler'.format(name))

    @hookimpl
    def temperature_reading(self, info):
        for name in self.thermocouples:
            try:
                info['thermocouple'][name]
            except KeyError:
                pass # FIXME Missing simulated heater support

    def run(self):
        log.info(self.message("Starting Controller: {}".format(self.name)))
        self.active = True

    @hookimpl
    def start_plugin(self):
        self.start()

# Multiple relay/element support
class Controllers(object):
    def __init__(self):
        controls = config.get('plugins.control.pid', None, 'No PID controllers specified')
        self.controllers = {}

        for name in controls.keys():
            ctrl = Controller(name)
            plugin_manager.register(ctrl)
            self.controllers[name] = ctrl


plugin_manager.register(Controllers())
