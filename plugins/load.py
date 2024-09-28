import os
import sys
import logging
import pluggy
import config

log = logging.getLogger(__name__)
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

def get_pluginmanager():
    pm = pluggy.PluginManager("kilnctrl")
    from plugins import hookspecs
    pm.add_hookspecs(hookspecs)
    pm.load_setuptools_entrypoints("kilnctrl")

    plugin_dict = {}
    for name in config.Plugins:
        log.info("Register "+name)
        plugin_dict[name] = {}
        obj = __import__(name)
        pm.register(obj)
        plugin_dict[name]["import"] = obj

    for name in config.Plugins:
        #log.info("Start "+name)
        plugin_dict[name]["thread"] = plugin_dict[name]["import"].startPlugin(pm.hook)
        #try:
        #    plugin_dict[name].sethook(pm.hook)
        #except AttributeError:
        #    pass

    pm.plugin_dict = plugin_dict
    return pm
