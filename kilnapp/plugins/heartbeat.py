import logging
import time

from settings import config

log = logging.getLogger("plugins." + __name__)

Pattern = {
    "off": [(0, 1)],
    "fail": [(1, .2), (0, .2)],
    "heartbeat": [(1, .1), (0, .1), (1, .1), (0, .7)],
    "sos": [ (1, .1), (0, .2), (1, .1), (0, .2), (1, .1), (0, .4),
        (1, .5), (0, .2), (1, .5), (0, .2), (1, .5), (0, .4),
        (1, .1), (0, .2), (1, .1), (0, .2), (1, .1), (0, 1) ]
}

from kilnapp.plugins import hookimpl, KilnPlugin

class Heartbeat(KilnPlugin):
    '''This represents a GPIO output that controls a
    status LED which beats like a heart.
    '''
    def __init__(self):
        super().__init__(__name__)

        # Read Heartbeat GPIO
        try:
            import digitalio
            pin = config.get_pin('plugins.heartbeat.led.gpio.pin')
            self.led = digitalio.DigitalInOut(pin)
            self.led.direction = digitalio.Direction.OUTPUT
            self.simulated = False
        except:
            self.simulated = True

        # Read Heartbeat active-high or active-low
        self.off = config.get('plugins.heartbeat.led.gpio.inverted', False)
        self.on = not self.off

        # Read Heartbeat period
        self.period = config.get_time_in_unit('plugins.heartbeat.period', 's')
        self.resetCountdown()

        self.verbose = config.get_log_subsystem('heartbeat')

    def record_heartbeat(self, status: str) -> None:
        self.hook.record_meta(info={"heartbeat": status})

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
                self.record_heartbeat("Okay")
            else:
                self.playpattern(Pattern["sos"], "Fail")
                self.record_heartbeat("SOS")

    def resetCountdown(self):
        self.countdown = self.period

heartbeatObj = None

@hookimpl
def start_plugin():
    global heartbeatObj
    heartbeatObj = Heartbeat()
    heartbeatObj.start()

@hookimpl
def activity():
    # Reset countdown
    if heartbeatObj:
        heartbeatObj.resetCountdown()
