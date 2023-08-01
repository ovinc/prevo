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

    def __init__(self,
                 filename,
                 column_names=None,
                 column_formats=None,
                 path='.',
                 csv_separator='\t'):
        """Parameters:

        - path: str or pathlib.Path object: folder in which file is located
        - filename: name of file within path folder.
        - csv_separator: separator (str) used to separate data in file
        - column_names (optional, for saving data): iterable of column names
        - column_formats (optional): iterable of str formatings of data in columns
        """
        self.path = Path(path)
        self.file = self.path / filename
        self.csv_separator = csv_separator
        self.column_names = column_names
        self.column_formats = column_formats

        if column_formats is None and self.column_names is not None:
            self.column_formats = ('',) * len(column_names)

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

    # ---------- Methods that work on already opened file managers -----------

    def _init_file(self, file):
        """What to do with file when recording is started."""
        # Line below allows the user to re-start the recording and append data
        if self.number_of_lines() == 0:
            self._write_columns(file)

    def _write_columns(self, file):
        """How to init the file containing the data (when file already open)"""
        if self.column_names is None:
            return
        columns_str = f'{self.csv_separator.join(self.column_names)}\n'
        file.write(columns_str)

    def _write_line(self, data, file):
        """Save data to file when file is already open."""
        data_str = [f'{x:{fmt}}' for x, fmt in zip(data, self.column_formats)]
        line_for_saving = self.csv_separator.join(data_str) + '\n'
        file.write(line_for_saving)

    # ----------- Corresponding methods that open the file manager -----------

    def init_file(self):
        """What to do with file when recording is started."""
        with open(self.file, 'a', encoding='utf8') as file:
            self._init_file(file)
