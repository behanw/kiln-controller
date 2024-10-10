import logging
import config
import time

log = logging.getLogger("plugins." + __name__)

from kilnapp.plugins import hookimpl, KilnPlugin

class TestStatus(KilnPlugin):
    '''Testing of the status hooks for plugins.
        config.test_verbose
    '''
    def __init__(self):
        super().__init__()

    @hookimpl
    def record_meta(self, info: dict):
        try:
            if config.test_verbose:
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
    #testStatusObj = TestStatus()
    #testStatusObj.start()

