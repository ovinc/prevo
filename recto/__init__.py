"""Base package to record data periodically from sensors"""

from .misc import NamesMgmt
from .fileio import CsvFile, RecordingToCsv
from .measurements import LiveMeasurementBase, SavedMeasurementBase
from .measurements import LiveMeasurement, SavedMeasurementCsv
from .record import SensorBase, SensorError, RecordingBase, RecordBase
from .plot import GraphBase, NumericalGraph
from .plot import PlotLiveSensors, PlotSavedData, PlotSavedDataUpdated
from .view import CameraViewCv, CameraViewMpl, max_possible_pixel_value

from importlib_metadata import version

__author__ = "Olivier Vincent"
__version__ = version("recto")
