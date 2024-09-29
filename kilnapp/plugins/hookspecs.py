from . import hookspec

@hookspec
def start_plugin():
    """Start plugins
    """

@hookspec
def on_start():
    """Run when app starts
    """

@hookspec
def activity():
    """Indicate that activity has ocurred. Used for heartbeat.
    """

@hookspec
def failure(info: dict):
    """Indicate a failure has ocurred.

    :param reason: failure reason
    """

@hookspec
def clear_failure(info: dict):
    """Indicate the failure has been cleared.

    :param reason: Reason for failure being cleared
    """
