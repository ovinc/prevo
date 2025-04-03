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

    def __init__(
        self,
        path,
        column_names=None,
        column_formats=None,
        csv_separator='\t',
    ):
        """Init CsvFile object

        Parameters
        ----------

        path : {str, pathlib.Path}
            path to file, including filename and extension

        column_names : {array_like[str], None}, optional
            (optional, for saving data): iterable of column names

        column_formats : {array_like[str], None}, optional
            iterable of str formatings of data in columns

        path : {str, pathlib.Path}, optional
            folder in which file is located (default current folder)

        csv_separator: str
            separator used to separate data in file
        """
        self.path = Path(path)
        self.csv_separator = csv_separator
        self.column_names = column_names
        self.column_formats = column_formats

        if column_formats is None and self.column_names is not None:
            self.column_formats = ('',) * len(column_names)

    def load(self, nrange=None):
        """Load data recorded in path, possibly with a range of indices (n1, n2).

        Parameters
        ----------
        nrange : {tuple[int], None}
            select part of the data:
            - if nrange is None (default), load the whole file.
            - if nrange = (n1, n2), loads the file from line n1 to line n2,
              both n1 and n2 being included (first line of data is n=1).

        Returns
        -------
        pandas.DataFrame
            Pandas DataFrame of the requested size.
        """
        if nrange is None:
            kwargs = {}
        else:
            n1, n2 = nrange
            kwargs = {'skiprows': range(1, n1), 'nrows': n2 - n1 + 1}
        return pd.read_csv(self.path, delimiter=self.csv_separator, **kwargs)

    def number_of_lines(self):
        """Return number of lines of a file"""
        with open(self.path, 'r') as f:
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
        with open(self.path, 'a', encoding='utf8') as file:
            self._init_file(file)


def resample_numerical_data(
    old_file,
    rule,
    new_file=None,
    sep='\t',
    column_formats=None,
):
    """Resample data that has a 'time (unix)' column.

    Takes data from the file and saves it into a new file.

    Parameters
    ----------
    old_file : {str, pathlib.Path}
        path to the old file containing the metadata

    rule : str
        pandas rule for resampling, e.g. "10s" for every 10 seconds

    new_file : {str, pathlib.Path}, optional
        if not supplied, use same name but with '_resampled' added in the name

    sep : str, optional
        separator used in the csv_file

    column_formats : array_like[str]
        iterable of f-string formatting of every column (including unix time)
        e.g. ('.3f', '.6f', '.0f')
        if None, use .3f for every column
    """
    data = pd.read_csv(old_file, sep=sep)

    data['datetime'] = pd.to_datetime(data['time (unix)'], unit='s')
    resampled_data = data.resample(rule=rule, on='datetime').mean()
    new_data = resampled_data.reset_index().drop('datetime', axis=1)

    if column_formats is not None:
        for name, fmt in zip(new_data, column_formats):
            new_data[name] = new_data[name].map(lambda x: f"{x:{fmt}}")
        float_format = None
    else:
        float_format = "%.3f"

    file = Path(old_file)
    if new_file is None:
        new_file = file.with_name(f"{file.stem}_resampled{file.suffix}")

    new_data.to_csv(new_file, sep=sep, index=False, float_format=float_format)
