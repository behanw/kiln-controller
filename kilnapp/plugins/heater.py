import logging
import time

from settings import config, InvalidSettingError

log = logging.getLogger("plugins." + __name__)

from kilnapp.plugins import hookimpl, KilnPlugin

# Heat on/off
# Cost calculation

def get_element(name: str):
    # Oven
    ovenmeta = config.get('oven.element')
    # Current sensors
    # Heater relays

class Heater(object):
    '''This represents a GPIO output that controls a solid
    state relay to turn the kiln elements on and off.
    inputs
    '''
    def __init__(self, name):
        self.active = False
        self.name = name

        # Read Heater GPIO, active-high or active-low
        try:
            (pin, self.off) = config.get_gpio('plugins.heater.relay.{}.gpio'.format(name))
            self.on = not self.off

            import digitalio
            self.heater = digitalio.DigitalInOut(pin)
            self.heater.direction = digitalio.Direction.OUTPUT

            self.simulated = False
        except:
            self.simulated = True

        self.percentage = config.get_percent('plugins.relay.{}.percentage'.format(name))

        self.verbose = config.get_log_subsystem('heater')

    def heaton(self):
        self.heater.value = self.on

    def heatoff(self):
        self.heater.value = self.off

class Relays(object):
    def __init__(self):
        devices = config.get('plugins.heater.relay', None, 'No heaters specified')
        self.heaters = {}

        for name, device in devices.items():
            if device['type'] == 'element':
                self.heaters[name] = Heater(name, device)
            else:
                raise InvalidSettingError("Unsupported relay type: {}({})".format(name, device['type']))
