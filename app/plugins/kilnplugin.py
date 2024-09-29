import logging
import threading

log = logging.getLogger(__name__)

class KilnPlugin(threading.Thread):
    def __init__(self, hook=None):
        threading.Thread.__init__(self)
        self.daemon = True

        # Simulation unless configured otherwise
        self.simulated = True
        self.quiet = False
        self.verbose = True
        self.hook = hook
        self.period = 1

    def __del__(self):
        log.warn("Deleting {}".format(__name__))

    def message(self, msg):
        if self.simulated:
            return msg+" (Simulated)"
        else:
            return msg
