"""Record several sensors as a function of time with interactive CLI and graph."""

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
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from queue import Queue, Empty
from traceback import print_exc
import os

# Non-standard imports
from tqdm import tqdm
import oclock
from clivo import CommandLineInterface, ControlledProperty, ControlledEvent

# Local imports
from ..control import RecordingControl
from ..misc import mode_to_names

# ================================ MISC Tools ================================


def try_func(function):
    """Decorator to make functions return & print errors if errors occur"""
    def wrapper(*args, **kwargs):

        try:
            function(*args, **kwargs)

        except Exception:
            try:
                nmax, _ = os.get_terminal_size()
            except OSError:
                nmax = 79
            print('\n')
            print('=' * nmax)
            # args is normally the object (self), will print its repr
            print(f'ERROR in {function.__name__}() for {args}')
            print_exc()
            print('=' * nmax)
            print('\n')
            return

    return wrapper


# ----------------------------------------------------------------------------
# =============================== SENSOR CLASS ===============================
# ----------------------------------------------------------------------------


class SensorError(Exception):
    pass


class SensorBase(ABC):
    """Abstract base class for sensor acquisition."""

    # If one wants to control specific properties of the sensor through
    # the CLI in Record or through pre-defined programs, it's possible
    # to specify them here, and they will be automatically added to
    # the controlled_properties attribute of the corresponding Recording
    # NOTE: this needs to be a class attribute and not an instance attribute,
    # because these properties are checked before the Sensor object is
    # instantiated.
    controlled_properties = ()

    def __init__(self):
        # (optional) : specific sensor errors to catch, can be an Exception
        # class or an iterable of exceptions; if not specified in subclass,
        # any exception is caught.
        self.exceptions = Exception

    def __enter__(self):
        """Context manager for sensor (enter). Optional."""
        return self

    def __exit__(self, exc_type, exc_val, traceback):
        """Context manager for sensor (exit). Optional."""
        pass

    @property
    @abstractmethod
    def name(self):
        """Name of sensor, Must be a class attribute."""
        pass

    def _read(self):
        """Read sensor.

        Either this method or _get_data() must be defined in subclasses.
        """
        with oclock.measure_time() as data:
            data['values'] = self._get_data()
        return data

    def _get_data(self):
        """Use this instead of subclassing _read() when you want the time
        of measurement and uncertainty on time to be added automatically.
        (useful when sensor does not return time information)"""
        return ()

    def read(self):
        """Read sensor and throw SensorError if measurement fails."""
        try:
            data = self._read()
        except self.exceptions:
            raise SensorError(f'Impossible to read {self.name} sensor')
        else:
            return data


# ----------------------------------------------------------------------------
# ============================= RECORDING CLASS ==============================
# ----------------------------------------------------------------------------


timer_ppty = ControlledProperty(attribute='interval',
                                readable='Δt (s)',
                                commands=('dt',))

active_ppty = ControlledProperty(attribute='active',
                                 readable='Rec. ON',
                                 commands=('on',))

saving_ppty = ControlledProperty(attribute='saving',
                                 readable='Sav. ON',
                                 commands=('save',))


class RecordingBase(ABC):
    """Base class for recording sensor periodically.

    Can be used as is, or can be fed to the Record class for extra features
    (live graph, metadata saving, etc.)
    """

    # Warnings when queue size goes over some limits
    queue_warning_limits = 1e1, 1e2, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8, 1e9

    def __init__(
        self,
        Sensor,
        path='.',
        dt=1,
        ctrl_ppties=(),
        active=True,
        saving=True,
        continuous=False,
        warnings=False,
        precise=False,
        immediate=True,
        programs=(),
        control_params=None,
        dt_save=1.3,
        dt_check=0.9,
    ):
        """Init Recording object.

        Parameters
        ----------

        - Sensor: subclass of SensorBase.
        - path: directory in which data is recorded.
        - dt: time interval between readings (default 1s).
        - ctrl_ppties: optional iterable of properties (ControlledProperty
                       objects) to control on the recording in addition to
                       default ones (time interval and active on/off)
        - active: if False, do not read data until self.active set to True.
        - saving: if False, do not save data to file until self.saving set to
                  True (note: data acquired during periods with saving=False
                  will not be saved later. This happens e.g. when one just
                  want to plot data without saving it).
        - continuous: if True, take data as fast as possible from sensor.
        - warnings: if True, print warnings of Timer (e.g. loop too short).
        - precise: if True, use precise timer in oclock (see oclock.Timer).
        - immediate: if False, changes in the timer (e.g interval) occur
                     at the next timestep. If True, a new data point is
                     taken immediately.
        - programs: iterable of programs, which are object of the
                    prevo.control.Program class or subclasses.
                    --> optional pre-defined temporal pattern of change of
                    properties of recording (e.g. define some times during
                    which sensor is active or not, or change time interval
                    between data points after some time, etc.)
        - control_params: dict {command: kwargs} containing any kwargs to pass
                          to the program controls (e.g. dt, range_limits, etc.)
                          Note: if None, use default params
                          (see RecordingControl class)
        - dt_save: how often (in seconds) queues are checked and written to files
                   (it is also how often files are open/closed)
        - dt_check: time interval (in seconds) for checking queue sizes.
        """
        self.Sensor = Sensor
        self.name = Sensor.name
        self.timer = oclock.Timer(interval=dt,
                                  name=self.name,
                                  warnings=warnings,
                                  precise=precise)
        self.immediate = immediate

        self.path = Path(path)
        self.path.mkdir(exist_ok=True)

        self.dt_save = dt_save
        self.dt_check = dt_check

        # Queues in which data is put (NEED to be defined before self.saving)
        self.queues = {
            'saving': Queue(),
            'plotting': Queue(),
        }
        # Events that need to be set to put data in each data queue
        self.queue_events = {
            'saving': Event(),
            'plotting': Event(),
        }

        # NOTE: DO NOT change to self.active = active because this can cause
        # problems upon init of the recording when self.sensor is not defined
        # yet, if the active setter uses properties of the sensor (e.g. to
        # turn it on or off)
        self._active = active  # can be set to False to temporarily stop recording from sensor

        # NOTE: Here, KEEP saving instead of _saving because one needs to
        # not only set the status but also activate the queues, etc.
        self.saving = saving  # can be set to False to temporarily not save data to file

        self.continuous = continuous

        # To be defined in subclass.
        # Object that manages how data is written to files.
        # Must have a .file attribute whith is a pathlib.Path object, and
        # .init_file() method to create / init the file when recording starts
        self.file_manager = None

        # Iterable of the recording properties that the program / CLI control.
        # Possibility to add other properties in subclasses
        # (need to be of type ControlledProperty or subclass)
        if self.continuous:
            # If sensor instantiated as continuous (e.g. streaming cameras)
            # we assume that the timer is internally controlled in the sensor
            # so that it does not make sense to control the time interval
            # from the CLI.
            # If one has a sensor when one wants to switch from continuous
            # to not continuous, it's better to instantiate it as not
            # continuous (possibly with on=False) and then switch to
            # continuous and on=True.
            default_ppties = (active_ppty, saving_ppty)
        else:
            default_ppties = (active_ppty, saving_ppty, timer_ppty)
        self.controlled_properties = default_ppties + ctrl_ppties
        self._add_sensor_controlled_properties()
        self._generate_ppty_dict()

        # Optional temporal programs to make controlled properties evolve.
        self._init_programs(programs=programs,
                            control_params=control_params)

        self.threads = []
        self.internal_stop = Event()

    def __repr__(self):
        return f'{self.__class__.__name__} ({self.name})'

    @property
    def active(self):
        """In case a bunch of things (e.g. sensor start/stop) need to be done
        when changing the active property --> subclass this"""
        return self._active

    @active.setter
    def active(self, value):
        self._active = value

    @property
    def saving(self):
        """Temporarily activate/disable saving of data to file"""
        return self._saving

    @saving.setter
    def saving(self, value):
        self._saving = value
        if self._saving:
            self.activate_queue('saving')
        else:
            self.deactivate_queue('saving')

    @property
    def interval(self):
        """Timer interval for the sampling of data from the sensor"""
        return self.timer.interval

    @interval.setter
    def interval(self, value):
        self.timer.set_interval(value, immediate=self.immediate)

    def activate_queue(self, kind):
        """Activate saving of data into chosen queue.

        kind can be 'saving', 'plotting', etc.
        """
        self.queue_events[kind].set()

    def deactivate_queue(self, kind):
        """Dectivate saving of data into chosen queue.

        kind can be 'saving', 'plotting', etc.
        """
        self.queue_events[kind].clear()

    # Private methods --------------------------------------------------------

    def _add_sensor_controlled_properties(self):
        for ppty in self.Sensor.controlled_properties:
            new_attribute = 'sensor.' + ppty.attribute
            new_ppty = ControlledProperty(attribute=new_attribute,
                                          readable=ppty.readable,
                                          commands=ppty.commands)
            self.controlled_properties += (new_ppty,)

    def _generate_ppty_dict(self):
        """Associate property commands to property objects"""
        self.ppty_commands = {}
        for ppty in self.controlled_properties:
            for ppty_cmd in ppty.commands:
                self.ppty_commands[ppty_cmd] = ppty

    def _init_programs(self, programs, control_params):
        self.programs = ()
        for supplied_program in programs:

            # In case same program is supplied to different recordings,
            # because a program object cannot be run several times in parallel.
            program = supplied_program.copy()

            ppty_cmd = program.quantity
            ppty = self.ppty_commands[ppty_cmd]
            if control_params is not None:
                control_kwargs = control_params.get(ppty_cmd, {})
            else:
                control_kwargs = {}
            log_filename = f'Control_Log_{self.name}_[{ppty.readable}].txt'
            program.control = RecordingControl(recording=self,
                                               ppty=ppty,
                                               log_file=log_filename,
                                               savepath=self.path,
                                               **control_kwargs)
            self.programs += (program,)

    def _stop_programs(self):
        for program in self.programs:
            program.stop()

    def _set_property(self, ppty, value):
        """Set property of recording.

        recording: RecordingBase object or subclass on which property is applied
        ppty: ControlledProperty object or subclass.
        value: value of property to apply.
        """
        if ppty not in self.controlled_properties:
            return
        try:
            # avoids having to pass a convert function
            exec(f'self.{ppty.attribute} = {value}')
        except Exception as e:
            print(f"WARNING: Could not set {ppty.readable} for {self.name} to {value}.\n Exception: {e}")

    # Compulsory methods / properties to subclass ----------------------------

    @abstractmethod
    def save(self, measurement, file):
        """Write data of measurement to (already open) file.

        file is the file object yielded by the open() context manager.
        """
        pass

    # Optional methods to subclass -------------------------------------------

    def format_measurement(self, data):
        """How to format the data given by self.Sensor.read().

        Returns a measurement object (e.g. dict, value, custom class etc.)."""
        return data

    def after_measurement(self):
        """Define what to do after measurement has been done and formatted.

        Acts on the recording object but does not return anything.
        (Optional)
        """
        pass

    # General methods and attributes (can be subclassed if necessary) --------

    def print_info_on_failed_reading(self, status):
        """Displays relevant info when reading fails."""
        t_str = datetime.now().isoformat(sep=' ', timespec='seconds')
        if status == 'failed':
            print(f'{self.name} reading failed ({t_str}). Retrying ...')
        elif status == 'resumed':
            print(f'{self.name} reading resumed ({t_str}).')

    # ======================= Data reading from sensor =======================

    def _data_read(self):
        """Reading data when the sensor context manager is active.

        (see self.data_read())
        """
        failed_reading = False  # True temporarily if reading fails

        # Without this here, the first data points are irregularly spaced.
        self.timer.reset()

        while not self.internal_stop.is_set():

            if not self.active:
                if not self.continuous:
                    # to avoid checking too frequently if active or not.
                    self.timer.checkpt()
                continue

            try:
                data = self.sensor.read()

            # Measurement has failed .........................................
            except SensorError:
                print_exc()
                if not failed_reading:  # means it has not failed just before
                    self.print_info_on_failed_reading('failed')
                failed_reading = True

            # Measurement is OK ..............................................
            else:
                if failed_reading:      # means it has failed just before
                    self.print_info_on_failed_reading('resumed')
                    failed_reading = False

                measurement = self.format_measurement(data)
                self.after_measurement()

                for queue, event in zip(self.queues.values(), self.queue_events.values()):
                    if event.is_set():
                        queue.put(measurement)

            # Below, this means that one does not try to acquire data right
            # away after a fail, but one waits for the usual time interval
            finally:
                if not self.continuous:
                    self.timer.checkpt()

    @try_func
    def data_read(self):
        """Read data from sensor and store it in data queues."""

        with self.Sensor() as self.sensor:
            # Initial setting of properties is done here in case one of the
            # properties acts on the sensor object, which is not defined
            # before this point.
            self._apply_ppties()
            self._start_programs()
            self._data_read()

    # ========================== Write data to file ==========================

    def _try_save(self, measurement, file, attempts=3):
        """Try saving data. If not, ignore"""
        error = False
        for attempt in range(attempts):
            try:
                self.save(measurement, file)
            except Exception as e:
                error = True
                print(f'Error saving {measurement} for {self.name}: {e}. '
                      f'Attempt {attempt + 1}/{attempts}')
            else:
                if error:
                    print(f'Success saving {measurement} for {self.name} '
                          f'at attempt {attempt + 1}')
                return
        else:
            print(f'Impossible saving {measurement} for {self.name}; '
                  'will be missing from data')

    @try_func
    def data_save(self):
        """Save data that is stored in a queue by data_read."""

        saving_queue = self.queues['saving']
        saving_timer = oclock.Timer(interval=self.dt_save)

        self.file_manager.init_file()

        while not self.internal_stop.is_set():

            # Open and close file at each cycle to be able to save periodically
            # and for other users/programs to access the data simultaneously
            with open(self.file_manager.file, 'a', encoding='utf8') as file:

                # Get all data from saving queue as long as the current
                # iteration of the timer is still active.
                # - If there is not a lot of data to save, the while loop will
                #   break immediately and go to the saving_timer.checkpt()
                #   waiting phase.
                # - If there is a lot of data to save and/or it takes too long
                #   then the saving_timer interval will be exceeded and the
                #   while loop will exit, thus forcing the saving file to be
                #   closed and re-opened.
                while not saving_timer.interval_exceeded:

                    try:
                        measurement = saving_queue.get(timeout=self.dt_save)
                    except Empty:
                        pass
                    else:
                        if measurement is not None:
                            self._try_save(measurement, file)

                    if self.internal_stop.is_set():  # Move to buffering waitbar
                        break

            # periodic check whether there is data to save
            # This is outside of the with statement in order to close the
            # file as soon as possible when not in use.
            saving_timer.checkpt()

        # Buffering waitbar --------------------------------------------------

        if not saving_queue.qsize():
            return

        print(f'Data buffer saving started for {self.name}')

        # The nested statements below, similarly to above, ensure that
        # self.file_manager.file is opened and closed regularly to avoid
        # loosing too much data if there is an error.

        with tqdm(total=saving_queue.qsize()) as pbar:
            while True:
                try:
                    with open(self.file_manager.file, 'a', encoding='utf8') as file:
                        saving_timer.reset()
                        while not saving_timer.interval_exceeded:
                            measurement = saving_queue.get(timeout=self.dt_save)
                            self._try_save(measurement, file)
                            pbar.update()
                except Empty:
                    break

        print(f'Data buffer saving finished for {self.name}')

    # ========================== Check queue sizes ===========================

    def _check_queue_size(self, queue, q_size_over, q_type):
        """Check that queue does not go beyond specified limits"""
        for qmax in self.queue_warning_limits:

            if queue.qsize() > qmax:
                if not q_size_over[qmax]:
                    print(f'\nWARNING: {q_type} buffer size for {self.name}'
                          f'over {int(qmax)} elements')
                    q_size_over[qmax] = True

            if queue.qsize() <= qmax:
                if q_size_over[qmax]:
                    print(f'\n{q_type} buffer size now below {int(qmax)}'
                          f'for {self.name}')
                    q_size_over[qmax] = False

    @try_func
    def check_queue_sizes(self):
        """Periodically verify that queue sizes are not over limits"""

        # Init queue warnings ------------------------------------------------

        lims = self.queue_warning_limits

        self.q_size_over = {}
        for queue_name in self.queues:
            self.q_size_over[queue_name] = {limit: False for limit in lims}

        # Check periodically -------------------------------------------------

        while not self.internal_stop.is_set():

            for queue_name, queue in self.queues.items():

                # No need to check if queue is not active
                if self.queue_events[queue_name].is_set():

                    self._check_queue_size(
                        queue=queue,
                        q_size_over=self.q_size_over[queue_name],
                        q_type=queue_name,
                    )

            self.internal_stop.wait(self.dt_check)

    # ====================== Start / stop recording ==========================

    def _apply_ppties(self):
        # Note: (_set_property() does not do anything if the property
        # does not exist for the recording of interest)
        for ppty_cmd, value in self.ppty_kwargs.items():
            ppty = self.ppty_commands[ppty_cmd]
            self._set_property(ppty=ppty, value=value)

    def _start_programs(self):
        """Optional pre-defined program for change of recording properties"""
        for program in self.programs:
            program.run()

    def _start_threads(self):
        """Start threads to read, save data etc."""
        for func in self.data_read, self.data_save, self.check_queue_sizes:
            thread = Thread(target=func)
            thread.start()
            # This is to be able to join threads in other programs using
            # the recording (i.e. wait for recording to finish)
            self.threads.append(thread)

    def start(self, **ppty_kwargs):
        """Start recording (nonblocking)"""

        # To be able to restart the recording after calling stop()
        self.internal_stop.clear()
        self.ppty_kwargs = ppty_kwargs

        try:
            self._start_threads()
        # Typically I think there should not be exceptions here because the
        # threads are in try_func decorator, but it's safe to catch
        # anything that might go wrong.
        except (Exception, KeyboardInterrupt):
            print(f'Error for {self.name}. Stopping recording.')
            print_exc()
            self.stop()

    def pause(self):
        self.active = False

    def resume(self):
        self.active = True

    def stop(self):
        self.internal_stop.set()
        self.timer.stop()
        self._stop_programs()

    @property
    def running(self):
        return not self.internal_stop.is_set()


# ----------------------------------------------------------------------------
# =============================== RECORD CLASS ===============================
# ----------------------------------------------------------------------------


class Record:
    """Asynchronous recording of several Recordings objects.

    Recordings objects are of type RecordingBase or subclasses."""

    def __init__(self,
                 recordings,
                 path='.',
                 on_start=(),
                 dt_request=0.7):
        """Init base class for recording data

        Parameters
        ----------
        - recordings: iterable of recording objects (RecordingBase or subclass)
        - path: directory in which data is recorded.
        - on_start: optional iterable of objects with a .start() or .run()
                    method, that need to be started at the same time as
                    Record.start().
                    Note: for now, start() and run() need to be non-blocking.
        - dt_request: time interval (in seconds) for checking user requests
                      (e.g. graph pop-up)
        """
        self.recordings = {rec.name: rec for rec in recordings}
        self.create_events()

        self.path = Path(path)
        self.path.mkdir(exist_ok=True)

        self.on_start = on_start

        self.dt_request = dt_request

        # Any additional functions that need to be run along the other threads
        # (to be defined in subclasses)
        self.additional_threads = []

    def __repr__(self):
        return f'Record object ({self.__class__.__name__})'

    # =========== Optional methods and attributes for subclassing ============

    def save_metadata(self):
        """Save experimental metadata. To be defined in subclass"""
        pass

    def data_plot(self):
        """What to do with data when graph event is triggered"""
        pass

    # ============================= INIT METHODS =============================

    def create_events(self):
        """Create event objects managed by the CLI"""
        self.internal_stop = Event()  # event set to stop recording when needed.
        self.graph_request = Event()  # event set to start plotting the data in real time

        graph_event = ControlledEvent(event=self.graph_request,
                                      readable='graph',
                                      commands=('g', 'graph'))

        stop_event = ControlledEvent(event=self.internal_stop,
                                     readable='stop',
                                     commands=('q', 'Q', 'quit'))

        self.controlled_events = graph_event, stop_event

    def parse_initial_user_commands(self, ppty_kwargs):
        """Check if user input contains specific properties.

        The values to apply for these properties are stored in a dict and
        will be applied to each recording when launched.

        If generic input (e.g. 'dt=10'), set all recordings to that value
        If specific input (e.g. dt_P=10), update recording to that value
        """
        initial_ppty_settings = {name: {} for name in self.recordings}

        global_commands = {}
        specific_commands = {}

        for cmd, value in ppty_kwargs.items():
            try:
                ppty_cmd, name = cmd.split('_', maxsplit=1)  # e.g. dt_P = 10
            except ValueError:                               # e.g. dt=10
                global_commands[cmd] = value
            else:
                specific_commands[name] = ppty_cmd, value

        # Apply first global values to all recordings ------------------------
        for ppty_cmd, value in global_commands.items():
            for name in self.recordings:
                initial_ppty_settings[name][ppty_cmd] = value

        # Then apply commands to specific recordings if specified ------------
        for name, (ppty_cmd, value) in specific_commands.items():
            initial_ppty_settings[name][ppty_cmd] = value

        return initial_ppty_settings

    # =================== START RECORDING (MULTITHREAD) ======================

    def start_supplied_objects(self):
        """Start user-supplied non-blocking objects with a start() or run() method."""
        for obj in self.on_start:
            for method in 'run', 'start':
                try:
                    getattr(obj, method)()
                except AttributeError:
                    pass
                else:
                    break
            else:
                print(f'WARNING - {obj.__class__.__name} does not have a'
                      f'run() or start() method --> not started. ')

    def start(self, **ppty_kwargs):
        """Start recording.

        Parameters
        ----------
        - ppty_kwargs: optional initial setting of properties.
                     (example dt=10 for changing all time intervals to 10
                      or dt_P=60 to change only time interval of recording 'P')
        """
        print(f'Recording started in folder {self.path.resolve()}')

        error_occurred = False
        self.threads = []

        try:
            # Check if user inputs particular initial settings for recordings
            init_ppties = self.parse_initial_user_commands(ppty_kwargs)

            # Start each recording with these initial settings
            for name, recording in self.recordings.items():
                recording.start(**init_ppties[name])

            # This is because in some situations save_metadata can take some
            # time, e.g. because it waits for sensors to be fully instantiated
            # to get info from them.
            metadata_thread = Thread(target=self.save_metadata)
            metadata_thread.start()
            self.threads.append(metadata_thread)

            # Add any other user-supplied functions for threading
            for func in self.additional_threads:
                thread = Thread(target=func)
                thread.start()
                self.threads.append(thread)

            # Add CLI. This one is a bit particular because it is blocking
            # with input() and has to be manually stopped. ----------------
            self.cli_thread = Thread(target=self.cli)
            self.cli_thread.start()

            # Start any other user-supplied objects (need to be nonblocking)
            self.start_supplied_objects()

            # real time graph (triggered by CLI, runs in main thread due to
            # GUI backend problems if not) --------------------------------
            self.data_graph()

        except Exception:
            error_occurred = True
            print('\nERROR during asynchronous Record. \n Stopping ... \n')
            print_exc()

        except KeyboardInterrupt:
            error_occurred = True
            print('\nManual interrupt by Ctrl-C event.\n Stopping ...\n')

        finally:

            self.stop()
            for recording in self.recordings.values():
                recording.stop()
                for thread in recording.threads:
                    thread.join()

            for thread in self.threads:
                thread.join()

            for obj in self.on_start:
                obj.stop()

            try:
                self.cli_thread
            except AttributeError:  # CLI thread not defined
                pass
            else:
                if error_occurred:
                    print('\nIMPORTANT: CLI still running. Input "q" to stop.\n')
                self.cli_thread.join()

            print('Recording Stopped')

    def stop(self):
        self.internal_stop.set()

    # =============================== Threads ================================

    @try_func
    def cli(self):
        if self.recordings:  # if no recordings provided, no need to record.
            command_input = CommandLineInterface(
                self.recordings,
                self.controlled_events,
            )
            command_input.run()
        else:
            self.internal_stop.set()
            raise ValueError('No recordings provided. Stopping ...')

    @try_func
    def data_graph(self):
        """Manage requests of real-time plotting of data during recording."""

        while not self.internal_stop.is_set():

            if self.graph_request.is_set():

                for recording in self.recordings.values():
                    recording.activate_queue('plotting')

                self.data_plot()  # Blocking (defined in subclasses)

                self.graph_request.clear()
                for recording in self.recordings.values():
                    recording.deactivate_queue('plotting')

            self.internal_stop.wait(self.dt_request)

    # ============================ Factory method ============================

    @classmethod
    def create(cls,
               mode=None,
               sensors=(),
               default_names=None,
               recording_types=None,
               recording_kwargs=None,
               programs=None,
               control_params=None,
               path='.',
               **kwargs):
        """Factory method to generate a Record object from sensor names etc.

        Parameters
        ----------
        - mode (default: all sensors): sensor names in any order (e.g. 'PTB1')
               and potentially with separators (e.g. 'P-T-B1')
        - sensors: iterable of all sensor classes [Sensor1, Sensor2, etc.]
        - default_names (optional): default sensor names to record if mode
                                    is not supplied (left to None)
        - recording_types: dict {sensor name: Recording} indicating what class
                           of recording (RecordingBase class or subclass)
                           needs to be instantiated for each sensor.
        - recording_kwargs: dict {sensor name: kwargs}
        - programs: dict {mode: programs} with mode same as the mode argument above
                    (describing all sensor recordings that are concerned by the
                    supplied programs), and programs an iterable of objects from
                    the prevo.control.Program class or subclass.
        - control_params: dict {command: kwargs} containing any kwargs to pass
                          to the program controls (e.g. dt, range_limits, etc.)
                          Note: if None, use default params
                          (see RecordingControl class)
        - path: directory in which data is recorded.
        - **kwargs is any keyword arguments to pass to Record __init__
          (only possible options: on_start and dt_request)
        """
        all_sensors = {Sensor.name: Sensor for Sensor in sensors}
        name_info = {'possible_names': all_sensors,
                     'default_names': default_names}
        names = mode_to_names(mode=mode, **name_info)

        programs = {} if programs is None else programs

        all_programs = {name: () for name in names}
        for pgm_mode, programs in programs.items():
            pgm_names = mode_to_names(mode=pgm_mode, **name_info)
            for name in pgm_names:
                all_programs[name] += programs

        recordings = []
        for name in names:
            Recording = recording_types[name]
            recording = Recording(Sensor=all_sensors[name],
                                  path=path,
                                  programs=all_programs[name],
                                  control_params=control_params,
                                  **recording_kwargs[name])
            recordings.append(recording)

        return cls(recordings=recordings, path=path, **kwargs)
