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


import oclock
from threading import Thread


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

    def __init__(self, interval, precise):
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
