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
from queue import Queue

import oclock
import numpy as np

# =========================== Dataname management ============================


class NamesMgmt:
    """Manage things related to sensor names from configuration info."""

    def __init__(self, config):
        """Config is a dict that must contain the keys:

        - 'sensors'
        - 'default names'
        """
        self.config = config

    def mode_to_names(self, mode):
        """Determine active names as a function of input mode."""
        if mode is None:
            return self.config['default names']
        names = []
        for name in self.config['sensors']:
            if name in mode:
                names.append(name)
        return names


# =========== Periodic Threaded systems for e.g. fake sensors etc. ===========


class PeriodicThreadedSystem:
    """Base class managing non-blocking, periodic control of devices."""

    name = None

    def __init__(self, interval=1, precise=False):
        """Parameters:

        - interval: update interval in seconds
        - precise (bool): use the precise option in oclock.Timer
        """
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

    def stop(self):
        self.timer.stop()
        self.thread.join()
        print(f'Non-blocking run of {self.name} stopped.')
        self.thread = None

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

    def __init__(self, interval=1):
        """Parameters:
        - interval: how often to read the sensor (in seconds)
        """
        super().__init__(interval=interval, precise=False)
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


# ============================== Dummy Sensors ===============================


class DummyPressureSensor:
    """3 channels: 2 (random) pressures in Pa, 1 in mbar"""

    def read(self):
        val1 = 3170 + random()
        val2 = 2338 + 2 * random()
        val3 = 17.06 + 0.5 * random()
        return {'P1 (Pa)': val1,
                'P2 (Pa)': val2,
                'P3 (mbar)': val3}


class DummyTemperatureSensor:
    """2 channels of (random) temperatures in ??C"""

    def read(self):
        val1 = 25 + 0.5 * random()
        val2 = 22.3 + 0.3 * random()
        return {'T1 (??C)': val1,
                'T2 (??C)': val2}


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
