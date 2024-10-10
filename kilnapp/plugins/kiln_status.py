import logging
import config

log = logging.getLogger("plugins." + __name__)

from kilnapp.routes import kiln
from kilnapp.plugins import hookimpl, KilnPlugin

@hookimpl
def abort_firing():
    times = kiln.end_run()

@hookimpl
def get_time():
    times = kiln.state.get_time()
    log.info("get_time: {}", times)
    return times

@hookimpl
def record_meta(info: dict):
    #log.debug("*** record_meta: {}".format(info))
    for key, value in info.items():
        #log.debug("record_meta: {} = {}".format(key, value))
        kiln.state.set(key, value)

@hookimpl
def record_temperature(info: dict):
    #log.info("*** record_temperature: {}".format(info))
    kiln.state.set_temperatures(info)
