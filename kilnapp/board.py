import time
import logging

from settings import config
from .plugins import plugin_manager

log = logging.getLogger(__name__)

class Output(object):
    '''This represents a GPIO output that controls a solid
    state relay to turn the kiln elements on and off.
    inputs
    '''
    def __init__(self):
        self.active = False
        (pin, self.off)  = config.get_gpio('plugins.heater.relay.main.gpio',
                             "No GPIO specified for turning on the heat relay")
        self.on = not self.off

        import digitalio
        self.heater = digitalio.DigitalInOut(pin)
        self.heater.direction = digitalio.Direction.OUTPUT

    def heat(self,sleepfor):
        self.heater.value = self.on
        time.sleep(sleepfor)

    def cool(self,sleepfor):
        '''no active cooling, so sleep'''
        self.heater.value = self.off
        time.sleep(sleepfor)

# wrapper for blinka board
class Board(object):
    '''This represents a blinka board where this code
    runs.
    '''
    def __init__(self):
        log.info(self.name)

    @staticmethod
    def get():
        if config.get('general.simulate', False):
            return SimulatedBoard()
        else:
            return RealBoard()

class RealBoard(Board):
    '''Each board has a thermocouple board attached to it.
    Any blinka board that supports SPI can be used. The
    board is automatically detected by blinka.
    '''
    def __init__(self):
        self.name = None
        self.load_libs()
        self.output = Output()
        Board.__init__(self)

    def load_libs(self):
        import board
        self.name = board.board_id

class SimulatedBoard(Board):
    '''Simulated board used during simulations.
    '''
    def __init__(self):
        self.name = "simulated"
        Board.__init__(self)

