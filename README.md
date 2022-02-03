About
=====

Record data from sensors periodically. This package provide base classes to rapidly create interactive data recording for various applications (e.g. recording of temperature, time-lapses with cameras etc.).

Install
-------

```bash
git clone https://cameleon.univ-lyon1.fr/ovincent/recto
cd recto
pip install -e .
```

Install must be done from a git repository, because version information is extracted automatically from git tags.


Contents
========

For using the package, three base classes must be subclassed:
- `MeasurementBase`
- `SensorRecordingBase`
- `RecordBase`

See docstrings for help.


Misc. info
==========

Module requirements
-------------------

### Modules outside of standard library

(installed automatically by pip if necessary)

- oclock >= 1.2.2

### Homemade modules

(need to be installed manually)

- clyo (command line interface management)


Python requirements
-------------------

Python : >= 3.6

Author
------

Olivier Vincent

(ovinc.py@gmail.com)
