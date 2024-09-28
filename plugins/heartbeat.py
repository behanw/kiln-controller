import logging
import config
import time
import digitalio

log = logging.getLogger(__name__)

import plugins
from plugins.kilnplugin import KilnPlugin

Pattern = {
    "off": [(0, 1)],
    "heartbeat": [(1, .1), (0, .1), (1, .1), (0, .7)],
    "fail": [(1, .25), (0, .1)]
}

class Heartbeat(KilnPlugin):
    '''This represents a GPIO output that controls a
    status LED which beats like a heart.
        config.heartbeat_gpio
        config.heartbeat_invert
        config.heartbeat_period
        config.heartbeat_verbose
    '''
    def __init__(self, hook=None):
        super().__init__(hook)

        # Read Heartbeat GPIO
        try:
            self.led = digitalio.DigitalInOut(config.heartbeat_gpio)
            self.led.direction = digitalio.Direction.OUTPUT 
            self.simulated = False
        except:
            self.simulated = True

        # Read Heartbeat active-high or active-low
        try:
            self.off = config.heartbeat_invert
        except:
            self.off = False
        self.on = not self.off

        # Read Heartbeat period
        try:
            self.period = config.heartbeat_period
        except:
            self.period = 1
        self.resetCountdown()

        # Verbose Heartbeat during simulation for debugging
        try:
            self.verbose = config.heartbeat_verbose
        except:
            self.verbose = False
        if self.simulated and self.verbose:
            log.warn("Heartbeat disabled during simulation")

    def play(self, pattern):
        for (state, delay) in pattern:
            if state:
                self.led.value = self.on
            else:
                self.led.value = self.off
            time.sleep(delay)

    def playpattern(self, pattern, msg):
        if self.verbose:
            log.info(msg)
        if not self.simulated:
            self.play(pattern)

    # This method will be executed when the thread starts
    def run(self):
        log.info(self.message("Starting Heartbeat"))

        while True:
            count = self.countdown
            if count > 0:
                self.countdown = count - 1
                self.playpattern(Pattern["heartbeat"], "Heartbeat")
            else:
                self.playpattern(Pattern["fail"], "Fail")

    def resetCountdown(self):
        self.countdown = self.period

heartbeatObj = None

def startPlugin(hook=None):
    global heartbeatObj
    heartbeatObj = Heartbeat(hook)
    heartbeatObj.start()
    return heartbeatObj

@plugins.hookimpl
def activity():
    # Reset countdown
    heartbeatObj.resetCountdown()
