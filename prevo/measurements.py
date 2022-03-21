"""Formatting sensor measurements giving numerical values.

Assumes data is saved with columns : time (unix), dt (s), m1, m2 ...
where m1, m2 are the different channels of the measurement.

Can be subclassed for arbitrary measurement formatting.
"""

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


# Standard library imports
from abc import ABC, abstractmethod

# Local imports
from .csv import CsvFile



# ======================= Base classes for saved data ========================
# ------------------- (used for plotting, loading, etc.) ---------------------


class SavedDataBase(ABC):
    """Abstract base class for live measurements of sensors"""

    def __init__(self, name):
        """Parameters:
        - name: name of sensor/recording
        """
        self.name = name
        self.data = None

    @abstractmethod
    def load(self, nrange=None):
        """Load measurement from saved data (time, etc.) into self.data

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
    def format_as_measurement(self):
        """Transform loaded data into something usable (e.g. by plots etc.)"""
        pass


# ========================== Examples of subclasses ==========================


class SavedCsvData(CsvFile, SavedDataBase):
    """Class managing saved measurements to CSV files (with pandas)"""

    def __init__(self, name, filename, path='.', csv_separator='\t'):

        SavedDataBase.__init__(self, name=name)

        CsvFile.__init__(self, filename=filename, path=path,
                         csv_separator=csv_separator)

    def load(self, nrange=None):
        self.data = CsvFile.load(self, nrange=nrange)

    def format_as_measurement(self):
        """Generate useful attributes for plotting on a Graph() object.

        Here we assume that the first two columns in the csv represent
        - time (unix)
        - dt (s)
        and are considered as time columns, not value columns
        """
        measurement = {}
        measurement['name'] = self.name
        measurement['time (unix)'] = self.data['time (unix)'].values
        # remove time columns
        measurement['values'] = [column.values for _, column in self.data.iloc[:, 2:].items()]
        return measurement
