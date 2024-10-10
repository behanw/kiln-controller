import logging
import time
import config
import digitalio

log = logging.getLogger("plugins." + __name__)

Pattern = {
    "off": [(0, 1)],
    "fail": [(1, .2), (0, .2)],
    "fail1": [(1, .2), (0, 1)],
    "fail2": [(1, .2), (0, .2), (1, .2), (0, 1)],
    "fail3": [(1, .2), (0, .2), (1, .2), (0, .2), (1, .2), (0, 1)],
    "fail4": [(1, .2), (0, .2), (1, .2), (0, .2), (1, .2), (0, .2), (1, .2), (0, 1)],
    "fail5": [(1, .2), (0, .2), (1, .2), (0, .2), (1, .2), (0, .2), (1, .2), (0, .2), (1, .2), (0, 1)],
    "fail6": [(1, .2), (0, .2), (1, .2), (0, .2), (1, .2), (0, .2), (1, .2), (0, .2), (1, .2), (0, .2), (1, .2), (0, 1)],
    "sos": [ (1, .1), (0, .2), (1, .1), (0, .2), (1, .1), (0, .4),
        (1, .5), (0, .2), (1, .5), (0, .2), (1, .5), (0, .4),
        (1, .1), (0, .2), (1, .1), (0, .2), (1, .1), (0, 1) ]
}

from kilnapp.plugins import hookimpl, KilnPlugin

class Caution(KilnPlugin):
    '''This represents a GPIO output that controls a
    status LED which indicates caution or a failure.
        config.caution_gpio
        config.caution_invert
        config.caution_verbose
    '''
    def __init__(self):
        super().__init__()
        self.fail = None
        self.pattern = Pattern["off"]
        self.record_caution("Okay")

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

    def record_caution(self, status: str) -> None:
        self.hook.record_meta(info={"caution": status})

    def setfail(self, info):
        self.fail = info["reason"]
        self.pattern = Pattern[info["pattern"] or "fail"]
        self.record_caution("Fail")

    def clearfail(self):
        self.fail = False
        self.pattern = Pattern["off"]
        self.record_caution("Okay")

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

@hookimpl
def start_plugin():
    global cautionObj
    cautionObj = Caution()
    cautionObj.start()

@hookimpl
def failure(info):
    log.info("Failure: {}".format(info["reason"]))
    if cautionObj != None:
        cautionObj.setfail(info)

@hookimpl
def clear_failure(info):
    log.info("Clear Failure: {}".format(info["reason"]))
    if cautionObj != None:
        cautionObj.clearfail()
