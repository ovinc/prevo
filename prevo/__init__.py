"""Base package to record data periodically from sensors"""

# ----------------------------- License information --------------------------

# This file is part of the prevo python package.
# Copyright (C) 2022 Olivier Vincent

# The prevo package is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# The prevo package is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with the prevo python package.
# If not, see <https://www.gnu.org/licenses/>


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
__version__ = version("prevo")
