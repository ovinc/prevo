"""General variables and functions used throughout the vacuum module."""


# Standard library imports
from datetime import datetime

# Non standard imports
from tzlocal import get_localzone


timezone = get_localzone()


# Measurement classes ========================================================


class MeasurementBase:
    """Base class for measurements data.

    Parameter
    ---------
    Name: sensor / recording name
    """
    def __init__(self, name, data):
        self.name = name
        self.data = data


class LiveMeasurement(MeasurementBase):
    """General class containing live measurement data.

    Parameters
    ----------
    - name: name of sensor
    - data: data from sensor
    """
    def format_for_plot(self):
        """Generate useful attributes for plotting on a Graph() object."""
        unix_time = self.data['time (unix)']
        self.time = datetime.fromtimestamp(unix_time, timezone)
        self.values = self.data['value']
