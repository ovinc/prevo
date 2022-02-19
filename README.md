About
=====

**P**eriodic **RE**cording and **V**isualization of sensor **O**bjects

This package provides base classes to rapidly create interactive data recording for various applications (e.g. recording of temperature, time-lapses with cameras etc.). Sensors are read in a asynchronous fashion and can have different time intervals for data reading (or be continuous, i.e. as fast as possible). Tools for graphical visualizations of data during recording are also provided.

Install
-------

```bash
pip install prevo
```


Main Contents
=============

For using the package for asynchronous recording of data, three base classes must/can be subclassed:
- `SensorBase` (requires subclassing)
- `RecordingBase` (requires subclassing)
- `RecordBase` (can be used as is or be subclassed)

A minimal example is provided below, to record pressure and temperature asynchronously, assuming the user already has classes (`Temp`, `Gauge`) to take single-point measurements (it could be functions as well). Let's assume that the pressure measurement also has an `averaging` parameter to smooth the data.

1) **Define the sensors**

    ```python
    from prevo import SensorBase


    class TemperatureSensor(SensorBase):

        name = 'T'

        def _read(self):
            """This method must have no arguments"""
            return Temp.read()


    class PressureSensor(SensorBase):

        name = 'P'

        def __init__(self):
            self.avg = 10  # default value

        def _read(self):
            return Gauge.read(averaging=self.avg)
    ```

1) **Define the individual recordings**

    Note: subclassing can help significantly reduce the code below.

    ```python
    from prevo import RecordingBase


    class RecordingT(RecordingBase):
        """Recording temperature data periodically"""

        def __init__(self):

            super().__init__(Sensor=TemperatureSensor,
                             dt=10)  # by default, record every 10 sec
            self.file = 'Temperature.txt'
            # Below, this allows the user to change time interval in real time
            self.controlled_properties = 'timer.interval',

        def init_file(self, file):
            """Define if you want to write column titles etc.
            (assuming the file is already open)
            """
            pass

        def format_measurement(self, data):
            """Define here how to format data from Sensor._read().
            (e.g., add time information, etc.). Returns a 'measurement'."""
            pass

        def save(self, measurement, file):
            """Define here how to save the measurement above into self.file.
            (assuming the file is already open)
            """
            pass


    class RecordingP(RecordingBase):
        """Recording pressure data periodically"""

        def __init__(self):

            super().__init__(Sensor=PressureSensor,
                             dt=1)  # by default, record every second
            self.file = 'Pressure.txt'
            # Here we can also control the averaging in real time
            self.controlled_properties = 'timer.interval', 'sensor.avg'

        def init_file(self, file):
            """same as above"""
            pass

        def format_measurement(self, data):
            """same as above"""
            pass

        def save(self):
            """same as above"""
            pass
    ```

1) **Define and start asynchronous recording**

    ```python
    from prevo import RecordBase


    class Record(RecordBase):
        """Options exist to add metadata saving or graphing"""
        pass


    # Keys must correspond to sensor names
    recordings = {'T': RecordingT(), 'P': RecordingP()}

    # All properties that can be controlled by CLI
    # (keys must correspond to some controlled_properties)
    properties = {'timer.interval': {'repr': 'Δt (s)',
                                     'commands': ('dt',),
                                     },
                  'sensor.avg': {'repr': 'Averaging',
                                 'commands': ('avg',),
                                 }
                  }

    # Start recording. A CLI will appear; type '?' for help
    Record(recordings=recordings, properties=properties).start()
    ```

Note: context managers also possible (i.e. define `__enter__` and `__exit__` in `Sensor` class) e.g. if sensors have to be opened once at the beginning and closed in the end; this is managed automatically by `RecordBase` if a context manager is defined.

See docstrings for more help.


Additional tools
================

Some elements are also provided to simplify and/or extend the classes above:

- read / save with CSV files (see `prevo.fileio`)
- plot numerical data in real time (see `prevo.plot`)
- live view images from camera-like sensors (see `prevo.view`)

See docstrings for more help.


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
