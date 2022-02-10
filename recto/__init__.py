"""Base package to record data periodically from sensors"""

from .misc import NamesMgmt
from .fileio import CsvFile, ConfiguredCsvFile
from .measurements import SensorBase, SensorError, create_sensor_dict
from .measurements import MeasurementBase, LiveMeasurement
from .measurements import SensorRecordingBase, ConfiguredCsvSensorRecording
from .record import RecordBase
from .plot import GraphBase, SavedGraph, SensorGraphUpdated, SavedGraphUpdated
from .view import CameraViewBase, max_possible_pixel_value

from importlib_metadata import version

__author__ = "Olivier Vincent"
__version__ = version("recto")
