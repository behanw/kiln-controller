import time
import logging
import config
import digitalio

from thermocouple import Thermocouple

log = logging.getLogger(__name__)

class Output(object):
    '''This represents a GPIO output that controls a solid
    state relay to turn the kiln elements on and off.
    inputs
        config.gpio_heat
        config.gpio_heat_invert
    '''
    def __init__(self, hook):
        self.hook = hook
        self.active = False
        self.heater = digitalio.DigitalInOut(config.gpio_heat)
        self.heater.direction = digitalio.Direction.OUTPUT
        self.off = config.gpio_heat_invert
        self.on = not self.off

    def heat(self,sleepfor):
        self.heater.value = self.on
        self.hook.activity()
        time.sleep(sleepfor)

    def cool(self,sleepfor):
        '''no active cooling, so sleep'''
        self.heater.value = self.off
        self.hook.activity()
        time.sleep(sleepfor)

# wrapper for blinka board
class Board(object):
    '''This represents a blinka board where this code
    runs.
    '''
    def __init__(self, hook):
        self.hook = hook
        log.info(self.name)
        self.thermocouple = Thermocouple.get()
        self.thermocouple.start()

    @staticmethod
    def get(hook):
        if config.simulate == True:
            return SimulatedBoard(hook)
        else:
            return RealBoard(hook)

class RealBoard(Board):
    '''Each board has a thermocouple board attached to it.
    Any blinka board that supports SPI can be used. The
    board is automatically detected by blinka.
    '''
    def __init__(self, hook):
        self.name = None
        self.load_libs()
        self.output = Output(hook)
        Board.__init__(self, hook)

    def load_libs(self):
        import board
        self.name = board.board_id

class SimulatedBoard(Board):
    '''Simulated board used during simulations.
    See config.simulate
    '''
    def __init__(self, hook):
        self.name = "simulated"
        Board.__init__(self, hook)

