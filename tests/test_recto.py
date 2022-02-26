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


datafolder = Path(prevo.__file__).parent / '..' / 'data/manip'

t_column, dt_column = 'time (unix)', 'dt (s)'

names = 'P', 'T', 'B1'
filenames = {'P': 'Vacuum_Pressure.tsv',
             'T': 'Vacuum_Temperature.tsv',
             'B1': 'Vacuum_SourceBath.tsv'}

meas_numbers = {'P': 22553, 'T': 11271, 'B1': 9883}

n = 8  # measurement line number to check when loading full file
# (considering first data line is numbered 1)

nrange = (5, 10)  # range for partial loading test
nred = n - nrange[0] + 1  # corresponding line in the partial data

lines = {'P': (1616490450.506, 0.167, 2727.25),
         'T': (1616490515.961, 2.623, 26.8932, 25.4829),
         'B1': (1616490514.585, 0.091, 24.2640)}

measP = SavedCsvData('P', filenames['P'], datafolder)
measT = SavedCsvData('T', filenames['T'], path=datafolder)
measB1 = SavedCsvData(name='B1', filename=filenames['B1'],
                      path=datafolder, csv_separator='\t')

saved_datas = {'P': measP, 'T': measT, 'B1': measB1}


def test_number_of_measurements():  # test with a variety of call options
    ns = [sdata.number_of_measurements() for sdata in saved_datas.values()]
    assert ns == list(meas_numbers.values())


@pytest.mark.parametrize('name', names)
def test_load_full(name):             # test full loading of data from file
    sdata = saved_datas[name]
    sdata.load()
    assert len(sdata.data) == meas_numbers[name]
    assert tuple(sdata.data.loc[n - 1].round(decimals=4)) == lines[name]


@pytest.mark.parametrize('name', names)
def test_load_partial(name):
    sdata = saved_datas[name]
    sdata.load(nrange)  # test partial loading of data
    assert len(sdata.data) == nrange[1] - nrange[0] + 1
    assert tuple(sdata.data.loc[nred - 1].round(decimals=4)) == lines[name]
