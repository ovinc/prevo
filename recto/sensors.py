"""General variables and functions used throughout the vacuum module."""


# Standard library imports
from pathlib import Path
from datetime import datetime
from abc import ABC, abstractmethod

# Non standard imports
import oclock
from tzlocal import get_localzone


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
        """Read sensor and save data (time, etc.) in the data attribute.

        If measurement fails, the data attribute stays None.
        """
        try:
            data = self._read(*args, **kwargs)
        except self.exceptions:
            data = None
        finally:
            # This is because sometimes the sensor sends None value instead
            # of an exception when the sensor cannot be read.
            if data is None:
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


class SensorRecordingBase(ABC):

    def __init__(self, sensor, dt):
        """Parameters:

        sensor: object with a .name attribute
        dt: default / initial time interval between data readings
        """
        self.sensor = sensor
        self.SensorError = SensorError  # can be modified if necessary

        self.name = self.sensor.name
        self.timer = oclock.Timer(interval=dt, name=self.sensor.name,
                                  warnings=True)

    def print_info_on_failed_reading(self, status):
        """Displays relevant info when reading fails."""
        t_str = datetime.now().isoformat(sep=' ', timespec='seconds')
        if status == 'failed':
            print(f'{self.name} reading failed ({t_str}). Retrying ...')
        elif status == 'resumed':
            print(f'{self.name} reading resumed ({t_str}).')

    def on_stop(self):
        """What happens when a stop event is requested in the CLI"""
        self.timer.stop()

    # ============ Methods that need to be defined in subclasses =============

    @abstractmethod
    def read(self):
        """How to read the data. Normally, self.sensor.read()"""
        pass

    @abstractmethod
    def format_measurement(self, data):
        """How to format the data given by self.read().

        Returns a measurement object."""
        pass

    @abstractmethod
    def after_measurement(self):
        """Define what to do after measurement has been done formatted.

        Acts on the recording object but does not return anything.
        """
        pass

    @abstractmethod
    def init_file(self):
        """How to init the file containing the data."""
        pass

    @abstractmethod
    def save(self, measurement):
        """How to write data of measurement to file"""
        pass

    # ======= Properties controlled by the CLI (in addition to timer) ========

    @property
    def misc_property(self):
        pass

    @misc_property.setter
    def misc_property(self, value):
        pass


class CsvFileRecordingBase:
    """Additional methods to SensorRecordingBase for saving to CSV files."""

    def __init__(self, path='.', filename=None, csv_separator='\t'):
        """Parameters:

        - path: directory into which file is saved (str or path object)
        - filename (str): file name, including extension
        - csv_separator: character separating data in csv file
        """
        self.path = Path(path)
        self.file = self.path / filename
        self.csv_separator = csv_separator

        self.column_names = ()  # Override in subclasses
        self.column_formats = ()  # Override in subclasses

    def init_file(self):
        """How to init the file containing the data."""
        # Line below allows the user to re-start the recording and append data
        if not self.file.exists():
            with open(self.file, 'w', encoding='utf8') as f:
                f.write(f'{self.csv_separator.join(self.column_names)}\n')

    def save_line(self, data):
        """How to save data to file."""
        # convert to list of str with the correct format
        data_str = [f'{x:{fmt}}' for x, fmt in zip(data, self.column_formats)]

        # make list into a single string (line) with tabs as separator
        line_for_saving = self.csv_separator.join(data_str)

        with open(self.file, 'a') as f:
            f.write(line_for_saving)
            f.write('\n')

    def number_of_measurements(self):
        """Count number of lines in data file, i.e. the number of measurements.

        If the file only has a header, returns 0 (even with \\n at end of header)
        """
        with open(self.file, 'r') as f:
            for i, line in enumerate(f):
                pass
            try:
                return i
            except UnboundLocalError:  # handles the case of an empty file
                return 0


class ConfiguredCsvSensorRecording(CsvFileRecordingBase, SensorRecordingBase):
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
        name = sensor.name

        SensorRecordingBase.__init__(self, sensor=sensor,
                                     dt=config['default dts'][name])

        CsvFileRecordingBase.__init__(self, path=path,
                                      filename=config['file names'][name],
                                      csv_separator=config['csv separator'])

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
