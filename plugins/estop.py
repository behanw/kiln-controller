import threading
import time
import logging
import config
import digitalio

log = logging.getLogger(__name__)

import plugins

class Estop(threading.Thread):
    '''This represents a GPIO output that controls a
    status LED which beats like a heart.
        config.estop_button_gpio
        config.estop_button_invert
        config.estop_led_gpio
        config.estop_led_invert
        config.estop_quiet
    '''
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True

        # Read Estop Button GPIO
        try:
            self.button = digitalio.DigitalInOut(config.estop_button_gpio)
            self.button.direction = digitalio.Direction.INPUT 
            self.simulated = False
        except:
            self.simulated = True

        # Read Estop Button active-high or active-low
        try:
            self.button_off = config.estop_button_invert
        except:
            self.button_off = False
        self.button_on = not self.button_off

        # Read Estop LED GPIO
        try:
            self.led = digitalio.DigitalInOut(config.estop_led_gpio)
            self.led.direction = digitalio.Direction.OUTPUT 
            self.simulated = False
        except:
            self.simulated = True

        # Read Estop active-high or active-low
        try:
            self.off = config.estop_led_invert
        except:
            self.led_off = False
        self.led_on = not self.led_off
        self.turnled(self.led_off)

        # Quiet Estop during simulation for debugging
        try:
            self.quiet = config.estop_quiet
        except:
            self.quiet = False
        if self.simulated and self.quiet:
            log.warn("Estop disabled during simulation")

        self.period = 1

        self.start()

    def turnled(self, state, delay=0, msg=None):
        if not self.simulated:
            self.led.value = state
        elif msg != None and self.quiet == False:
            log.info(msg)
        time.sleep(delay)

    # This method will be executed when the thread starts
    def run(self):
        log.info("Starting E-stop monitor")

        while True:
            if not self.simulated and self.button.value == self.button_on:
                self.turnled(self.led_on, self.period, "E-stop engaged")
            else:
                self.turnled(self.led_off, self.period)
