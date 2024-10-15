import os
import sys
import logging
import pluggy
import threading

from kilnapp.settings import setting

log = logging.getLogger(__name__)

# Define the hookspec
hookspec = pluggy.HookspecMarker("kilnctrl")
hookimpl = pluggy.HookimplMarker("kilnctrl")

# Hook implementation manager
plugin_manager = pluggy.PluginManager("kilnctrl")

class KilnPlugin(threading.Thread):
    def __init__(self, name: str="plugin"):
        threading.Thread.__init__(self)
        self.daemon = True
        self.name = name

        # Simulation unless configured otherwise
        self.simulated = True
        self.quiet = False
        self.verbose = True
        self.hook = plugin_manager.hook
        self.period = 1

    def __del__(self):
        log.warning("Deleting {}".format(__name__))

    def message(self, msg):
        if self.simulated:
            return msg+" (Simulated)"
        else:
            return msg

from kilnapp.plugins import hookspecs
plugin_manager.add_hookspecs(hookspecs)
plugin_manager.load_setuptools_entrypoints('kilnctrl')

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
#plugin_dict = {}
#for name in config.Plugins:
for name in setting("Plugins", ["kiln_status"], "Plugin list missing"):
    log.debug("Register "+name)
    #plugin_dict[name] = {}
    obj = __import__(name)
    plugin_manager.register(obj)
    #plugin_dict[name]["import"] = obj
