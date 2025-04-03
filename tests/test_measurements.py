"""Tests for the prevo package.

(VERY partial)
"""

# Standard library
from pathlib import Path

# Non standard
import pytest

# local imports
import prevo
from prevo.measurements import SavedCsvData


DATAFOLDER = Path(prevo.__file__).parent / '..' / 'data/manip'

NAMES = 'P', 'T', 'B1'

FILENAMES = {
    'P': 'Vacuum_Pressure.tsv',
    'T': 'Vacuum_Temperature.tsv',
    'B1': 'Vacuum_SourceBath.tsv',
}

MEAS_NUMBERS = {'P': 22553, 'T': 11271, 'B1': 9883}

n = 8  # measurement line number to check when loading full file
# (considering first data line is numbered 1)

nrange = (5, 10)  # range for partial loading test
nred = n - nrange[0] + 1  # corresponding line in the partial data

LINES = {
    'P': (1616490450.506, 0.167, 2727.25),
    'T': (1616490515.961, 2.623, 26.8932, 25.4829),
    'B1': (1616490514.585, 0.091, 24.2640),
}

measP = SavedCsvData('P', DATAFOLDER / FILENAMES['P'])
measT = SavedCsvData('T', path=DATAFOLDER / FILENAMES['T'])
measB1 = SavedCsvData(
    name='B1',
    path=DATAFOLDER / FILENAMES['B1'],
    csv_separator='\t',
)

SAVED_DATA = {'P': measP, 'T': measT, 'B1': measB1}


def test_number_of_measurements():  # test with a variety of call options
    ns = [sdata.number_of_measurements() for sdata in SAVED_DATA.values()]
    assert ns == list(MEAS_NUMBERS.values())


@pytest.mark.parametrize('name', NAMES)
def test_load_full(name):             # test full loading of data from file
    sdata = SAVED_DATA[name]
    sdata.load()
    assert len(sdata.data) == MEAS_NUMBERS[name]
    assert tuple(sdata.data.loc[n - 1].round(decimals=4)) == LINES[name]


@pytest.mark.parametrize('name', NAMES)
def test_load_partial(name):
    sdata = SAVED_DATA[name]
    sdata.load(nrange)  # test partial loading of data
    assert len(sdata.data) == nrange[1] - nrange[0] + 1
    assert tuple(sdata.data.loc[nred - 1].round(decimals=4)) == LINES[name]
