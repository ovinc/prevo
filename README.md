About
=====

**P**eriodic **RE**cording and **V**isualization of (sensor) **O**bjects

This package provides classes to rapidly create interactive data recording for various applications (e.g. recording of temperature, time-lapses with cameras etc.).

Sensors are read in an asynchronous fashion and can have different time intervals for data reading (or be continuous, i.e. as fast as possible). Synchronous recording is also possible (although not the main goal of this package) by defining a super-sensor object that reads all sensors (and which is itself probed at regular intervals).

Tools for graphical visualizations of data during recording are also provided (updated numerical graphs, oscilloscope-like graphs, image viewers for cameras etc.)

The package contains various modules:

- `prevo.record`: record sensors periodically, CLI interface, trigger GUI tools from CLI (see `examples/Record.ipynb` for examples)

- `prevo.control`: control device properties, create pre-defined temporal evolutions of settings for sensors, devices and recording properties (see `examples/Control.ipynb` for examples)

- `prevo.plot`: plot numerical data in real time (regular plots, oscilloscope-like graphs, see `examples/LiveGraph.ipynb` for examples)

- `prevo.viewers`: live view of images from camera-like sensors (see `examples/Viewers.ipynb` for examples)

- `prevo.csv`: read / save data with CSV/TSV files

- `prevo.parser`: parse command line arguments to trigger functions or class methods

- `prevo.measurements`: additional tools to format measurements for `Record`-like classes.

- `prevo.misc`: miscellaneous tools, including dummy sensors and devices.

See Jupyter notebooks in `examples/` and docstrings for more help. Below is also an example showing the workflow for defining objects for periodic recording.


Install
=======

```bash
pip install prevo
```


Record sensors periodically
===========================

For using the package for asynchronous recording of data, three base classes must/can be subclassed:
- `SensorBase` (requires subclassing)
- `RecordingBase` (requires subclassing)
- `RecordBase` (can be used as is or be subclassed)

A minimal example is provided below, to record pressure and temperature asynchronously, assuming the user already has classes (`Temp`, `Gauge`) to take single-point measurements (it could be functions as well). See `examples/Record.ipynb` for an actual working example. Let's assume that the pressure measurement also has an `averaging` parameter to smooth the data.

1) **Define the sensors**

    ```python
    from prevo.record import SensorBase, ControlledProperty


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
    from prevo.record import RecordingBase


    class RecordingT(RecordingBase):
        """Recording temperature data periodically"""

        def __init__(self):

            super().__init__(Sensor=TemperatureSensor,
                             dt=10)  # by default, record every 10 sec
            self.file = 'Temperature.txt'

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

    # For the pressure recording, one might want to also control the averaging
    # of the data in real time. In this case, a ControlledProperty object needs
    # to be defined with the attribute of the recording to be controlled,
    # a readable representation of the property, and shorctut commands to
    # interact with the property in the CLI

    averaging = ControlledProperty(attribute='sensor.avg',
                                   readable='Averaging',
                                   commands=('avg',))


    class RecordingP(RecordingBase):
        """Recording pressure data periodically"""

        def __init__(self):
            """By default, the time interval and the active status (on/off)
            of the recording are controlled. Here we can also add control of
            the averaging in real time"""

            super().__init__(Sensor=PressureSensor,
                             ctrl_ppties=(averaging,),
                             dt=1)  # by default, record every second
            self.file = 'Pressure.txt'

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
    from prevo.record import RecordBase


    class Record(RecordBase):
        """Options exist to add metadata saving or graphing"""
        pass


    # Keys must correspond to sensor names
    recordings = {'T': RecordingT(), 'P': RecordingP()}

    # Start recording. A CLI will appear; type '?' for help
    Record(recordings=recordings, properties=properties).start()
    ```

Note: context managers also possible (i.e. define `__enter__` and `__exit__` in `Sensor` class) e.g. if sensors have to be opened once at the beginning and closed in the end; this is managed automatically by `RecordBase` if a context manager is defined.

See docstrings for more help and `Record.ipynb` for examples.


Misc. info
==========

Module requirements
-------------------

### Packages outside of standard library

(installed automatically by pip if necessary)

- tqdm
- tzlocal < 3.0
- oclock >= 1.2.2 (timing tools)
- clivo >= 0.4.0 (command line interface)
- matplotlib >= 3.1 (due to `cache_frame_data` option in `FuncAnimation`)
- numpy

### Optional packages

- pandas (optional, for csv loading methods)
- opencv-python (optional, for specific camera viewers)


Python requirements
-------------------

Python : >= 3.6

Author
------

Olivier Vincent

(ovinc.py@gmail.com)
