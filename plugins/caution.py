import logging
import time

from settings import config

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

from plugins import hookimpl, KilnPlugin

class Caution(KilnPlugin):
    '''This represents a GPIO output that controls a
    status LED which indicates caution or a failure.
    '''
    def __init__(self):
        super().__init__(__name__)
        self.fail = None
        self.pattern = Pattern["off"]
        self.record_caution("Okay")

        # Read Caution LED GPIO, active-high or active-low
        try:
            (pin, self.off) = config.get_gpio('plugins.caution.led.gpio')
            self.on = not self.off

            import digitalio
            self.led = digitalio.DigitalInOut(pin)
            self.led.direction = digitalio.Direction.OUTPUT
            self.turnled(self.off)

            self.simulated = False
        except:
            self.simulated = True

        self.verbose = config.get_log_subsystem('caution')

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
