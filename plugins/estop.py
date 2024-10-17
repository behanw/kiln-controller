import logging
import time

from settings import config

log = logging.getLogger("plugins." + __name__)

from plugins import hookimpl, KilnPlugin, plugin_manager

class Estop(KilnPlugin):
    '''This reads the state of the estop button.
    Although the estop directly controls power to the kiln,
    this GPIO allows us to know if it's been pushed or not.
    '''
    def __init__(self):
        super().__init__(__name__)
        self.active = True
        self.record_estop("Okay")

        # Read Estop Button GPIO, active-high or active-low
        try:
            (pin, self.released) = config.get_gpio('plugins.estop.switch.gpio')
            self.pressed = not self.released

            import digitalio
            self.button = digitalio.DigitalInOut(pin)
            self.button.direction = digitalio.Direction.INPUT

            self.simulated = False
        except:
            self.simulated = True

        self.verbose = config.get_log_subsystem('estop')

    def record_estop(self, status: str) -> None:
        self.hook.record_meta(info={"estop": status})

    def ispressed(self):
        if self.simulated:
            return False
        if self.button.value == self.pressed:
            # Debounce
            for n in range(5):
                time.sleep(.1)
                if self.button.value == self.pressed:
                    return True
            log.warning("Estop needed to be debounced")
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
                #log.warning("button pressed")
                self.hook.failure(info={
                    "reason": "E-stop engaged",
                    "pattern": "fail"
                    })
                self.active = True
                self.record_estop("STOP")
            elif self.active and self.isreleased():
                self.hook.clear_failure(info={
                    "reason": "E-stop released",
                    "pattern": "off"
                    })
                self.active = False
                self.record_estop("Okay")
            time.sleep(self.period)

    @hookimpl
    def start_plugin(self):
        self.start()

plugin_manager.register(Estop())
