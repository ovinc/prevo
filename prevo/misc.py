"""Misc classes for the prevo package"""

# ----------------------------- License information --------------------------

# This file is part of the prevo python package.
# Copyright (C) 2022 Olivier Vincent

# The prevo package is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# The prevo package is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with the prevo python package.
# If not, see <https://www.gnu.org/licenses/>

import time
from threading import Thread
from random import random
from queue import Queue, Empty
from statistics import mean
from pathlib import Path

import oclock
import numpy as np


# ============================ Misc. queue management ========================


def get_last_from_queue(queue):
    """Function to empty queue to get last element from it.

    Return None if queue is initially empty, return last element otherwise.
    """
    element = None
    while True:
        try:
            element = queue.get(timeout=0)
        except Empty:
            break
    return element


def get_all_from_queue(queue):
    """Function to empty queue to get all elements from it as a list

    Return None if queue is initially empty, return last element otherwise.
    """
    elements = []
    while True:
        try:
            elements.append(queue.get(timeout=0))
        except Empty:
            break
    return elements


# ========================== Misc. file management ===========================


def increment_filename(file):
    """Find an increment on file name, e.g. -1, -2 etc. to create file
    that does not exist.

    Convenient for some uses, e.g. not overwrite metadata file, etc.
    """
    full_name_str = str(file.absolute())
    success = False
    n = 0
    while not success:
        n += 1
        new_stem = f'{file.stem}-{n}'
        new_name = full_name_str.replace(file.stem, new_stem)
        new_file = Path(new_name)
        if not new_file.exists():
            success = True
    return new_file


# =========================== Dataname management ============================


def mode_to_names(mode, possible_names, default_names=None):
    """Determine active names as a function of input mode."""
    if mode is None:
        return [] if default_names is None else default_names
    names = []
    for name in possible_names:
        if name in mode:
            names.append(name)
    return names


# =========== Periodic Threaded systems for e.g. fake sensors etc. ===========


class PeriodicThreadedSystem:
    """Base class managing non-blocking, periodic control of devices."""

    name = None

    def __init__(self, interval=1, precise=False, verbose=False):
        """Parameters:

        - interval: update interval in seconds
        - precise (bool): use the precise option in oclock.Timer
        - verbose: if True, print indications in console when thread
                   is started or stopped
        """
        self.verbose = verbose
        self.timer = oclock.Timer(interval=interval, precise=precise)
        self.thread = None

    # ------------ Methods that need to be defined in subclasses -------------

    def _update(self):
        """Defined in subclass. Defines what needs to be done periodically."""
        pass

    def _on_start(self):
        """Defined in subclass (optional). Anything to do when system is started."""
        pass

    def _on_stop(self):
        """Defined in subclass (optional). Anything to do when system is stopped."""
        pass

    # ------------------------------------------------------------------------

    def _run(self):
        """Run _update() periodically, in a blocking fashion.

        See start() for non-blocking.
        """
        self._on_start()
        self.timer.reset()
        while not self.timer.is_stopped:
            self._update()
            self.timer.checkpt()
        self._on_stop()

    def start(self):
        """Non-blocking version of _run()."""
        self.thread = Thread(target=self._run)
        self.thread.start()
        if self.verbose:
            print(f'Non-blocking run of {self.name} started.')

    def stop(self):
        self.timer.stop()
        self.thread.join()
        self.thread = None
        if self.verbose:
            print(f'Non-blocking run of {self.name} stopped.')

    @property
    def dt(self):
        return self.timer.interval

    @dt.setter
    def dt(self, value):
        self.timer.interval = value


# ============ Classes to put sensor data in queues periodically =============


class PeriodicSensor(PeriodicThreadedSystem):
    """Read sensor periodically and put data in a queue with time info."""

    name = None         # Define in subclasses
    data_types = None   # Define in subclasses

    def __init__(self, interval=1, precise=False, verbose=False):
        """Init PeriodicSensor object

        Parameters
        ----------
        - interval: update interval in seconds
        - precise (bool): use the precise option in oclock.Timer
        - verbose: if True, print indications in console when thread
                   is started or stopped
        """
        super().__init__(interval=interval, precise=precise, verbose=verbose)
        self.queue = Queue()

    def _read(self):
        """Define in subclasses. Must return data ready to put in queue."""
        pass

    def _update(self):
        data = self._read()
        self.queue.put(data)


class PeriodicTimedSensor(PeriodicSensor):
    """Automatically add information about time/duration of sensor reading."""

    def _read_sensor(self):
        """Define in subclass. Raw data from sensor, iterable if several channels."""
        pass

    def _read(self):
        with oclock.measure_time() as data:
            values = self._read_sensor()
        data['values'] = values
        data['name'] = self.name
        return data


# ======================== Dummy Sensors and Devices =========================


class DummyPressureSensor:
    """3 channels: 2 (random) pressures in Pa, 1 in mbar.

    Possibility of averaging when reading values.
    """

    def read(self, avg=1):
        val1, val2, val3 = [], [], []
        for _ in range(int(avg)):
            val1.append(3170 + random())
            val2.append(2338 + 2 * random())
            val3.append(17.06 + 0.5 * random())
        return {'P1 (Pa)': mean(val1),
                'P2 (Pa)': mean(val2),
                'P3 (mbar)': mean(val3)}


class DummyTemperatureSensor:
    """2 channels of (random) temperatures in °C.

    Possibility of averaging when reading values.
    """

    def read(self, avg=1):
        val1, val2 = [], []
        for _ in range(int(avg)):
            val1.append(25 + 0.5 * random())
            val2.append(22.3 + 0.3 * random())
        return {'T1 (°C)': mean(val1),
                'T2 (°C)': mean(val2)}


class DummyElectricalSensor:
    """Random electrical data returned as a numpy array with 3 columns
    corresponding to time and 2 electrical signals."""

    def __init__(self, interval=1, npts=100):
        self.interval = interval
        self.npts = npts

    def read(self):
        t0 = time.time() - self.interval
        time_array = t0 + np.linspace(start=0,
                                      stop=self.interval,
                                      num=self.npts)
        data_array_a = 0.1 * np.random.rand(self.npts) + 0.7
        data_array_b = 0.2 * np.random.rand(self.npts) + 0.3
        return np.vstack((time_array, data_array_a, data_array_b))


class DummyCirculatedBath:
    """Mimics a circulated bath to control temperature with a fluid."""

    def __init__(self, setpt=25):
        self.setpt = setpt
        self.status = 'off'

    def on(self):
        """Turn the bath on."""
        self.status = 'on'
        print('Bath ON')

    def off(self):
        """Turn the bath off."""
        self.status = 'off'
        print('Bath OFF')

    @property
    def tfluid(self):
        """Read fluid temperature in the bath."""
        return self.setpt + 0.1 * (random() - 0.5)


class DummyPump:

    def __init__(self):
        self._running = False
        self._normal_speed = False
        self._rpm = 0

    def on(self):
        self._running = True
        self._rpm = 30
        print('Pump on')

    def off(self):
        self._running = False
        self._rpm = 0
        print('Pump off')

    def speed(self, cmd):
        """Set the speed of the pump, can be 'full' or 'standby'."""
        if cmd == 'full':
            self._normal_speed = True
            self._rpm = 30
            print('Full speed')
        elif cmd == 'standby':
            self._normal_speed = False
            self._rpm = 7
            print('Standby speed')
        else:
            raise ValueError("Commands can only be 'full' or 'standby'")

    @property
    def status(self):

        return {'running': self._running,
                'rpm': self._rpm,
                'normal speed': self._normal_speed}



class DummyLapseCamera(PeriodicSensor):
    """Mock time-lapse camera returning white-noise images periodically"""

    name = 'Mock Lapse Camera'

    def _read(self):
        """Return image in a dict"""
        img = np.random.randint(256, size=(480, 640), dtype='uint8')
        return {'image': img}

    def read(self):
        """Return dict with image and timestamp"""
        with oclock.measure_time() as data:
            data['image'] = self._read()['image']
        return {'image': data['image'],
                'timestamp': data['time (unix)']}
