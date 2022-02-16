About
=====

**P**eriodic **RE**cording and **V**isualization of sensor **O**bjects

This package provides base classes to rapidly create interactive data recording for various applications (e.g. recording of temperature, time-lapses with cameras etc.). Sensors are read in a asynchronous fashion and can have different time intervals for data reading (or be continuous, i.e. as fast as possible). Tools for graphical visualizations of data during recording are also provided.

Install
-------

```bash
git clone https://cameleon.univ-lyon1.fr/ovincent/prevo
pip install -e prevo
```

Install must be done from a git repository (or from PyPI), because version information is extracted automatically from git tags.


Contents
========

For using the package, three base classes must be subclassed:
- `SensorBase`
- `RecordingBase`
- `RecordBase`

See docstrings for help.


Misc. info
==========

Module requirements
-------------------

### Modules outside of standard library

(installed automatically by pip if necessary)

- tqdm
- tzlocal < 3.0
- oclock >= 1.2.2 (timing tools)
- clivo >= 0.2.0 (command line interface)
- pandas (optional, for csv loading methods)


Python requirements
-------------------

Python : >= 3.6

Author
------

Olivier Vincent

(ovinc.py@gmail.com)
