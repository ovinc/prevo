"""Control classes for making programs/cycles of device/recording settings."""

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
# along with the prevo python package. If not, see <https://www.gnu.org/licenses/>

# Standard library
from datetime import datetime
from threading import Event, Thread
from math import inf
from pathlib import Path

# Other modules
import oclock

# Local imports
from .program import _format_time, _get_and_check_input
from .program import Program, Stairs, Teeth


# ----------------------------------------------------------------------------
# ================================ Base Class ================================
# ----------------------------------------------------------------------------


class Control:
    """Base class to manage temporal evolution of settings.

    Can be used for ramping and programming temporal patterns of pressure,
    temperature, etc. Needs to be subclassed."""
    # [Optional] allowed inputs as parameters for control (e.g. 'p', 'rh', etc.)
    # To be defined in subclasses as an iterable, if necessary
    possible_inputs = None

    def __init__(
        self,
        range_limits,
        round_digits=3,
        print_log=False,
        save_log=True,
        log_file="Control_Log.txt",
        savepath=".",
    ):
        """Initialize the Control object.

        Parameters
        ----------
        range_limits : tuple
            Limits in settable parameter value (min, max).
        round_digits : int, optional
            Number of digits after decimal point to keep/consider when
            reading or applying settings. Default is 3.
        print_log : bool, optional
            If True, print succession of settings in console. Default is False.
        save_log : bool, optional
            If True, save succession of settings sent to device into a .txt
            file. Default is True.
        log_file : str, optional
            Name of .txt file in which to save log of settings.
            Default is 'Control_Log.txt'.
        savepath : str or Path, optional
            Directory in which to save the log file. Default is '.'.
        """
        self.range_limits = range_limits
        self.round_digits = round_digits
        self.print_log = print_log
        self.log_file = Path(savepath) / log_file if save_log else None

    # -------- Private methods for class operation behind the scenes --------

    def _check_range_limits(self, qty, value, message=True):
        """Check if a value is within the allowed range.

        Parameters
        ----------
        qty : str
            Quantity name (e.g., 'p', 'rh').
        value : float
            Value to check.
        message : bool, optional
            If True, print a message if the value is out of range.
            Default is True.

        Returns
        -------
        float
            The value if within limits, otherwise the nearest limit.
        """
        vmin, vmax = self.range_limits
        value_min = vmin if vmin is not None else -inf
        value_max = vmax if vmax is not None else inf

        if value_min <= value <= value_max:
            return value
        value_setpt = value_min if value < value_min else value_max
        if message:
            msg = (
                f"Required {qty}={value} outside of allowed range "
                f"{value_min}-{value_max}. Setting kept at {value_setpt}."
            )
            self._manage_message(msg)
        return value_setpt

    def _print_ramp_info(self, qty, v1, v2, duration):
        """Print information about a new program step in console."""
        msg = f"==> NEW STEP from {qty}={v1} to {qty}={v2} in {duration}"
        self._manage_message(msg)

    def _manage_message(self, msg, force_print=False):
        """Print in console and/or save to log file if options are activated.

        Parameters
        ----------
        msg : str
            Message to print or save.
        force_print : bool, optional
            If True, force printing to console regardless of print_log setting.
            Default is False.
        """
        t_str = datetime.now().isoformat(sep=" ", timespec="seconds")
        line = f"[{t_str}] {msg}\n"

        if self.log_file:
            try:
                with open(self.log_file, "a", encoding="utf8") as file:
                    file.write(line)
            except Exception as e:
                print(f"Error saving to log file: {e}")

        if self.print_log or force_print:
            print(line)

    # ------- Private methods that need to be defined in child classes -------

    def _convert_input(self, **values):
        """Convert input from possible_inputs into parameter usable by device.

        For example, if one inputs p=... for a circulated thermal bath, convert
        the vapor pressure p to the temperature of water generating that bath,
        using the dewpoint at that pressure.

        To be defined in subclasses.
        """
        pass

    # ---------- Public methods that need to be defined in subclasses---------

    def ramp(self, duration, **values):
        """Ramp from val1 to val2 with given duration.

        Must be defined in subclasses! It is better if this method is
        non-blocking, for user experience.

        Parameters
        ----------
        duration : timedelta or str
            Duration of the ramp (e.g., 'h:m:s').
        **values : dict
            Keyword arguments (kwargs) with:
            - key : str, setting quantity (e.g., 'p', 'rh', 'aw', 'T').
            - value : tuple, (start, stop) values of the ramp.
        """
        pass

    def stop(self):
        """Stop control (e.g., cancel ramp, stop timers, etc.).

        For example, cancel timer and cancel blocking behavior, etc.
        """
        pass

    # ------------- Factory methods to generate program objects --------------

    def program(self, repeat=0, **steps):
        """Convenience method to generate a Program object.

        Parameters
        ----------
        repeat : int, optional
            Number of times the cycle is repeated. Default is 0.
        **steps : dict
            Keyword arguments (kwargs) for the Program. See Program class.

        Returns
        -------
        Program
            A new Program instance.

        Examples
        --------
        >>> ctrl = Control(range_limits=(0, 100))
        >>> prog = ctrl.program(durations=[':10:', ':5:', '::'], T=[20, 10, 10, 20])
        """
        return Program(control=self, repeat=repeat, **steps)

    def stairs(self, duration=None, repeat=0, **steps):
        """Convenience method to generate a Stairs program.

        Parameters
        ----------
        duration : str or timedelta, optional
            Duration of every plateau. If None, a list of durations must be
            supplied in `**steps` under the key 'durations'. Default is None.
        repeat : int, optional
            Number of times the cycle is repeated. Default is 0.
        **steps : dict
            Keyword arguments (kwargs) for the Stairs program.
            See Stairs class.

        Returns
        -------
        Stairs
            A new Stairs instance.

        Examples
        --------
        >>> ctrl = Control(range_limits=(0, 100))
        >>> stairs_prog = ctrl.stairs(duration='1::', rh=[90, 70, 50], repeat=1)
        """
        return Stairs(control=self, duration=duration, repeat=repeat, **steps)

    def teeth(
        self,
        slope=None,
        slope_unit="/min",
        plateau_duration=None,
        start="plateau",
        repeat=0,
        **steps,
    ):
        """Convenience method to generate a Teeth program.

        Parameters
        ----------
        slope : float, optional
            Rate of change of the parameter. Default is None.
        slope_unit : str, optional
            Time unit for the slope (e.g., '/s', '/min', '/h').
            Default is '/min'.
        plateau_duration : str or timedelta, optional
            Duration of every plateau. Default is None.
        start : str, optional
            Whether to start with a 'plateau' (default) or a 'ramp'.
        repeat : int, optional
            Number of times the cycle is repeated. Default is 0.
        **steps : dict
            Keyword arguments (kwargs) for the Teeth program.
            See Teeth class.

        Returns
        -------
        Teeth
            A new Teeth instance.

        Examples
        --------
        >>> ctrl = Control(range_limits=(0, 3000))
        >>> teeth_prog = ctrl.teeth(slope=25, slope_unit='/min', p=[3000, 2000])
        """
        return Teeth(
            control=self,
            slope=slope,
            slope_unit=slope_unit,
            plateau_duration=plateau_duration,
            start=start,
            repeat=repeat,
            **steps,
        )


# ----------------------------------------------------------------------------
# ======= Base subclass for control using periodic update of settings ========
# ----------------------------------------------------------------------------


class PeriodicControl(Control):
    """Control using periodic update of device setting, no feedback."""
    def __init__(
        self,
        dt=1,
        range_limits=(None, None),
        round_digits=3,
        print_log=False,
        save_log=True,
        log_file="Control_Log.txt",
        savepath=".",
    ):
        """Initialize the PeriodicControl object.

        Parameters
        ----------
        dt : float, optional
            Time interval (s) between commands. Default is 1.
        range_limits : tuple, optional
            Limits in settable parameter value (min, max). Default is (None, None).
        round_digits : int, optional
            Number of digits after decimal point to keep/consider when
            reading or applying settings. Default is 3.
        print_log : bool, optional
            If True, print succession of settings in console. Default is False.
        save_log : bool, optional
            If True, save succession of settings sent to device into a .txt
            file. Default is True.
        log_file : str, optional
            Name of .txt file in which to save log of settings.
            Default is 'Control_Log.txt'.
        savepath : str or Path, optional
            Directory in which to save the log file. Default is '.'.
        """
        super().__init__(
            range_limits=range_limits,
            round_digits=round_digits,
            print_log=print_log,
            save_log=save_log,
            log_file=log_file,
            savepath=savepath,
        )
        self._dt = dt
        self.timer = oclock.Timer(interval=dt)
        self.stop_event = Event()

    # ============================== Properties ==============================

    @property
    def dt(self):
        """Time interval (s) between commands."""
        return self._dt

    @dt.setter
    def dt(self, value):
        """Set the time interval between commands."""
        self.timer.interval = value
        self._dt = value

    # ================== Methods to be defined in subclasses ==================

    def _convert_input(self, **values):
        """Convert input from possible_inputs into parameter usable by device.

        See Control class.
        """
        pass

    def _apply_setting(self, value):
        """Define how to apply a setting to the device of interest.

        To be defined in subclasses.

        Parameters
        ----------
        value : float
            Setting value to apply.
        """
        pass

    def _read_setting(self):
        """Define how to read the setting on the device of interest.

        To be defined in subclasses.

        Returns
        -------
        float
            Current setting value.
        """
        pass

    def _print_setting(self, value):
        """Define how to print information about current setting in console.

        Optional. To be defined in subclass.

        Parameters
        ----------
        value : float
            Setting value to print.

        Returns
        -------
        str
            Formatted string to print.
        """
        return f"Setting: {value}"

    # =============== Methods deriving from the methods above ================

    def apply_setting(self, value):
        """Apply a setting to the device.

        Parameters
        ----------
        value : float
            Setting value to apply.
        """
        setting = round(value, self.round_digits)
        self._apply_setting(setting)

    def read_setting(self):
        """Read the current setting from the device.

        Returns
        -------
        float
            Current setting value, rounded to `round_digits`.
        """
        setting = self._read_setting()
        return round(setting, self.round_digits)

    def print_setting(self, value):
        """Print the current setting in console.

        Parameters
        ----------
        value : float
            Setting value to print.
        """
        rounded_setting = round(value, self.round_digits)
        msg = self._print_setting(rounded_setting)
        self._manage_message(msg)

    # =========== Misc. methods used for ramping and set settings ============

    def _check_range_and_apply_setting(self, qty, value):
        """Check if setting is valid, then apply to device.

        Parameters
        ----------
        qty : str
            Quantity name (e.g., 'p', 'rh').
        value : float
            Setting value to apply.
        """
        target_setting = self._convert_input(**{qty: value})
        final_setting = self._check_range_limits(qty, target_setting)
        try:
            self.apply_setting(final_setting)
        except Exception as e:
            t_str = datetime.now().isoformat(sep=" ", timespec="seconds")
            print(f"Impossible to apply setting {qty}={value} ({t_str}).\n{e}")
        else:
            self.print_setting(final_setting)

    def _try_read_setting(self):
        """Try to read setting from device.

        Returns
        -------
        float or None
            Current setting value if successful, None otherwise.
        """
        try:
            setting = self.read_setting()
        except Exception:
            t_str = datetime.now().isoformat(sep=" ", timespec="seconds")
            print(f"Impossible to read setting ({t_str}).")
        else:
            return setting

    # ============================ Ramping methods ===========================

    def _apply_setting_and_check_done(self, qty, value, attempts=10):
        """Stay at a given value setting until it is applied (blocking).

        Parameters
        ----------
        qty : str
            Quantity name (e.g., 'p', 'rh').
        value : float
            Target setting value.
        attempts : int, optional
            Maximum number of attempts to apply the setting. Default is 10.
        """
        setting = self._convert_input(**{qty: value})
        target_setting = self._check_range_limits(qty, setting, message=False)

        for _ in range(attempts):
            self._check_range_and_apply_setting(qty, value)
            actual_setting = self._try_read_setting()
            target_round = round(target_setting, self.round_digits)

            if actual_setting == target_round:
                return

            if self.stop_event.is_set():
                return

            self.timer.checkpt()

        msg = (
            f"WARNING -- Could not apply setting: target setting "
            f"{target_round} and actual setting {actual_setting} do not match."
        )
        self._manage_message(msg, force_print=True)

    def _ramp(self, duration, **values):
        """Ramp from val1 to val2 with given duration (blocking).

        Parameters
        ----------
        duration : timedelta or str
            Duration of the ramp (e.g., 'h:m:s').
        **values : dict
            Keyword arguments (kwargs) with:
            - key : str, setting quantity (e.g., 'p', 'rh', 'aw', 'T').
            - value : tuple, (start, stop) values of the ramp.
        """
        self.stop_event.clear()

        qty, (v1, v2) = _get_and_check_input(
            values,
            possible_inputs=self.possible_inputs
        )
        self._print_ramp_info(qty, v1, v2, duration)

        self.timer.reset()
        t_ramp = _format_time(duration)

        if v1 == v2:
            dwell = True
            self._apply_setting_and_check_done(qty, v2)
            self._manage_message(f"Dwelling started ({qty}={v2})")
        else:
            dwell = False

        while self.timer.elapsed_time <= t_ramp:
            if not dwell:
                t = self.timer.elapsed_time
                setting = v1 + t / t_ramp * (v2 - v1) if t_ramp > 0 else v2
                self._check_range_and_apply_setting(qty, setting)

            self.timer.checkpt()

            if self.stop_event.is_set():
                self._manage_message("==X Manual STOP")
                return

        if dwell:
            self._manage_message("Dwelling finished")
        if not dwell:
            self._check_range_and_apply_setting(qty, v2)
            self.timer.checkpt()

    def ramp(self, duration, **values):
        """Ramp from val1 to val2 with given duration (non-blocking).

        Parameters
        ----------
        duration : timedelta or str
            Duration of the ramp (e.g., 'h:m:s').
        **values : dict
            Keyword arguments (kwargs) with:
            - key : str, setting quantity (e.g., 'p', 'rh', 'aw', 'T').
            - value : tuple, (start, stop) values of the ramp.

        Examples
        --------
        >>> Control().ramp(':1:30', rh=(50, 30))
        Generates a ramp going from 50%RH to 30%RH in 1.5 minutes.
        """
        Thread(target=self._ramp, args=(duration,), kwargs=values).start()

    def stop(self):
        """Cancel timers and stop ramp."""
        self.stop_event.set()
        self.timer.stop()


# ----------------------------------------------------------------------------
# =========== Periodic control adapted to the prevo.record module ============
# ----------------------------------------------------------------------------


class RecordingControl(PeriodicControl):
    """Control of prevo Recordings objects."""

    def __init__(
        self,
        recording=None,
        ppty=None,
        dt=1,
        range_limits=(None, None),
        round_digits=3,
        print_log=False,
        save_log=True,
        log_file="Control_Log_Recording.txt",
        savepath=".",
    ):
        """Initialize the RecordingControl object.

        Parameters
        ----------
        recording : Recording or None, optional
            Recording object or subclass. Default is None.
        ppty : ControlledProperty or None, optional
            ControlledProperty object describing the property to control
            within that recording. Default is None.
        dt : float, optional
            Time interval (s) between commands. Default is 1.
        range_limits : tuple, optional
            Safety limits (min, max). Default is (None, None).
        round_digits : int, optional
            Number of digits after decimal point to keep/consider when
            reading or applying settings. Default is 3.
        print_log : bool, optional
            If True, print succession of settings in console. Default is False.
        save_log : bool, optional
            If True, save succession of settings sent to device into a .txt
            file. Default is True.
        log_file : str, optional
            Name of .txt file in which to save log of settings.
            Default is 'Control_Log_Recording.txt'.
        savepath : str or Path, optional
            Directory in which to save the log file. Default is '.'.
        """
        self.ppty = ppty
        self.possible_inputs = self.ppty.commands if ppty else None

        super().__init__(
            dt=dt,
            range_limits=range_limits,
            round_digits=round_digits,
            print_log=print_log,
            save_log=save_log,
            log_file=log_file,
            savepath=savepath,
        )
        self.recording = recording

    def _apply_setting(self, value):
        """Set property value on recording."""
        exec(f"self.recording.{self.ppty.attribute} = {value}")

    def _read_setting(self):
        """Get property value of recording."""
        self._value = None  # exec does not work on local scope
        exec(f"self._value = self.recording.{self.ppty.attribute}")
        return self._value

    def _print_setting(self, value):
        """Print information about current setting in console.

        Parameters
        ----------
        value : float
            Setting value to print.

        Returns
        -------
        str
            Formatted string to print.
        """
        return f"Setting: {self.ppty.attribute}={value}"

    def _convert_input(self, **values):
        """Convert input from possible_inputs into parameter usable by device.

        Parameters
        ----------
        **values : dict
            Keyword arguments (kwargs) with:
            - key : str, one of self.possible_inputs.
            - value : float, target value.

        Returns
        -------
        float
            Converted value.

        Raises
        ------
        ValueError
            If input key does not match self.possible_inputs.
        """
        for command in self.ppty.commands:
            try:
                return values[command]
            except KeyError:
                pass
        input_key, = values.keys()
        raise ValueError(
            f"Input {input_key} does not match {self.ppty.commands}."
        )
