import logging
import time

from settings import config

log = logging.getLogger("plugins." + __name__)

from kilnapp.plugins import hookimpl, KilnPlugin

# Heat on/off
# Cost calculation

class Heater(object):
    '''This represents a GPIO output that controls a solid
    state relay to turn the kiln elements on and off.
    inputs
    '''
    def __init__(self):
        self.active = False
        try:
            import digitalio
            pin = config.get_pin('plugins.heater.ssr.main.gpio.pin')
            self.heater = digitalio.DigitalInOut(pin)
            self.heater.direction = digitalio.Direction.OUTPUT
            self.simulated = False
        except:
            self.simulated = True

        # Read Heater active-high or active-low
        self.off = config.get('plugins.heater.ssr.main.gpio.inverted', False)
        self.on = not self.off

        self.verbose = config.get_log_subsystem('heater')

    def heat(self,sleepfor):
        self.heater.value = self.on
        time.sleep(sleepfor)

    def cool(self,sleepfor):
        '''no active cooling, so sleep'''
        self.heater.value = self.off
        time.sleep(sleepfor)

