About
=====

**P**eriodic **RE**cording and **V**isualization of (sensor) **O**bjects

This package provides classes to rapidly create interactive data recording for various applications (e.g. recording of temperature, time-lapses with cameras etc.).

Sensors are read in an asynchronous fashion and can have different time intervals for data reading (or be continuous, i.e. as fast as possible). Synchronous recording is also possible (although not the main goal of this package) by defining a super-sensor object that reads all sensors (and which is itself probed at regular intervals).

Tools for graphical visualizations of data during recording are also provided (updated numerical graphs, oscilloscope-like graphs, image viewers for cameras etc.)

The package contains various modules:

- `prevo.record`: record sensors periodically, CLI interface, trigger GUI tools from CLI,

- `prevo.control`: control device properties, create pre-defined temporal evolutions of settings for sensors, devices and recording properties,

- `prevo.plot`: plot numerical data in real time (regular plots, oscilloscope-like graphs etc.),

- `prevo.viewers`: live view of images from camera-like sensors,

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
- `SensorBase`
- `RecordingBase` (children: `NumericalRecording`, `ImageRecording`)
- `RecordBase` (children: `NumericalRecord`, `ImageRecord`)

A minimal example is provided below, to record pressure and temperature asynchronously into a CSV file, assuming the user already has classes (`Temp`, `Gauge`) to take single-point measurements (it could be functions as well). See `examples/Record.ipynb` for more detailed examples, including periodic recording of images from several cameras.

1) **Define the sensors**

    ```python
    from prevo.record import SensorBase


    class TemperatureSensor(SensorBase):

        name = 'T'

        def _get_data(self):
            return Temp.read()


    class PressureSensor(SensorBase):

        name = 'P'

        def _get_data(self):
            return Gauge.read(averaging=self.avg)
    ```

1) **Define the individual recordings**

    ```python
    from prevo.record.numerical import NumericalRecording

    # Because timestamp and time uncertaintyare added automatically in data
    # Can be renamed to have different time column titles in csv file.
    time_columns = ('time (unix)', 'dt (s)')

    # Note: NumericalRecording can also be subclassed for simpler use
    # (see examples/Record.ipynb Jupyter notebook)

    recording_P = NumericalRecording(
        Sensor=PressureSensor,
        filename='Pressure.csv',
        column_names=time_columns + ('P (mbar)',),
    )

    recording_T = NumericalRecording(
        Sensor=TemperatureSensor,
        filename='Temperature.csv',
        column_names=time_columns + ('T (°C)',),
    )
    ```

1) **Define and start asynchronous recording of all sensors**

    ```python
    from prevo.record.numerical import NumericalRecord

    recordings = recording_P, recording_T
    record = NumericalRecord(recordings)
    record.start(dt=2)  # time interval of 2 seconds for both sensors
    ```

Note: context managers also possible (i.e. define `__enter__` and `__exit__` in `Sensor` class) e.g. if sensors have to be opened once at the beginning and closed in the end.

Many other options and customizations exist (e.g. live view of data, sensor properties controlled in real time in CLI, etc.). See docstrings for more help and `examples/Record.ipynb` for examples.


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
- gittools >= 0.6.0 (metadata saving tools)
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
