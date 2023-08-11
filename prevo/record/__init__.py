"""Record module of the prevo package (periodic sensor recording)"""

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

from .general import SensorBase, SensorError
from .general import RecordingBase, Record
from .general import ControlledEvent, ControlledProperty

# NOTE -- DO NOT include the line below, because it results in circular
# imports problem with prevo.plot (NumericalGraph)
# from .numerical import NumericalRecording, NumericalRecord
# from .images import ImageRecording, ImageRecord
