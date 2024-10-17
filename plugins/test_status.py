import logging
import time

from settings import config

log = logging.getLogger("plugins." + __name__)

from plugins import hookimpl, KilnPlugin

class StatusTest(KilnPlugin):
    '''Testing of the status hooks for plugins.
    '''
    def __init__(self):
        super().__init__(__name__)
        self.verbose = config.get_log_subsystem('statustest')

    @hookimpl
    def record_meta(self, info: dict):
        try:
            if self.verbose:
                log.info(info)
        except AttributeError:
            pass

    # This method will be executed when the thread starts
    def run(self):
        log.info(self.message("Starting Test Status"))

        while True:
            if self.fail:
                if self.verbose:
                    log.info(self.fail)
            if not self.simulated:
                self.play(self.pattern)

testStatusObj = None

@hookimpl
def start_plugin():
    log.info("Starting Test Status")
    #global testStatusObj
    #testStatusObj = StatusTest()
    #testStatusObj.start()

