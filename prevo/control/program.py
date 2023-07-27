"""Programs to make automatic temporal patterns of settings."""

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

# Standard library imports
from datetime import timedelta
from threading import Thread, Event
from pathlib import Path
import json

# Other modules
import oclock
import matplotlib.pyplot as plt


# ================================== Config ==================================


time_factors = {'s': 1, 'min': 60, 'h': 3600}  # used for slope calculations


# ============================= Misc. Functions ==============================

def _get_and_check_input(entry, possible_inputs):
    try:
        (quantity, values), = entry.items()
    except ValueError:
        msg = f"Only one input quantity allowed, not {list(entry.keys())}"
        raise ValueError(msg)

    if possible_inputs is not None and quantity not in possible_inputs:
        msg = f"Settings must only have one of {possible_inputs} as key."
        raise ValueError(msg)
    else:
        return quantity, values


def _format_time(t):
    """format hh:mm:ss str time into timedelta if not already timedelta."""
    try:
        dt = t.total_seconds()
    except AttributeError:
        dt = oclock.parse_time(t).total_seconds()
    finally:
        return dt


def _seconds_to_hms(t):
    """convert seconds to hours, minutes, seconds tuple."""
    h = t // 3600
    ss = t % 3600
    m = ss // 60
    s = ss % 60
    return h, m, s


def _circular_permutation(x):
    return x[1:] + [x[0]]


# ============= Classes to make and manage temperature programs ==============


class Program:
    """Class for managing programmable cycles for control of devices."""

    def __init__(self,
                 control=None,
                 repeat=0,
                 **steps):
        """Initiate temperature cycle(s) program on device.

        Parameters
        ----------
        - control: object of the Control class (or child classes)
                   (can be added later after instantiation)
                   # Note: Program will inherit possible_inputs from the
                           Control object either upon instantiation or
                           when it is defined later.
        - repeat: number of times the cycle is repeated (int); if 0 (default),
                  the program is done only once.
        - steps: kwargs/dict with the following keys:
            * durations: list tt of step durations (timedelta or str 'h:m:s')
            * p=, rh=, aw=, T=: list vv of step target values

        Notes
        -----
        - tt[i] is the duration between steps vv[i] and vv[i + 1].
        - When a cycle is done, the last step loops back to the first step,
            i.e. tt[-1] connects vv[-1] and vv[0]

        Example
        -------
        pp = [3100, 3100, 850]
        tt = ['3::', '1:30:', '::']

        ctrl = Control()  # see Control subclasses for details on instantiation

        # EITHER:
        program = ctrl.program(durations=tt, p=pp, repeat=2)
        # OR:
        program = Program(ctrl, durations=tt, p=pp, repeat=2)

        creates the following program (each dot represents 30 min):

        p (Pa) 3000 ......         ......        ......       .
                          .       |      .      |      .      |
                           .      |       .     |       .     |
               850          .......        ......        ......

        program.plot()   # check everything is ok
        program.run()    # start program
        program.running  # check whether program is running or not
        program.stop()   # stop program
        """
        self.control = control
        self.repeat = repeat
        self.durations = steps.pop('durations')  # list of step durations

        # quantity: 'p', 'rh', 'T', etc., origins: initial values for each ramp
        self.quantity, self.origins = _get_and_check_input(
            steps,
            possible_inputs=self.possible_inputs
        )
        self.targets = _circular_permutation(self.origins)  # loops back to beginning

        self.stop_event = Event()
        self.stop_event.set()

    def __repr__(self):
        msg = f'{self.__class__} with {len(self.durations)} steps of ' \
              f'{self.quantity.upper()} and {self.repeat} repeats.'
        return msg

    def _run(self):
        """Start program in a blocking manner, stop if stop_event is set."""

        if self.control is None:
            msg = 'Control object that the program acts upon not defined yet. '
            msg += 'Please defined a `program.control` attribute of Control type.'
            raise ValueError(msg)

        if self.running:
            msg = 'Program already running. No action taken.'
            self.control._manage_message(msg, force_print=True)
            return

        self.stop_event.clear()

        for n in range(self.repeat + 1):

            msg = f'------ PROGRAM ({self.quantity})--- NEW CYCLE {n + 1} / {self.repeat + 1}'
            self.control._manage_message(msg, force_print=True)

            for v1, v2, duration in zip(self.origins, self.targets, self.durations):
                self.control._ramp(duration, **{self.quantity: (v1, v2)})
                if self.stop_event.is_set():
                    msg = f'------ PROGRAM ({self.quantity})--- STOPPED'
                    self.control._manage_message(msg, force_print=True)
                    return
        else:
            msg = f'------ PROGRAM ({self.quantity})--- FINISHED'
            self.control._manage_message(msg, force_print=True)

    def run(self):
        """Start program in a non-blocking manner."""
        Thread(target=self._run).start()

    def stop(self):
        """Interrupt program."""
        self.stop_event.set()
        self.control.stop()

    def plot(self, time_unit='min'):
        """Same input as cycle(), to visualize the program before running it.

        Note: time_unit can be in 'h', 'min', 's'
        """
        fig, ax = plt.subplots()
        ax.grid()

        t = 0
        for v1, v2, duration in zip(self.origins, self.targets, self.durations):
            dt = _format_time(duration) / time_factors[time_unit]  # h, min, s
            ax.plot([t, t + dt], [v1, v2], '-ok')
            t += dt

        ax.set_xlabel(f'time ({time_unit})')
        ax.set_ylabel(f'{self.quantity}')

        fig.show()

    def copy(self):
        """Return program with same characteristics of current one.

        can be useful to run the same program on different sensors/devices.
        """
        return Program(**self.info)

    def save(self, savepath='.', filename=None):
        """Save program to JSON file. Use load() to regenerate program.

        If filename is None, use default filename.
        """
        filename =  self.default_filename if filename is None else filename
        file = Path(savepath) / filename
        with open(file, 'w', encoding='utf8') as f:
            json.dump(self.info, f, indent=4, ensure_ascii=False)

    @classmethod
    def load(cls, savepath='.', filename=None):
        """Load program from file (filename NEEDS to be supplied here)."""
        if filename is None:
            raise ValueError('Filename needs to be provided')
        file = Path(savepath) / filename
        with open(file, 'r', encoding='utf8') as f:
            info = json.load(f)
        return cls(**info)

    @staticmethod
    def _to_json(file, data):
        """Load python data (dict or list) from json file"""

    @property
    def info(self):
        """Gathers useful info to regenerate the program in a dict.

        Note: self.control not in there because not easily represented by
        a string / number.
        """
        info_dict = {
            'repeat': self.repeat,
            'durations': self.durations,
            self.quantity: self.origins,
        }
        return info_dict

    @property
    def default_filename(self):
        return f'Program_{self.quantity}.json'

    @property
    def cycle_duration(self):
        """Duration of a single cycle of the program."""
        dt = 0
        for duration in self.durations:
            dt += _format_time(duration)  # in seconds
        return timedelta(seconds=dt)

    @property
    def total_duration(self):
        """Duration of a all cycles including repeats."""
        return (self.repeat + 1) * self.cycle_duration

    @property
    def running(self):
        is_running = False if self.stop_event.is_set() else True
        return is_running

    @property
    def control(self):
        return self._control

    @control.setter
    def control(self, value):
        self._control = value
        if self._control is None:
            self.possible_inputs = None
        else:
            self.possible_inputs = self._control.possible_inputs


class Stairs(Program):
    """Special program consisting in plateaus of temperature, of same duration."""

    def __init__(self,
                 control=None,
                 duration=None,
                 repeat=0,
                 **steps):
        """Specific program with a succession of constant setting plateaus.

        Parameters
        ----------
        - control: object of the Control class (or child classes)
                   (can be added later after instantiation)
                   # Note: Program will inherit possible inputs from the
                           Control object either upon instantiation or
                           when it is defined later.
        - duration: (str of type 'hh:mm:ss' or timedelta): if not None, sets
          the duration of every plateau to be the same. If None, a list of
          durations must be supplied within **steps (key 'durations').

        - repeat: number of times the cycle is repeated (int); if 0 (default),
                  the program is done only once.

        - **steps:
            - do not correspond to points in the program, but segments.
            - if duration is None: must contain the key 'durations' with a list
              (tt) of plateau durations as value
            - if duration is not None: 'durations' key is ignored
            - other key must be p=, rh= etc. with the list of plateau setpoints
              (vv) s values.

        Notes
        -----
        - tt[i] is the duration of step i at setting vv[i] (this is different
          from the behavior of Control.program())
        - similarly to Control.program(), the program loops back to the
          beginning, i.e. the last setting sent to the bath is the first one
          in the list.

        Example 1
        ---------
        rh = [90, 70, 50, 30]

        ctrl = Control()  # see Control subclasses for details on instantiation

        # EITHER:
        program = ctrl.stairs(duration='1::', rh=rh, repeat=1)
        # OR:
        program = Stairs(ctrl, duration='1::', rh=rh, repeat=1)

        creates the following program (each dot represents 15 min):

        %RH  90 ....            ....           .
                   |           |   |           |
             70     ....       |    ....       |
                       |       |       |       |
             50         ....   |        ....   |
                           |   |           |   |
             30             ....            ....

        Methods to run, check and stop the program are the same as for the
        Program class:
            program.plot()
            program.run()
            program.running
            program.stop()

        Example 2
        ---------
        pp = [3170, 2338]
        tt = ['1::', '3::']
        Control().stairs(durations=tt, rh=rh, repeat=2)

        Does the following when run (each dot represents 15 minutes):

        p (Pa)  3170 ....            ....            ....           .
                        |           |   |           |   |           |
                        |           |   |           |   |           |
                2338     ............    ............    ............
        """
        self.control = control  # To be able to get possible_inputs automatically
        if duration is None:
            durations = steps.pop('durations')  # list of step durations

        qty, step_plateaus = _get_and_check_input(
            steps,
            possible_inputs=self.possible_inputs
        )
        step_points = sum([[v, v] for v in step_plateaus], [])

        if duration is None:
            step_durations = sum([[dt, '::'] for dt in durations], [])
        else:
            step_durations = [duration, '::'] * len(step_plateaus)

        formatted_steps = {'durations': step_durations, qty: step_points}

        super().__init__(control=control,
                         repeat=repeat,
                         **formatted_steps)


class Teeth(Program):
    """Plateaus of fixed duration separated by ramps of constant slope."""

    def __init__(self,
                 control=None,
                 slope=None,
                 slope_unit='/min',
                 plateau_duration='::',
                 start='plateau',
                 repeat=0,
                 **steps):
        """Plateaus of fixed duration separated by ramps of constant slope.

        Parameters
        ----------
        - control: object of the Control class (or child classes)
                   (can be added later after instantiation)
                   # Note: Program will inherit possible inputs from the
                           Control object either upon instantiation or
                           when it is defined later.
        - slope: rate of change of the parameter specified in **steps. For
          example, if steps contains rh=..., the slope is in %RH / min, except
          if a different time unit is specified in slope_unit.

        - slope_unit: can be '/s', '/min', '/h'

        - plateau_duration : duration of every plateau separating the ramps
          (as as hh:mm:ss str or as a timedelta object)

        - start: can be 'plateau' (default, start with a plateau) or 'ramp'
          (start directly with a ramp).

        - repeat: number of times the cycle is repeated (int); if 0 (default),
                  the program is done only once.

        - **steps:
            - correspond to the values of the plateaus.
            - only key must be p=, rh= etc. with the list of plateau setpoints
              as values.

        Example 1
        ---------
        rh = [90, 70, 90, 50]

        ctrl = Control()  # see Control subclasses for details on instantiation

        # EITHER:
        program = ctrl.teeth(40, '/h', '1::', rh=rh, repeat=1)
        # OR:
        program = Teeth(ctrl, 40, '/h', '1::', rh=rh, repeat=1)

        creates the following program (15 min / dot, ramps at 40%RH / hour):

        %RH  90 ....      ....          ....     ....          .
                    .    .    .        .    .        .        .
             70      ....      .      .      ....     .      .
                                .    .                 .    .
             50                  ....                   ....

        Methods to run, check and stop the program are the same as for the
        Program class:
            program.plot()
            program.run()
            program.running
            program.stop()

        Example 2
        ---------
        pp = [3000, 2000, 3000, 1000]
        Control().teeth(25, '/min', '1:20:', p=pp, start='ramp', repeat=1)

        Does the following when run (20 min / dot, ramps at 25 Pa / min):

        p (Pa)  3000 .      ....          ....     ....          ....
                      .    .    .        .    .        .        .
                2000   ....      .      .      ....     .      .
                                  .    .                 .    .
                1000               ....                   ....
        """
        self.control = control  # To be able to get possible_inputs automatically
        self.slope = slope
        self.slope_unit = slope_unit

        qty, values = _get_and_check_input(
            steps,
            possible_inputs=self.possible_inputs
        )
        next_values = _circular_permutation(values)

        dt_ramps = [self._slope_to_time(vals) for vals in zip(values, next_values)]

        dts = sum([[plateau_duration, dt] for dt in dt_ramps], [])
        pts = sum([[v, v] for v in values], [])

        if start == 'plateau':
            step_durations = dts
            step_points = pts
        elif start == 'ramp':
            step_durations = _circular_permutation(dts)
            step_points = _circular_permutation(pts)
        else:
            msg = f"start parameter must be 'plateau' or 'ramp', not {start}"
            raise ValueError(msg)

        formatted_steps = {'durations': step_durations, qty: step_points}

        super().__init__(control,
                         repeat=repeat,
                         **formatted_steps)

    def _slope_to_time(self, values):
        """values is a tuple (v1, v2) of start and end values."""

        v1, v2 = values

        dvdt = self.slope / time_factors[self.slope_unit.strip('/')]  # in qty / second

        dt = abs((v2 - v1) / dvdt)  # ramp time in seconds
        h, m, s = _seconds_to_hms(dt)

        return timedelta(hours=h, minutes=m, seconds=s)
