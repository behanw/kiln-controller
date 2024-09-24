import threading
import time
import logging
import config
import digitalio

log = logging.getLogger(__name__)

import plugins

class Caution(threading.Thread):
    '''This represents a GPIO output that controls a
    status LED which beats like a heart.
        config.caution_gpio
        config.caution_invert
        config.caution_quiet
    '''
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True

        # Read Caution LED GPIO
        try:
            self.led = digitalio.DigitalInOut(config.caution_gpio)
            self.led.direction = digitalio.Direction.OUTPUT 
            self.simulated = False
        except:
            self.simulated = True

        # Read Caution LED active-high or active-low
        try:
            self.off = config.caution_led_invert
        except:
            self.off = False
        self.on = not self.off
        self.turnled(self.off)

        # Quiet Caution during simulation for debugging
        try:
            self.quiet = config.caution_quiet
        except:
            self.quiet = False
        if self.simulated and self.quiet:
            log.warn("Caution disabled during simulation")

        self.period = 1
        self.state = {}

        self.start()

    def turnled(self, state, delay=0, msg=None):
        if not self.simulated:
            self.led.value = state
        elif msg != None and self.quiet == False:
            log.info(msg)

    # This method will be executed when the thread starts
    def run(self):
        log.info("Starting CautionE-stop monitor")

        while True:
            if self.state != {}:
                self.turnled(self.on, "Caution")
            else:
                self.turnled(self.off)
            time.sleep(self.period)

    @plugins.hookimpl
    def failure(self, reason):
        self.state = reason
        # Reset countdown
        if hasattr(reason, 'msg'):
            log.warn(reason['msg'])
