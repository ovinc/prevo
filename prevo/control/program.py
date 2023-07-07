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

# Other modules
import matplotlib.pyplot as plt


# ================================== Config ==================================


time_factors = {'/s': 1, '/min': 60, '/h': 3600}  # used for slope calculations


# ============================= Misc. Functions ==============================


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

    def __init__(self, control, repeat=1, **steps):
        """Initiate temperature cycle(s) program on device.

        Parameters
        ----------
        - control: object of the Control class (or child classes)
        - repeat: number of times the cycle is repeated (int)
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
        program = ctrl.program(durations=tt, p=pp, repeat=3)
        # OR:
        program = Program(ctrl, durations=tt, p=pp, repeat=3)

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
        self.durations = steps.pop('durations')  # list of step durations
        self.quantity = control._check_input(steps)  # 'p', 'rh', 'T', etc.

        step_list = steps[self.quantity]
        self.origins = step_list
        self.targets = _circular_permutation(step_list)  # loops back to beginning

        self.steps = list(zip(self.origins, self.targets, self.durations))
        self.control = control
        self.repeat = repeat

        self.stop_event = Event()
        self.stop_event.set()

    def __repr__(self):
        ns = len(self.durations)
        s = f'{self.__class__} with {ns} steps of {self.quantity.upper()} ' \
            f'and {self.repeat} repeats.'
        return s

    def _run(self):
        """Start program in a blocking manner, stop if stop_event is set."""

        if self.running:
            print('Program already running. No action taken.')
            return

        self.stop_event.clear()

        for n in range(self.repeat):

            msg = f'------ PROGRAM --- NEW CYCLE {n+1} / {self.repeat}\n'
            print(msg)
            self.control._manage_message(msg)

            for v1, v2, duration in self.steps:
                self.control._ramp(duration, **{self.quantity: (v1, v2)})
                if self.stop_event.is_set():
                    print('------ PROGRAM --- STOPPED')
                    return
        else:
            msg = '------ PROGRAM --- FINISHED'
            print(msg)
            self.control._manage_message(msg)

    def run(self):
        """Start program in a non-blocking manner."""
        Thread(target=self._run).start()

    def stop(self):
        """Interrupt program."""
        self.stop_event.set()
        self.control.stop()

    def plot(self):
        """Same input as cycle(), to visualize the program before running it."""
        fig, ax = plt.subplots()
        ax.grid()

        t = 0
        for v1, v2, duration in self.steps:
            dt = self.control._format_time(duration) / 3600  # time in hours
            ax.plot([t, t + dt], [v1, v2], '-ok')
            t += dt

        ax.set_xlabel('time (hours)')
        ax.set_ylabel(self.quantity.upper())

        fig.show()

    @property
    def cycle_duration(self):
        """Duration of a single cycle (1 repeat) of the program."""
        dt = 0
        for duration in self.durations:
            dt += self.control._format_time(duration)  # in seconds
        return timedelta(seconds=dt)

    @property
    def total_duration(self):
        """Duration of a all cycles including repeats."""
        return self.repeat * self.cycle_duration

    @property
    def running(self):
        is_running = False if self.stop_event.is_set() else True
        return is_running


class Stairs(Program):
    """Special program consisting in plateaus of temperature, of same duration."""

    def __init__(self, control, duration=None, repeat=1, **steps):
        """Specific program with a succession of constant setting plateaus.

        Parameters
        ----------
        - control: object of the Control class (or child classes)
        - duration: (str of type 'hh:mm:ss' or timedelta): if not None, sets
          the duration of every plateau to be the same. If None, a list of
          durations must be supplied within **steps (key 'durations').

        - repeat: number of times the cycle is repeated (int)

        - **steps:
            - do not correspond to points in the program, but segments.
            - if duration is None: must contain the key 'durations' with a list
              (tt) of plateau durations as value
            - if duration is not None: 'durations' key is ignored
            - other key myust be p=, rh= etc. with the list of plateau setpoints
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
        program = ctrl.stairs(duration='1::', rh=rh, repeat=2)
        # OR:
        program = Stairs(ctrl, duration='1::', rh=rh, repeat=2)

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
        Control().stairs(durations=tt, rh=rh, repeat=3)

        Does the following when run (each dot represents 15 minutes):

        p (Pa)  3170 ....            ....            ....           .
                        |           |   |           |   |           |
                        |           |   |           |   |           |
                2338     ............    ............    ............
        """
        if duration is None:
            durations = steps.pop('durations')  # list of step durations

        qty = control._check_input(steps)    # 'p', 'rh', 'T', etc.
        step_plateaus = steps[qty]

        step_points = sum([[v, v] for v in step_plateaus], [])

        if duration is None:
            step_durations = sum([[dt, '::'] for dt in durations], [])
        else:
            step_durations = [duration, '::'] * len(step_plateaus)

        formatted_steps = {'durations': step_durations, qty: step_points}

        super().__init__(control, repeat=repeat, **formatted_steps)


class Teeth(Program):
    """Plateaus of fixed duration separated by ramps of constant slope."""

    def __init__(self, control, slope=None, slope_unit='/min',
                 plateau_duration=None, start='plateau', repeat=1, **steps):
        """Plateaus of fixed duration separated by ramps of constant slope.

        Parameters
        ----------
        - control: object of the Control class (or child classes)
        - slope: rate of change of the parameter specified in **steps. For
          example, if steps contains rh=..., the slope is in %RH / min, except
          if a different time unit is specified in slope_unit.

        - slope_unit: can be '/s', '/min', '/h'

        - plateau_duration : duration of every plateau separating the ramps
          (as as hh:mm:ss str or as a timedelta object)

        - start: can be 'plateau' (default, start with a plateau) or 'ramp'
          (start directly with a ramp).

        - **steps:
            - correspond to the values of the plateaus.
            - only key myust be p=, rh= etc. with the list of plateau setpoints
              as values.

        Example 1
        ---------
        rh = [90, 70, 90, 50]

        ctrl = Control()  # see Control subclasses for details on instantiation

        # EITHER:
        program = ctrl.teeth(40, '/h', '1::', rh=rh, repeat=2)
        # OR:
        program = Teeth(ctrl, 40, '/h', '1::', rh=rh, repeat=2)

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
        Control().teeth(25, '/min', '1:20:', p=pp, start='ramp', repeat=2)

        Does the following when run (20 min / dot, ramps at 25 Pa / min):

        p (Pa)  3000 .      ....          ....     ....          ....
                      .    .    .        .    .        .        .
                2000   ....      .      .      ....     .      .
                                  .    .                 .    .
                1000               ....                   ....
        """
        self.slope = slope
        self.slope_unit = slope_unit

        qty = control._check_input(steps)  # 'p', 'rh', 'T', etc.

        values = steps[qty]
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

        super().__init__(control, repeat=repeat, **formatted_steps)

    def _slope_to_time(self, values):
        """values is a tuple (v1, v2) of start and end values."""

        v1, v2 = values

        dvdt = self.slope / time_factors[self.slope_unit]  # in qty / second

        dt = abs((v2 - v1) / dvdt)  # ramp time in seconds
        h, m, s = _seconds_to_hms(dt)

        return timedelta(hours=h, minutes=m, seconds=s)
