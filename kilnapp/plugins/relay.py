import logging
import time

from settings import config, InvalidSettingError

log = logging.getLogger("plugins." + __name__)

from kilnapp.plugins import hookimpl, KilnPlugin

# Heat on/off
# Cost calculation


def get_oven_elements():
    return config.get('oven.element').keys()

def get_current_elements():
    try:
        sensors = config.get('plugins.current.hw.sensors')
    except NoSettingError:
        return {}

    elements = {}
    for element in get_oven_elements():
        elements[element] = ""

    for name, sensor in sensors.items():
        element = sensor['element']
        if not elements.has_key(element):
            raise InvalidSettingError("Undefined element configured for {}: {}".format(name, element))
        elements[element] = name
    return elements

def get_element_watts(name: str) -> int:
    return config.get('oven.elemenet.{}.watts'.format(name), None,
        'Oven element "{}" does not specify how many watts is consumes'.format(name))

class Heater(object):
    '''This represents a GPIO output that controls a solid
    state relay to turn the kiln elements on and off.
    '''
    def __init__(self, name):
        self.active = False
        self.name = name
        base = 'plugins.relay.device.' + name

        # Read Heater GPIO, active-high or active-low
        try:
            (pin, self.off) = config.get_gpio(base + '.gpio')
            self.on = not self.off

            import digitalio
            self.relay = digitalio.DigitalInOut(pin)
            self.relay.direction = digitalio.Direction.OUTPUT

            self.simulated = False
        except:
            self.simulated = True

        self.percentage = config.get_percent(base + '.percentage')
        self.elements = config.get(base + '.element', None, 'No elements specified')
        self.thermocouple = config.get(base + '.thermocouple', None, 'No thermocouples specified')

        self.verbose = config.get_log_subsystem('relay')

    def heaton(self):
        self.relay.value = self.on

    def heatoff(self):
        self.relay.value = self.off

class Relays(object):
    def __init__(self):
        devices = config.get('plugins.relay.device', None, 'No relays specified')
        self.relays = {}

        for name, device in devices.items():
            if device['type'] == 'heater':
                self.relays[name] = Heater(name)
            else:
                raise InvalidSettingError("Unsupported relay type: {}({})".format(name, device['type']))

relaysObj = None

@hookimpl
def start_plugin():
    global relayObj
    relayObj = Relays()
