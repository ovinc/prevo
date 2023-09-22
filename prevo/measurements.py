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
from pathlib import Path
from queue import Queue

# Local imports
from .csv import CsvFile
from .misc import PeriodicThreadedSystem


# ======================= Base classes for saved data ========================
# ------------------- (used for plotting, loading, etc.) ---------------------


class SavedDataBase(ABC):
    """Abstract base class for live measurements of sensors"""

    def __init__(self, name, filename, path='.'):
        """Parameters:
        - name: name of sensor/recording
        """
        self.name = name
        self.filename = filename
        self.path = Path(path)
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


class SavedCsvData(SavedDataBase):
    """Class managing saved measurements to CSV files (with pandas)"""

    def __init__(self,
                 name,
                 filename,
                 path='.',
                 csv_separator='\t'):

        super().__init__(name=name,
                         filename=filename,
                         path=path)

        self.csv_file = CsvFile(filename=self.filename,
                                path=self.path,
                                csv_separator=csv_separator)

    def load(self, nrange=None):
        self.data = self.csv_file.load(nrange=nrange)

    def number_of_measurements(self):
        return self.csv_file.number_of_measurements()

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


# =========== Classes to get measurements from files periodically ============


class PeriodicMeasurementsFromFile(PeriodicThreadedSystem):
    """Get measurements by reading periodically from file where data is saved.

    New measurements detected in file are put in a queue (self.queue).
    """

    def __init__(self, saved_data, only_new=False, **kwargs):
        """Init PeriodicMeasurementsFromFile object

        Parameters
        ----------

        - saved_data: object of the SavedData class or subclasses/equivalent
        - only_new: if True, do not put in queue measurements that are already
                    saved in the file when the file monitoring is started.

        Additional KWARGS inherited from PeriodicThreadedSystem:
        - interval: update interval in seconds
        - precise (bool): use the precise option in oclock.Timer
        """
        self.saved_data = saved_data
        self.only_new = only_new
        self.queue = Queue()
        super().__init__(**kwargs)

    def _update(self):
        """Must return data ready to put in queue."""
        n = self.saved_data.number_of_measurements()
        if n > self.n0:
            self.saved_data.load(nrange=(self.n0 + 1, n))
            if self.saved_data.data is not None:
                measurement = self.saved_data.format_as_measurement()
                self.queue.put(measurement)
                self.n0 = n

    def _on_start(self):
        """Anything to do when system is started."""
        if self.only_new:
            self.n0 = self.saved_data.number_of_measurements()
        else:
            self.n0 = 0
