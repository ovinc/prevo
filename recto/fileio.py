"""General file input/output."""


from pathlib import Path

import pandas as pd


class CsvFile:

    def __init__(self, filename, column_names, column_formats=None,
                 path='.', csv_separator='\t'):
        """Parameters:

        - file: file object (or str) to read.
        - csv_separator: separator (str) used to separate data in file
        - column_names, column_formats: only to use init_file() and save_line()
        """
        self.path = Path(path)
        self.file = self.path / filename
        self.csv_separator = csv_separator

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

    def init_file(self):
        """How to init the file containing the data."""
        # Line below allows the user to re-start the recording and append data
        if not self.file.exists():
            with open(self.file, 'w', encoding='utf8') as f:
                f.write(f'{self.csv_separator.join(self.column_names)}\n')

    def _save_line(self, data, file):
        """Save data to file when file is already open."""
        data_str = [f'{x:{fmt}}' for x, fmt in zip(data, self.column_formats)]
        line_for_saving = self.csv_separator.join(data_str) + '\n'
        file.write(line_for_saving)

    def save_line(self, data):
        """Save data to file, when file has to be opened"""
        # convert to list of str with the correct format
        with open(self.file, 'a') as file:
            self._save_line(data, file)


class ConfiguredCsvFile(CsvFile):
    """Same as CsvFile, but with keys (names) instead of files."""

    def __init__(self, config, name, path='.'):
        """Parameters:
        - config: configuration dict, with the following keys:
            - 'file names': {name: file_name} dict
            - 'csv separator': str describing the csv
            - 'column name': iterable of column names
            - 'column formats': iterable of column formats
        - name: name of data to load, following names in config.py (e.g. 'P')
        - path: directory in which data files are stored
        """
        super().__init__(filename=config['file names'][name], path=path,
                         csv_separator=config['csv separator'],
                         column_names=config['column names'],
                         column_formats=config['column formats'])
