from . import hookspec

class PluginHooks:

    @hookspec
    def start_plugin(self):
        """Start plugins. Used by all plugins
        """
        # kilnapp -> all plugins

    @hookspec
    def on_start(self):
        """Run when app starts. (Not currently used)
        """
        # Not currently used
        # kilnapp -> Whomever

    @hookspec
    def activity(self):
        """Indicate that activity has ocurred. Used for heartbeat.
           (Probably should use heat() instead?)
        """
        # Deprecated?
        # oven -> heartbeat

    @hookspec
    def start_firing(self):
        """Start the firing.
        Don't know it this is needed?
        Perhaps a generic event hook?
        """
        # Not currently used
        # ? oven -> Controller
        # Run profile?

    @hookspec
    def get_time(self):
        """Get time from a centralized source.
        Time could be accelerated during simulation and testing.
        Should be provided by the Oven (real or simulateds)
        """
        # Not currently used
        # ? -> Thermocouple?

    @hookspec
    def temperature_reading(self, info: dict):
        """Save Thermocouple temperate and heating rate.
        Perhaps should be renamed?
        Sends temperature readings to PID and UI.
        """

    @hookspec
    def sensor_reading(self, info: dict):
        """Thermocouple readings.  Sends sensor readings to PID and UI.
        """

    @hookspec
    def heat(self, info):
        """Turn heat on for a percentage of the duty cycle.
        Controls relays, or simulated heat in the oven or kiln.
        """
        # Used by control to communicate to heater relay

    @hookspec
    def add_cost(self, info):
        """Add cost for duty_cycle.
        Heat leads to cost, which is sent to status.
        """
        # Heater -> State

    @hookspec
    def abort_firing(self):
        """Stop the firing due to error.
        Perhaps a generic event hook?
        """
        # Stop firing

    @hookspec
    def failure(self, info: dict):
        """Indicate a failure has ocurred.
        :param reason: failure reason
        """
        # Used by caution

    @hookspec
    def clear_failure(self, info: dict=None):
        """Indicate the failure has been cleared.
        :param reason: Reason for failure being cleared
        """
        # Used by caution
