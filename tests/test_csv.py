"""Tests for the prevo package.

(VERY partial)
"""

# Standard library
from pathlib import Path

# local imports
import prevo
from prevo.csv import CsvFile, resample_numerical_data


DATAFOLDER = Path(prevo.__file__).parent / '..' / 'data'
DATA_FILE = DATAFOLDER / 'manip' / 'Vacuum_Pressure.tsv'
out_file_1 = DATAFOLDER / 'untracked_data' / 'Pressure_resampled_1.tsv'
out_file_2 = DATAFOLDER / 'untracked_data' / 'Pressure_resampled_2.tsv'


def test_resample_simple():
    """Resampling of numerical data, default parameters"""
    resample_numerical_data(DATA_FILE, '30s', new_file=out_file_1)
    csv_file = CsvFile(out_file_1)
    assert csv_file.path.exists()
    assert csv_file.number_of_measurements() == 3758


def test_resample_advanced():
    """Resampling of numerical data"""

    resample_numerical_data(
        DATA_FILE,
        '2min',
        column_formats=('.3f', '.3f', '.2f'),
        new_file=out_file_2,
    )
    csv_file = CsvFile(out_file_2)
    assert csv_file.path.exists()
    assert csv_file.number_of_measurements() == 940
