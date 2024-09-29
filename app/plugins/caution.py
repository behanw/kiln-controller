import logging
import config
import time
import digitalio

log = logging.getLogger(__name__)

import app.plugins
from app.plugins.kilnplugin import KilnPlugin

Pattern = {
    "off": [(0, 1)],
    "fail": [(1, .25), (0, .25)]
}

class Caution(KilnPlugin):
    '''This represents a GPIO output that controls a
    status LED which indicates caution or a failure.
        config.caution_gpio
        config.caution_invert
        config.caution_verbose
    '''
    def __init__(self, hook=None):
        super().__init__(hook)
        self.fail = None
        self.pattern = Pattern["off"]

        # Read Caution LED GPIO
        try:
            self.led = digitalio.DigitalInOut(config.caution_gpio)
            self.led.direction = digitalio.Direction.OUTPUT 
            self.simulated = False
        except:
            self.simulated = True

        # Read Caution LED active-high or active-low
        try:
            self.off = config.caution_invert
        except:
            self.off = False
        self.on = not self.off
        self.turnled(self.off)

        # Quiet Caution during simulation for debugging
        try:
            self.verbose = config.caution_verbose
        except:
            self.verbose = False
        if self.simulated and self.verbose:
            log.warn("Caution disabled during simulation")

        self.clearfail()

    def setfail(self, info):
        self.fail = info["reason"]
        self.pattern = Pattern[info["pattern"] or "fail"]

    def clearfail(self):
        self.fail = False
        self.pattern = Pattern["off"]

    def turnled(self, state, delay=1):
        self.led.value = state
        time.sleep(delay)

    def play(self, pattern):
        for (state, delay) in pattern:
            if state:
                self.led.value = self.on
            else:
                self.led.value = self.off
            time.sleep(delay)

    # This method will be executed when the thread starts
    def run(self):
        log.info(self.message("Starting Caution light"))

        while True:
            if self.fail:
                if self.verbose:
                    log.info(self.fail)
            if not self.simulated:
                self.play(self.pattern)

cautionObj = None

def startPlugin(hook=None):
    global cautionObj
    cautionObj = Caution(hook)
    cautionObj.start()
    return cautionObj

@app.plugins.hookimpl
def failure(info):
    if cautionObj != None:
        cautionObj.setfail(info)

@app.plugins.hookimpl
def clear_failure(info):
    if cautionObj != None:
        cautionObj.clearfail()
