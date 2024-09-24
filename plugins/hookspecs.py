import pluggy
hookspec = pluggy.HookspecMarker("kilnctrl")

@hookspec
def activity():
    """Indicate that activity has ocurred. Used for heartbeat.
    """


@hookspec
def failure(reason: dict):
    """Indicate a failure has ocurred.

    :param reason: failure reason
    """
