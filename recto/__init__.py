"""Base package to record data periodically from sensors"""

from .misc import NamesMgmt
from .fileio import CsvFile, ConfiguredCsvFile
from .fileio import RecordingToCsv, RecordingToCsvConfigured
from .measurements import MeasurementBase, LiveMeasurement
from .record import SensorBase, SensorError, RecordingBase, RecordBase
from .plot import GraphBase, SavedGraph, SensorGraphUpdated, SavedGraphUpdated
from .view import CameraViewBase, max_possible_pixel_value

from importlib_metadata import version

__author__ = "Olivier Vincent"
__version__ = version("recto")
