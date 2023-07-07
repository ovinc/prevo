"""Control classes for making programs/cycles of device/recording settings."""

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


# Standard library
from datetime import datetime
from threading import Thread, Event
from math import inf
from pathlib import Path

# Other modules
import oclock

# Local imports
from .program import Program, Stairs, Teeth


# ----------------------------------------------------------------------------
# ================================ Base Class ================================
# ----------------------------------------------------------------------------


class Control:
    """Base class to manage temporal evolution of settings.

    Can be used for ramping and programming temporal patterns of pressure,
    temperature, etc.

    Needs to be subclassed.
    """
    # Allowed inputs as parameters for control (e.g., vapor pressure, %RH etc)
    # To be defined in subclass (tuple of str)
    possible_inputs = None

    def __init__(self,
                 range_limits,
                 round_digits=3,
                 print_log=False,
                 save_log=True,
                 log_file='Control_Log.txt',
                 savepath='.'):
        """Init control object, with parameters:

        - range_limits: limits in settable parameter value (tuple min, max)
        - round_digits: number of digits after decimal point to keep/consider
                        when reading or applying settings
        - dt: time interval (s) between commands
        - range_limits: limits in settable parameter value (tuple min, max).
        - round_digits: number of digits after decimal point to keep/consider
                        when reading or applying settings
        - print_log: if True (default), print succession of settings in console
        - save_log: if True (default), save succession of settings sent to
                    device into a .txt file.
        - log_file: name of .txt file in which to save log of settings.
                    (default: Control_Log.txt)
        - savepath: directory in which to save the log file
        """
        self.range_limits = range_limits
        self.round_digits = round_digits
        self.print_log = print_log
        self.log_file = Path(savepath) / log_file if save_log else None

    # -------- Private methods for class operation behind the scenes ---------

    @staticmethod
    def _format_time(t):
        """format hh:mm:ss str time into timedelta if not already timedelta."""
        try:
            dt = t.total_seconds()
        except AttributeError:
            dt = oclock.parse_time(t).total_seconds()
        finally:
            return dt

    def _check_input(self, values):
        """Check that input is OK and return the quantity used (e.g. 'rh')."""
        try:
            qty, = tuple(values.keys())
        except ValueError:
            failed = True
            qty = None
        else:
            failed = False

        if failed or qty not in self.possible_inputs:
            msg = f"Settings must only have one of {self.possible_inputs} as key."
            raise ValueError(msg)
        else:
            return qty

    def _check_range_limits(self, qty, value):
        """Return value if within limits, else return higher or lower limit."""
        vmin, vmax = self.range_limits
        value_min = vmin if vmin is not None else -inf
        value_max = vmax if vmax is not None else inf

        if value_min <= value <= value_max:
            return value
        else:
            if value < value_min:
                value_setpt = value_min
            else:
                value_setpt = value_max
            msg = (f'Required {qty}={value} outside of allowed'
                   f'range {value_min}-{value_max}.\n'
                   f'Setting kept at {value_setpt}.')
            print(msg)
            return value_setpt

    def _print_ramp_info(self, qty, v1, v2, duration):
        """Print information about new program step in console."""
        msg = f'==> NEW STEP from {qty}={v1} to {qty}={v2} in {duration}\n'
        self._manage_message(msg)

    def _manage_message(self, msg):
        """Print in console and/or save to log file if options are activated"""

        t_str = datetime.now().isoformat(sep=' ', timespec='seconds')
        line = f'[{t_str}] {msg}'

        if self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf8') as file:
                    file.write(line)
            except Exception as e:
                print(f'Error saving to log file: {e}')

        if self.print_log:
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

        =================== Must be defined in subclasses! ===================
        It is better if this method is non blocking, for user experience.

        Parameters
        ----------
        - duration: timedelta or 'h:m:s' str
        - values: dict (kwargs) with
            - key(word): setting quantity (e.g., p=, rh=, aw=, T=)
            - value: tuple (start, stop): start and end values of ramp.

        Example
        -------
        >>> Control().ramp(':1:30', rh=(50, 30))
        generates a ramp going from 50%RH to 30%RH (at 25°C) in 1.5 hours.
        """
        pass

    def stop(self):
        """Stop control (e.g. cancel ramp, stop timers, etc.).

        For example, cancel timer and cancel blocking behavior, etc.
        """
        pass

    # ------------- Factory methods to generate program objects --------------

    def program(self, repeat=1, **steps):
        """Convenience method to generate a program. see Program Class."""
        return Program(self, repeat, **steps)

    def stairs(self, duration=None, repeat=1, **steps):
        """Convenience method to generate a stairs program. see Stairs Class."""
        return Stairs(self, duration, repeat, **steps)

    def teeth(self, slope=None, slope_unit='/min', plateau_duration=None,
              start='plateau', repeat=1, **steps):
        """Convenience method to generate a teeth program. see Teeth Class."""
        return Teeth(self, slope, slope_unit, plateau_duration, start, repeat, **steps)


# ----------------------------------------------------------------------------
# ======== Base subclass for control using periodic update of settings ========
# ----------------------------------------------------------------------------


class PeriodicControl(Control):
    """Control using periodic update of device setting, no feedback"""

    def __init__(self,
                 dt=1,
                 range_limits=(None, None),
                 round_digits=3,
                 print_log=False,
                 save_log=True,
                 log_file='Control_Log.txt',
                 savepath='.'):
        """Create PeriodicControl object, with parameters:

        - dt: time interval (s) between commands
        - range_limits: limits in settable parameter value (tuple min, max).
        - round_digits: number of digits after decimal point to keep/consider
                        when reading or applying settings
        - print_log: if True (default), print succession of settings in console
        - save_log: if True (default), save succession of settings sent to
                    device into a .txt file
        - log_file: name of .txt file in which to save log of settings.
                    (default: Control_Log.txt)
        - savepath: directory in which to save the log file
        """
        Control.__init__(self,
                         range_limits=range_limits,
                         round_digits=round_digits,
                         print_log=print_log,
                         save_log=save_log,
                         log_file=log_file,
                         savepath=savepath)
        self._dt = dt
        self.timer = oclock.Timer(interval=dt)
        self.stop_event = Event()

    # ============================== Properties ==============================

    @property
    def dt(self):
        return self._dt

    @dt.setter
    def dt(self, value):
        self.timer.interval = value
        self._dt = value

    # ================== Methods to be defined in subclasses =================

    def _convert_input(self, **values):
        """Convert input from possible_inputs into parameter usable by device.

        (see Control class)
        """
        pass

    def _apply_setting(self, value):
        """"Define how to apply a setting to the device of interest.

        Defined in subclasses.
        e.g. device.setpt = value
        """
        pass

    def _read_setting(self):
        """"Define how to read the setting on the device of interest.

        (e.g. to check that setting has been really applied)
        Defined in subclasses.
        e.g. return device.setpt
        """
        pass

    def _print_setting(self, value):
        """How to print information about current setting in console.

        (OPTIONAL)
        Define in subclass.
        """
        pass

    # =============== Methods deriving from the methods above ================

    def apply_setting(self, value):
        setting = round(value, self.round_digits)
        self._apply_setting(setting)

    def read_setting(self):
        setting = self._read_setting()
        return round(setting, self.round_digits)

    def print_setting(self, value):
        msg = self._print_setting(value)
        self._manage_message(msg)

    # =========== MISC. methods used for ramping and set settings ============

    def _check_range_and_apply_setting(self, qty, value):
        """Check setting ok, rescale it if not, then apply to device."""
        target_setting = self._convert_input(**{qty: value})
        final_setting = self._check_range_limits(qty, target_setting)
        try:
            self.apply_setting(final_setting)
        except Exception:
            t_str = datetime.now().isoformat(sep=' ', timespec='seconds')
            print(f'Impossible to apply setting {qty}={value} ({t_str}).')
        else:
            self.print_setting(final_setting)

    def _try_read_setting(self):
        """Try to read setting from device."""
        try:
            setting = self.read_setting()
        except Exception:
            t_str = datetime.now().isoformat(sep=' ', timespec='seconds')
            print(f'Impossible to read setting ({t_str}).')
        else:
            return setting

    # ============================ Ramping methods ===========================

    def _apply_setting_and_check_done(self, qty, value, duration):
        """Stay at a given value setting for the quantity of interest (blocking)

        Not a public method; is used by _ramp() and ramp().
        """
        target_setting = self._convert_input(**{qty: value})
        t_ramp = self._format_time(duration)

        setting_success = False

        while not setting_success and self.timer.elapsed_time <= t_ramp:

            self._check_range_and_apply_setting(qty, value)
            actual_setting = self._try_read_setting()
            target_round = round(target_setting, self.round_digits)

            if actual_setting == target_round:
                setting_success = True

            else:

                # This is to be able to stop the program even when the system
                # is continuously trying to apply a setting.
                if self.stop_event.is_set():
                    return

                print(f'Target setting {target_round} and actual setting '
                      f'{actual_setting} do not match.')

                self.timer.checkpt()

    def _ramp(self, duration, **values):
        """Ramp from val1 to val2 with given duration.

        This method is BLOCKING. See ramp() for the nonblocking version and
        for parameter info and examples.
        """
        self.stop_event.clear()

        qty = self._check_input(values)  # 'p' or 'T', etc.
        v1, v2 = values[qty]

        self._print_ramp_info(qty, v1, v2, duration)

        self.timer.reset()
        t_ramp = self._format_time(duration)

        if v1 == v2:
            # If dwelling, no need to update the setting regularly.
            # Just apply it once, but make sure it has really been applied.
            dwell = True
            self._apply_setting_and_check_done(qty, v2, duration)
            self._manage_message(f'Dwelling started ({qty}={v2})\n')
        else:
            dwell = False

        while self.timer.elapsed_time <= t_ramp:

            if not dwell:
                t = self.timer.elapsed_time
                setting = v1 + t / t_ramp * (v2 - v1) if t_ramp > 0 else v2

                self._check_range_and_apply_setting(qty, setting)

            self.timer.checkpt()

            if self.stop_event.is_set():
                self._manage_message('==X Manual STOP\n')
                return

        else:
            if dwell:
                self._manage_message('Dwelling finished\n')
            if not dwell:
                self._check_range_and_apply_setting(qty, v2)

    def ramp(self, duration, **values):
        """Ramp from val1 to val2 with given duration.

        =================== Must be defined in subclasses! ===================
        It is better if this method is non blocking, for user experience.

        Parameters
        ----------
        - duration: timedelta or 'h:m:s' str
        - values: dict (kwargs) with
            - key(word): setting quantity (e.g., p=, rh=, aw=, T=)
            - value: tuple (start, stop): start and end values of ramp.

        Example
        -------
        >>> Control().ramp(':1:30', rh=(50, 30))
        generates a ramp going from 50%RH to 30%RH (at 25°C) in 1.5 hours.
        """
        Thread(target=self._ramp, args=(duration,), kwargs=values).start()

    def stop(self):
        """Cancel timers and stop ramp."""
        self.stop_event.set()
        self.timer.stop()
