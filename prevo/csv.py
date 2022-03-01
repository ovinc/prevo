"""General file input/output with csv files"""

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


# Standard library
from pathlib import Path

# Nonstandard
try:
    import pandas as pd
except ModuleNotFoundError:
    pass


class CsvFile:

    def __init__(self, filename, column_names=None, column_formats=None,
                 path='.', csv_separator='\t'):
        """Parameters:

        - file: file object (or str) to read.
        - csv_separator: separator (str) used to separate data in file
        - column_names (optional, for saving data): iterable of names
        - column_formats (optional, even if column_names is provided)
        """
        self.path = Path(path)
        self.file = self.path / filename
        self.csv_separator = csv_separator

        if column_names is not None:

            self.column_names = column_names

            if column_formats is None:
                self.column_formats = ('',) * len(column_names)
            else:
                self.column_formats = column_formats

    def load(self, nrange=None):
        """Load data recorded in path, possibly with a range of indices (n1, n2).

        Input
        -----
        - nrange: select part of the data:
            - if nrange is None (default), load the whole file.
            - if nrange = (n1, n2), loads the file from line n1 to line n2,
              both n1 and n2 being included (first line of data is n=1).

        Output
        ------
        Pandas DataFrame of the requested size.
        """
        if nrange is None:
            kwargs = {}
        else:
            n1, n2 = nrange
            kwargs = {'skiprows': range(1, n1),
                      'nrows': n2 - n1 + 1}

        return pd.read_csv(self.file, delimiter=self.csv_separator, **kwargs)

    def number_of_lines(self):
        """Return number of lines of a file"""
        with open(self.file, 'r') as f:
            for i, line in enumerate(f):
                pass
            try:
                return i + 1
            except UnboundLocalError:  # handles the case of an empty file
                return 0

    def number_of_measurements(self):
        """Can be subclassed (here, assumes column titles)"""
        return self.number_of_lines() - 1

    def _write_columns(self, file):
        """How to init the file containing the data (when file already open)"""
        columns_str = f'{self.csv_separator.join(self.column_names)}\n'
        file.write(columns_str)

    def write_columns(self):
        """How to init the file containing the data."""
        # Line below allows the user to re-start the recording and append data
        with open(self.file, 'w', encoding='utf8') as file:
            self._write_columns(file)

    def _write_line(self, data, file):
        """Save data to file when file is already open."""
        data_str = [f'{x:{fmt}}' for x, fmt in zip(data, self.column_formats)]
        line_for_saving = self.csv_separator.join(data_str) + '\n'
        file.write(line_for_saving)

    def write_line(self, data):
        """Save data to file, when file has to be opened"""
        # convert to list of str with the correct format
        with open(self.file, 'a', encoding='utf8') as file:
            self._write_line(data, file)


class RecordingToCsv:
    """Recording data to CSV file.

    Provides the following attributes and methods for RecordBase:
    - self.file
    - self.init_file()
    - self.save()

    Requires definition of the following methods in subclasses:
    - measurement_to_data_iterable()
    """

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

    def init_file(self, file):
        # Line below allows the user to re-start the recording and append data
        if self.csv_file.number_of_lines() == 0:
            self.csv_file._write_columns(file)

    def format_measurement(self, measurement):
        """Format raw sensor data.

        Here, we assume a standard measurement as a dict with keys
        'time (unix)', 'dt (s)', 'values'
        """
        if measurement is None:
            return
        measurement['name'] = self.name
        return measurement

    def measurement_to_data_iterable(self, measurement):
        """How to convert measurement to an iterable of data.

        Input
        -----
        Measurement object

        Output
        ------
        Iterable of data to be saved in CSV file

        The length of the iterable must be equal to that of column_names.

        Can be redefined in subclasses.

        Here, we assume a standard measurement as a dict with keys
        'time (unix)', 'dt (s)', 'values'
        """
        return (measurement['time (unix)'], measurement['dt (s)']) + measurement['values']

    def save(self, measurement, file):
        """Save to file"""
        # Line below allows some recordings to not be saved if they give None
        if measurement is None:
            return
        data_iterable = self.measurement_to_data_iterable(measurement)
        self.csv_file._write_line(data_iterable, file)
