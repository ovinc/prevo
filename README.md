About
=====

**P**eriodic **RE**cording and **V**isualization of (sensor) **O**bjects

This package provides classes to rapidly create interactive data recording for various applications (e.g. recording of temperature, time-lapses with cameras etc.).

Sensors are read in an asynchronous fashion and can have different time intervals for data reading (or be continuous, i.e. as fast as possible). Synchronous recording is also possible (although not the main goal of this package) by defining a super-sensor object that reads all sensors (and which is itself probed at regular intervals).

Tools for graphical visualizations of data during recording are also provided (updated numerical graphs, oscilloscope-like graphs, etc.)

The package contains various modules:

- `prevo.record`: record sensors periodically, CLI interface, trigger GUI tools from CLI,

- `prevo.control`: control device properties, create pre-defined temporal evolutions of settings for sensors, devices and recording properties,

- `prevo.plot`: plot numerical data in real time (regular plots, oscilloscope-like graphs etc.),

- `prevo.csv`: read / save data with CSV/TSV files

- `prevo.parser`: parse command line arguments to trigger functions or class methods

- `prevo.measurements`: additional tools to format measurements for `Record`-like classes.

- `prevo.misc`: miscellaneous tools, including dummy sensors and devices.

See Jupyter notebooks in `examples/` and docstrings for more help.

Below are also minimal examples showing implementation of periodic recording.


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
- `Record` (children: `NumericalRecord`, `ImageRecord`)

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
            return Gauge.read()
    ```

    Note: context managers also possible (i.e. define `__enter__` and `__exit__` in `Sensor` class) e.g. if sensors have to be opened once at the beginning and closed in the end.


2) **Define the individual recordings**

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

    **NOTE**: the recordings are already usable as is if one does not need fancy functionality.
    For example, one can start a periodic recording of pressure every two seconds with

    ```python
    recording.start(dt=2)
    ```

    And the following methods and attributes are available:
    ```python
    # can be set to True or False to pause/resume recording
    recording.active

    # can be set to True or False to pause/resume saving to file
    # (e.g. to continue live view of data without saving)
    recording.saving

    # Equivalent to playing with .active:
    recording.pause()
    recording.resume()

    recording_P.stop()
    # After a stop(), it is possible to call start() again.

    # To change the time interval between data:
    recording.timer.interval = ...

    # To record data as fast as possible:
    recording.continuous = True
    ```

    **NOTE**: `recording.start()` is non-blocking, so several independent recordings can be started at the same time, and can be changed in real time with the methods/attribute above. However, a convenient interface to manage several recordings simultaneously is provided by the `Record` class, see below.

3) **`Record` interface for managing simultaneous recordings**

    `Record` provides a real-time CLI to manage recordings properties in real time as well as live data visualization.

    ```python
    from prevo.record.numerical import NumericalRecord

    recordings = recording_P, recording_T
    record = NumericalRecord(recordings)
    record.start(dt=2)  # time interval of 2 seconds for both sensors
    ```

Many other options and customizations exist See docstrings for more help and `examples/Record.ipynb` for examples.


# Record images from cameras

See *Record_Images.ipynb*


---
Control device properties
==========================

The `prevo.control` module allows you to control device properties (e.g., temperature of a bath, relative humidity of a RH generator) and create pre-defined temporal patterns (ramps, plateaus, cycles).

### Key classes:
- `Control`: Base class for managing settings (must be subclassed).
- `PeriodicControl`: For controlling devices with periodic updates of their settings.
- `RecordingControl`: For controlling `prevo.Recording` objects.

### Pre-defined temporal patterns:
- `Program`: Custom cycles with arbitrary ramps and plateaus.
- `Stairs`: Cycles with constant plateaus.
- `Teeth`: Plateaus separated by ramps of constant slope.

See Jupyter notebook (`examples/Control.ipynb`) for examples.


Misc. info
==========

Module requirements
-------------------

### Packages outside of standard library

(installed automatically by pip if necessary)

- tqdm
- tzlocal < 3.0
- oclock >= 1.3.2 (timing tools)
- clivo >= 0.4.0 (command line interface)
- gittools >= 0.6.0 (metadata saving tools)
- matplotlib >= 3.1 (due to `cache_frame_data` option in `FuncAnimation`)
- numpy

### Optional packages

- pandas (optional, for csv loading methods)


Python requirements
-------------------

Python : >= 3.6

Author
------

Olivier Vincent

(ovinc.py@gmail.com)
