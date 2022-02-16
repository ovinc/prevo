"""Formatting sensor measurements giving numerical values.

Assumes data is saved with columns : time (unix), dt (s), m1, m2 ...
where m1, m2 are the different channels of the measurement.
"""


# Standard library imports
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

# Non standard imports
from tzlocal import get_localzone
try:
    import pandas as pd
except ModuleNotFoundError:
    pass

# Local imports
from .fileio import CsvFile


# Misc =======================================================================


local_timezone = get_localzone()


# =============== Base classes for live and saved measurements ===============
# --------------------------- (used for plotting) ----------------------------


class LiveMeasurementBase(ABC):
    """Abstract base class for live measurements of sensors"""

    def __init__(self, name, data):
        """Parameters:
        - name: name of sensor
        - data: data from sensor
        """
        self.name = name
        self.data = data

    @abstractmethod
    def format_for_plot(self):
        """Generate useful attributes for plotting on a Graph() object."""
        pass


class SavedMeasurementBase(ABC):
    """Abstract base class for live measurements of sensors"""

    def __init__(self, name, filename, path='.'):
        """Parameters:
        - name: name of sensor/recording
        - filename: name (str) of file in which data is stored
        - path (str or path object): directory containing data.
        """
        self.name = name
        self.filename = filename
        self.path = Path(path)
        self.data = None

    @abstractmethod
    def load(self, nrange=None):
        """Load measurement from saved data (time, etc.) into self.data.

        nrange = None should load all the data
        nrange = (n1, n2) loads measurement numbers from n1 to n2 (both
        included), and first measurement is n=1.
        """
        pass

    @abstractmethod
    def number_of_measurements(self):
        """Return total number of measurements currently saved in file."""
        pass

    @abstractmethod
    def format_for_plot(self):
        """Generate useful attributes for plotting on a Graph() object."""
        pass


# ========================== Examples of subclasses ==========================


class LiveMeasurement(LiveMeasurementBase):
    """General class containing live measurement data.

    Parameters
    ----------
    - name: name of sensor
    - data: data from sensor
    """
    def __init__(self, name, data):
        self.name = name
        self.data = data

    def format_for_plot(self):
        """Generate useful attributes for plotting on a Graph() object."""
        unix_time = self.data['time (unix)']
        self.time = datetime.fromtimestamp(unix_time, local_timezone)
        self.values = self.data['value']


class SavedMeasurementCsv(SavedMeasurementBase):
    """Class managing saved measurements to CSV files (with pandas)"""

    def __init__(self, name, filename, path='.',
                 csv_separator='\t'):

        super().__init__(name=name,
                         filename=filename,
                         path=path)

        self.csv_file = CsvFile(filename=filename,
                                path=path,
                                csv_separator=csv_separator)

    def load(self, nrange=None):
        """Load measurement from saved data (time, etc.) into self.data.

        nrange = None should load all the data
        nrange = (n1, n2) loads measurement numbers from n1 to n2 (both
        included), and first measurement is n=1.
        """
        self.data = self.csv_file.load(nrange)

    def number_of_measurements(self):
        """Return total number of measurements currently saved in file."""
        return self.csv_file.number_of_lines() - 1  # remove column titles

    def format_for_plot(self):
        """Generate useful attributes for plotting on a Graph() object."""
        unix_time = self.data['time (unix)']
        utc_time = pd.to_datetime(unix_time, unit='s', utc=True)
        self.time = utc_time.dt.tz_convert(local_timezone)
        self.values = [column for _, column in self.data.iloc[:, 2:].items()]
