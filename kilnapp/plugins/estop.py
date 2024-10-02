import logging
import config
import time
import digitalio

log = logging.getLogger("plugins." + __name__)

from kilnapp.plugins import hookimpl, KilnPlugin

class Estop(KilnPlugin):
    '''This reads the state of the estop button.
    Although the estop directly controls power to the kiln,
    this GPIO allows us to know if it's been pushed or not.
        config.estop_gpio
        config.estop_invert
        config.estop_quiet
    '''
    def __init__(self):
        super().__init__()
        self.active = True

        # Read Estop Button GPIO
        try:
            self.button = digitalio.DigitalInOut(config.estop_gpio)
            self.button.direction = digitalio.Direction.INPUT
            self.simulated = False
        except:
            self.simulated = True

        # Read Estop Button active-high or active-low
        try:
            self.released = config.estop_invert
        except:
            self.released = False
        self.pressed = not self.released

        # Quiet Estop during simulation for debugging
        try:
            self.quiet = config.estop_quiet
        except:
            self.quiet = False
        if self.simulated and self.quiet:
            log.warn("Estop disabled during simulation")

    def ispressed(self):
        if self.simulated:
            return False
        if self.button.value == self.pressed:
            # Debounce
            for n in range(5):
                time.sleep(.1)
                if self.button.value == self.pressed:
                    return True
            log.warn("Estop needed to be debounced")
        return False

    def isreleased(self):
        if self.simulated:
            return True
        if self.button.value == self.released:
            return True
        return False

    # This method will be executed when the thread starts
    def run(self):
        log.info(self.message("Starting E-stop monitor"))

        while True:
            if not self.active and self.ispressed():
                #log.warn("button pressed")
                self.hook.failure(info={
                    "reason": "E-stop engaged",
                    "pattern": "fail"
                    })
                self.active = True
            elif self.active and self.isreleased():
                self.hook.clear_failure(info={
                    "reason": "E-stop released",
                    "pattern": "off"
                    })
                self.active = False
            time.sleep(self.period)

estopObj = None

@hookimpl
def start_plugin():
    global estopObj
    estopObj = Estop()
    estopObj.start()

