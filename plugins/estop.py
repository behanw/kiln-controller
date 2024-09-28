import logging
import config
import time
import digitalio

log = logging.getLogger(__name__)

from plugins.kilnplugin import KilnPlugin

class Estop(KilnPlugin):
    '''This reads the state of the estop button.
    Although the estop directly controls power to the kiln,
    this GPIO allows us to know if it's been pushed or not.
        config.estop_gpio
        config.estop_invert
        config.estop_quiet
    '''
    def __init__(self, hook=None):
        super().__init__(hook)

        # Read Estop Button GPIO
        try:
            self.button = digitalio.DigitalInOut(config.estop_button_gpio)
            self.button.direction = digitalio.Direction.INPUT 
            self.simulated = False
        except:
            self.simulated = True

        # Read Estop Button active-high or active-low
        try:
            self.unpressed = config.estop_invert
        except:
            self.unpressed = False
        self.pressed = not self.unpressed

        # Quiet Estop during simulation for debugging
        try:
            self.quiet = config.estop_quiet
        except:
            self.quiet = False
        if self.simulated and self.quiet:
            log.warn("Estop disabled during simulation")

    # This method will be executed when the thread starts
    def run(self):
        log.info(self.message("Starting E-stop monitor"))

        while True:
            if self.hook:
                if not self.simulated and self.button.value == self.pressed:
                    #log.warn("button pressed")
                    self.hook.failure(info={
                        "reason": "E-stop engaged",
                        "pattern": "fail"
                        })
                else:
                    self.hook.clear_failure(info={
                        "reason": "E-stop released",
                        "pattern": "off"
                        })
            time.sleep(self.period)

estopObj = None

def startPlugin(hook=None):
    global estopObj
    estopObj = Estop(hook)
    estopObj.start()
    return estopObj

