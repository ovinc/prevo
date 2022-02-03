"""Base package to record data periodically from sensors"""

from .sensors import SensorRecordingBase, MeasurementBase
from .record import RecordBase

from importlib_metadata import version

__author__ = "Olivier Vincent"
__version__ = version("recto")
