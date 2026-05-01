"""Programs to make automatic temporal patterns of settings."""

# ----------------------------- License information --------------------------
# This file is part of the prevo python package.
# Copyright (C) 2022 Olivier Vincent
#
# The prevo package is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# The prevo package is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with the prevo python package. If not, see <https://www.gnu.org/licenses/>.

# Standard library imports
from datetime import timedelta
from pathlib import Path
from threading import Event, Thread
import json

# Other modules
import matplotlib.pyplot as plt
import oclock

# ================================== Config ==================================

time_factors = {"s": 1, "min": 60, "h": 3600}  # used for slope calculations

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
    return quantity, values

def _format_time(t):
    """Format hh:mm:ss str time into timedelta if not already timedelta."""
    try:
        return t.total_seconds()
    except AttributeError:
        return oclock.parse_time(t).total_seconds()

def _seconds_to_hms(t):
    """Convert seconds to hours, minutes, seconds tuple."""
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

    def __init__(self, control=None, repeat=0, **steps):
        """Initialize a programmable cycle for device control.

        Parameters
        ----------
        control : Control or None, optional
            Object of the Control class (or child classes).
            Can be added later.
        repeat : int, optional
            Number of times the cycle is repeated. If 0 (default),
            the program runs once.
        **steps : dict
            Keyword arguments (kwargs) with the following keys:
            - 'durations' : list of step durations (timedelta or
              'hh:mm:ss' str)
            - one in the self.possible_inputs (e.g., 'p', 'rh', 'aw',
              'T') : list of step target values

        Examples
        --------
        prog = Program(durations=[':10:', ':5:', '::'], T=[20, 10, 10, 20])

        Notes
        -----
        - `durations[i]` is the duration between `origins[i]` and
          `targets[i]`.
        - The last step loops back to the first, i.e., `durations[-1]`
          connects `origins[-1]` to `origins[0]`.
        """
        self.control = control
        self.repeat = repeat
        self.durations = steps.pop("durations")

        self.quantity, self.origins = _get_and_check_input(
            steps, possible_inputs=self.possible_inputs
        )
        self.targets = _circular_permutation(self.origins)
        self.stop_event = Event()
        self.stop_event.set()

    def __repr__(self):
        return (
            f"{self.__class__.__name__} with {len(self.durations)} steps of "
            f"{self.quantity.upper()} and {self.repeat} repeats."
        )

    def _run(self):
        """Start program in a blocking manner, stop if stop_event is set."""
        if self.control is None:
            msg = (
                "Control object that the program acts upon not defined yet. "
                "Please define a `program.control` attribute of Control type."
            )
            raise ValueError(msg)

        if self.running:
            msg = "Program already running. No action taken."
            self.control._manage_message(msg, force_print=True)
            return

        self.stop_event.clear()

        for n in range(self.repeat + 1):
            msg = (
                f"------ PROGRAM ({self.quantity})--- NEW CYCLE {n + 1} / "
                f"{self.repeat + 1}"
            )
            self.control._manage_message(msg, force_print=True)

            for v1, v2, duration in zip(
                self.origins, self.targets, self.durations
            ):
                self.control._ramp(duration, **{self.quantity: (v1, v2)})
                if self.stop_event.is_set():
                    msg = f"------ PROGRAM ({self.quantity})--- STOPPED"
                    self.control._manage_message(msg, force_print=True)
                    return

        msg = f"------ PROGRAM ({self.quantity})--- FINISHED"
        self.control._manage_message(msg, force_print=True)

    def run(self):
        """Start program in a non-blocking manner."""
        Thread(target=self._run).start()

    def stop(self):
        """Interrupt program."""
        self.stop_event.set()
        self.control.stop()

    def plot(self, time_unit="min"):
        """Visualize the program before running it.

        Parameters
        ----------
        time_unit : str, optional
            Time unit for the x-axis. Can be 'h', 'min', or 's'.
            Default is 'min'.
        """
        fig, ax = plt.subplots()
        ax.grid()

        t = 0
        for v1, v2, duration in zip(
            self.origins, self.targets, self.durations
        ):
            dt = _format_time(duration) / time_factors[time_unit]
            ax.plot([t, t + dt], [v1, v2], "-ok")
            t += dt

        ax.set_xlabel(f"time ({time_unit})")
        ax.set_ylabel(self.quantity)
        fig.show()

    def copy(self):
        """Return a copy of the program with the same characteristics.

        Returns
        -------
        Program
            A new instance with the same attributes as the current program.
        """
        return Program(**self.info)

    def save(self, savepath=".", filename=None):
        """Save the program to a JSON file.

        Parameters
        ----------
        savepath : str or Path, optional
            Directory to save the file. Default is the current directory.
        filename : str or None, optional
            Name of the file. If None, uses the default filename.
        """
        filename = self.default_filename if filename is None else filename
        file = Path(savepath) / filename
        with open(file, "w", encoding="utf8") as f:
            json.dump(self.info, f, indent=4, ensure_ascii=False)

    @classmethod
    def load(cls, savepath=".", filename=None):
        """Load a program from a JSON file.

        Parameters
        ----------
        savepath : str or Path, optional
            Directory where the file is located. Default is current
            directory.
        filename : str
            Name of the file to load.

        Returns
        -------
        Program
            A new program instance loaded from the file.

        Raises
        ------
        ValueError
            If `filename` is not provided (None).
        """
        if filename is None:
            raise ValueError("Filename needs to be provided")
        file = Path(savepath) / filename
        with open(file, "r", encoding="utf8") as f:
            info = json.load(f)
        return cls(**info)

    @staticmethod
    def _to_json(file, data):
        """Load python data (dict or list) from json file."""
        with open(file, "w", encoding="utf8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    @property
    def info(self):
        """Gather useful information to regenerate the program.

        Returns
        -------
        dict
            Dictionary containing the program's repeat count, durations,
            and quantity origins.
        """
        return {
            "repeat": self.repeat,
            "durations": self.durations,
            self.quantity: self.origins,
        }

    @property
    def default_filename(self):
        """Default filename for saving the program.

        Returns
        -------
        str
            Default filename in the format 'Program_{quantity}.json'.
        """
        return f"Program_{self.quantity}.json"

    @property
    def cycle_duration(self):
        """Duration of a single cycle of the program.

        Returns
        -------
        timedelta
            Total duration of one cycle.
        """
        dt = 0
        for duration in self.durations:
            dt += _format_time(duration)
        return timedelta(seconds=dt)

    @property
    def total_duration(self):
        """Total duration of all cycles, including repeats.

        Returns
        -------
        timedelta
            Total duration of the program.
        """
        return (self.repeat + 1) * self.cycle_duration

    @property
    def running(self):
        """Check if the program is currently running.

        Returns
        -------
        bool
            True if the program is running, False otherwise.
        """
        return not self.stop_event.is_set()

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
    """Special program consisting of plateaus of constant settings.

    All plateaus have the same duration.
    """

    def __init__(self, control=None, duration=None, repeat=0, **steps):
        """Initialize a Stairs program with constant setting plateaus.

        Parameters
        ----------
        control : Control or None, optional
            Object of the Control class (or child classes).
        duration : str or timedelta or None, optional
            Duration of every plateau. If None, a list of durations must
            be supplied in `**steps` under the key 'durations'.
        repeat : int, optional
            Number of times the cycle is repeated. Default is 0 (run once).
        **steps : dict
            Keyword arguments (kwargs) with the following keys:
            - If `duration` is None: must contain the key 'durations' with
              a list of plateau durations.
            - Must contain one in self.possible_inputs (e.g., 'p', 'rh',
              etc.) with a list of plateau setpoints.

        Examples
        --------
        prog = Stairs(duration='1::', rh=[90, 70, 50], repeat=1)

        Notes
        -----
        - Each plateau duration `durations[i]` corresponds to the setting
          `vv[i]`.
        - The program loops back to the beginning after the last plateau.
        """
        self.control = control
        if duration is None:
            durations = steps.pop("durations")

        qty, step_plateaus = _get_and_check_input(
            steps,
            possible_inputs=self.possible_inputs
        )
        step_points = sum([[v, v] for v in step_plateaus], [])

        if duration is None:
            step_durations = sum([[dt, "::"] for dt in durations], [])
        else:
            step_durations = [duration, "::"] * len(step_plateaus)

        formatted_steps = {"durations": step_durations, qty: step_points}
        super().__init__(control=control, repeat=repeat, **formatted_steps)


class Teeth(Program):
    """Program with plateaus of fixed duration separated by ramps.

    Ramps have a constant slope.
    """

    def __init__(
        self,
        control=None,
        slope=None,
        slope_unit="/min",
        plateau_duration="::",
        start="plateau",
        repeat=0,
        **steps,
    ):
        """Initialize a Teeth program with plateaus and ramps.

        Parameters
        ----------
        control : Control or None, optional
            Object of the Control class (or child classes).
        slope : float or None, optional
            Rate of change of the parameter specified in `**steps`.
            For example, if `**steps` contains one in self.possible_inputs
            (e.g., 'rh'), the slope is in %RH per time unit.
        slope_unit : str, optional
            Time unit for the slope. Can be '/s', '/min', or '/h'.
            Default is '/min'.
        plateau_duration : str or timedelta, optional
            Duration of every plateau separating the ramps, as 'hh:mm:ss'
            or timedelta. Default is '::' (zero duration).
        start : str, optional
            Whether to start with a 'plateau' (default) or a 'ramp'.
        repeat : int, optional
            Number of times the cycle is repeated. Default is 0 (run once).
        **steps : dict
            Keyword arguments (kwargs) with the following key:
            - Must contain one in self.possible_inputs (e.g., 'p', 'rh',
              etc.) with a list of plateau setpoints.

        Examples
        --------
        prog = Teeth(
            slope=40, slope_unit='/h', plateau_duration='1::',
            rh=[90, 70, 90, 50], repeat=1
        )
        """
        self.control = control
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

        if start == "plateau":
            step_durations = dts
            step_points = pts
        elif start == "ramp":
            step_durations = _circular_permutation(dts)
            step_points = _circular_permutation(pts)
        else:
            msg = f"start parameter must be 'plateau' or 'ramp', not {start}"
            raise ValueError(msg)

        formatted_steps = {"durations": step_durations, qty: step_points}
        super().__init__(control, repeat=repeat, **formatted_steps)

    def _slope_to_time(self, values):
        """Calculate ramp duration from start and end values.

        Parameters
        ----------
        values : tuple
            Tuple of (v1, v2), the start and end values for the ramp.

        Returns
        -------
        timedelta
            Duration of the ramp.
        """
        v1, v2 = values
        dvdt = self.slope / time_factors[self.slope_unit.strip("/")]
        dt = abs((v2 - v1) / dvdt)
        h, m, s = _seconds_to_hms(dt)
        return timedelta(hours=h, minutes=m, seconds=s)
