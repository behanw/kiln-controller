import config
import logging

log = logging.getLogger(__name__)

def has_setting(*names):
    for name in names:
        if not hasattr(config, name):
            return False
    return True

def setting(name: str, default=0, helpmsg="Missing configuration"):
    if hasattr(config, name):
        return config.__dict__[name]
    elif default:
        return default
    else:
        log.critical("{}: {}".format(name, helpmsg))
        raise

def ifsetting(name: str, value, iftrue, iffalse, default=False, helpmsg="Missing configuration"):
    lookup = setting(name, default, helpmsg)
    if type(lookup) == str:
        lookup = lookup.lower()
        value = value.lower()
    if lookup == value: 
        return iftrue
    else:
        return iffalse

def ignore_compare(msg: str, value: str, ignore: str) -> bool:
        msg == value and setting(ignore)
