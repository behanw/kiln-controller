import logging
import os
import pluggy
import sys
import threading

from settings import config

log = logging.getLogger(__name__)

plugin_namespace = 'kilnctrl'

# Define the hookspec
hookspec = pluggy.HookspecMarker(plugin_namespace)
hookimpl = pluggy.HookimplMarker(plugin_namespace)

# Hook implementation manager
plugin_manager = pluggy.PluginManager(plugin_namespace)

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

from plugins.hookspecs import PluginHooks
plugin_manager.add_hookspecs(PluginHooks)
plugin_manager.load_setuptools_entrypoints(plugin_namespace)

# Import plugins listed in the configuration
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
for name in config.get('plugins', None, "Plugin list missing").keys():
    log.debug("Register "+name)
    obj = __import__(name)
