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
def start_firing():
    """Start the firing.
    """

@hookspec
def abort_firing():
    """Stop the firing due to error.
    """

@hookspec
def get_time():
    """Get time from a centralized source.
    Time could be accelerated during simulation and testing.
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

@hookspec
def record_meta(info: dict):
    """Send data to UI. Key/Value is added to kiln.ovenState.
    """

@hookspec
def record_temperature(info: dict):
    """Save Thermocouple temperate and heating rate.
    """

class PluginHooks:

    @hookspec
    def activity(self):
        """Indicate that activity has ocurred. Used for heartbeat.
        """

    @hookspec
    def heat(self):
        """Get time from a centralized source.
        Time could be accelerated during simulation and testing.
        """
