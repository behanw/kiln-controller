import threading
import time
import logging
import config
import digitalio

log = logging.getLogger(__name__)

import plugins

class Heartbeat(threading.Thread):
    '''This represents a GPIO output that controls a
    status LED which beats like a heart.
        config.heartbeat_gpio
        config.heartbeat_invert
        config.heartbeat_period
        config.heartbeat_quiet
    '''
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True

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
        self.turnled(self.off)

        # Read Heartbeat period
        try:
            self.period = config.heartbeat_period
        except:
            self.period = 1
        self.countdown = self.period

        # Quiet Heartbeat during simulation for debugging
        try:
            self.quiet = config.heartbeat_quiet
        except:
            self.quiet = False
        if self.simulated and self.quiet:
            log.warn("Heartbeat disabled during simulation")

        self.start()

    def turnled(self, state, delay=0, msg=None):
        if not self.simulated:
            self.led.value = state
        elif msg != None and self.quiet == False:
            log.info(msg)
        time.sleep(delay)

    # This method will be executed when the thread starts
    def run(self):
        tenth = self.period * 0.1
        seventieth = self.period * 0.7

        log.info("Starting Heartbeat")

        while True:
            count = self.countdown
            if count > 0:
                self.countdown = count - 1
                self.turnled(self.on,  tenth, "Heartbeat")
                self.turnled(self.off, tenth)
                self.turnled(self.on,  tenth)
                self.turnled(self.off, seventieth)
            else:
                self.turnled(self.on, self.period * 2, "Failure")

    @plugins.hookimpl
    def activity(self):
        # Reset countdown
        self.countdown = self.period
