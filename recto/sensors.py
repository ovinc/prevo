"""General variables and functions used throughout the vacuum module."""


# Standard library imports
from datetime import datetime
from abc import ABC, abstractmethod
from sklearn.model_selection import cross_val_predict

# Non standard imports
from tzlocal import get_localzone

# Local imports
from .fileio import CsvFile
from .record import RecordingBase

timezone = get_localzone()


# ============================== Sensor classes ==============================


class SensorError(Exception):
    pass


class SensorBase(ABC):
    """Abstract base class for sensor acquisition."""

    def __init__(self):
        # (optional) : specific sensor errors to catch, can be an Exception
        # class or an iterable of exceptions; if not specified in subclass,
        # any exception is catched.
        self.exceptions = Exception

    @property
    @abstractmethod
    def name(self):
        """Name of sensor, attribute must be defined in sensor subclass."""
        pass

    @abstractmethod
    def _read(self, *args, **kwargs):
        """Read sensor, method must be defined in sensor subclass."""
        pass

    def read(self, *args, **kwargs):
        """Read sensor and throw SensorError if measurement fails."""
        try:
            data = self._read(*args, **kwargs)
        except self.exceptions:
            raise SensorError(f'Impossible to read {self.name} sensor')
        else:
            return data


def create_sensor_dict(sensor_list):
    """Create dict of correspondence of sensor name and sensor classes."""
    sensors = {}
    for Sensor in sensor_list:
        sensors[Sensor.name] = Sensor
    return sensors


# ======================== Sensor recordings classes =========================


class SensorRecordingBase(RecordingBase):
    """Recording sensor objects. Needs to be subclassed.

    See RecordingBase for required attributes / methods.
    """

    def __init__(self, sensor, dt):
        """Parameters:

        sensor: object with a .name attribute
        dt: default / initial time interval between data readings
        """
        self.sensor = sensor
        self.SensorError = SensorError  # can be modified if necessary
        self.name = self.sensor.name


class RecordingToCsv(RecordingBase):
    """Recording data to CSV file."""

    def __init__(self, filename, column_names, column_formats=None,
                 path='.', csv_separator='\t'):
        """Init Recording to CSV object"""

        self.csv_file = CsvFile(filename=filename,
                                path=path,
                                csv_separator=csv_separator,
                                column_names=column_names,
                                column_formats=column_formats
                                )

        self.file = self.csv_file.file

    def init_file(self):
        return self.csv_file.init_file()

    def measurement_to_data_iterable(self, measurement):
        """How to convert measurement to an iterable of data.

        Input
        -----
        Measurement object

        Output
        ------
        Iterable of data to be saved in CSV file

        The length of the iterable must be equal to that of column_names.
        Needs to be defined in subclasses.
        """
        pass

    def save(self, measurement, file):
        data_iterable = self.measurement_to_iterable(measurement)
        self.csv_file._save_line(data_iterable, file)


class ConfiguredCsvSensorRecording(SensorRecordingBase):
    """Additional methods to SensorRecordingBase for configured recordings."""

    def __init__(self, sensor, config, path='.'):
        """config must have keys:
        - 'default dts',
        - 'file names'
        - 'csv separator'
        - 'column names'
        - 'column formats'
        """
        self.config = config

        SensorRecordingBase.__init__(self, sensor=sensor,
                                     dt=config['default dts'][name])

        self.csv_file = ConfiguredCsvFile(config=config, name=name, path=path)

        self.column_names = self.config['column names'][name]
        self.column_formats = self.config['column formats'][name]


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
