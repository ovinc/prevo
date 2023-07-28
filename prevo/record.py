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
from .control import RecordingControl
from .misc import mode_to_names


# ================================ MISC Tools ================================


def try_thread(function):
    """Decorator to make threaded functions return & print errors if errors occur"""
    def wrapper(*args, **kwargs):
        try:
            function(*args, **kwargs)
        except Exception:
            try:
                name = kwargs['name']
            except KeyError:
                sensor_info = ''
            else:
                sensor_info = f' for sensor "{name}"'
            try:
                nmax, _ = os.get_terminal_size()
            except OSError:
                nmax = 80
            print('\n')
            print('=' * nmax)
            print(f'ERROR in {function.__name__}() {sensor_info}')
            print('-' * nmax)
            print_exc()
            print('=' * nmax)
            print('\n')
            return
    return wrapper


# ========================== Sensor base classes =============================


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


# =============== Default controlled properties for recordings ===============

timer_ppty = ControlledProperty(attribute='timer.interval',
                                readable='Δt (s)',
                                commands=('dt',))

active_ppty = ControlledProperty(attribute='active',
                                 readable='Rec. ON',
                                 commands=('on',))

# ========================== Recording base class ============================


class RecordingBase(ABC):
    """Base class for recording object used by RecordBase. To subclass"""

    def __init__(self,
                 Sensor,
                 path='.',
                 dt=1,
                 ctrl_ppties=(),
                 active=True,
                 continuous=False,
                 warnings=False,
                 precise=False,
                 programs=(),
                 control_params=None):
        """Parameters:

        - Sensor: subclass of SensorBase.
        - path: directory in which data is recorded.
        - dt: time interval between readings (default 1s).
        - ctrl_ppties: optional iterable of properties (ControlledProperty
                       objects) to control on the recording in addition to
                       default ones (time interval and active on/off)
        - active: if False, do not record data until self.active set to True.
        - continuous: if True, take data as fast as possible from sensor.
        - warnings: if True, print warnings of Timer (e.g. loop too short).
        - precise: if True, use precise timer in oclock (see oclock.Timer).
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
        """
        self.Sensor = Sensor
        self.name = Sensor.name
        self.timer = oclock.Timer(interval=dt,
                                  name=self.name,
                                  warnings=warnings,
                                  precise=precise)
        self.path = Path(path)

        self.active = active  # can be set to False to temporarily stop recording from sensor
        self.continuous = continuous

        # Subclasses must define upon init the file (Path object) in which
        # data is saved. The file is opened at the beginning of the recording
        # and closed in the end.
        self.file = None

        # Iterable of the recording properties that the program / CLI control.
        # Possibility to add other properties in subclasses
        # (need to be of type ControlledProperty or subclass)
        self.controlled_properties = (timer_ppty, active_ppty) + ctrl_ppties
        self._add_sensor_controlled_properties()
        self._generate_ppty_dict()

        # Optional temporal programs to make controlled properties evolve.
        self._init_programs(programs=programs,
                            control_params=control_params)

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

    # Compulsory methods to subclass -----------------------------------------

    @abstractmethod
    def init_file(self, file_manager):
        """How to init the (already opened) data file (columns etc.).

        file_manager is the file object yielded by the open() context manager.
        """
        pass

    @abstractmethod
    def save(self, measurement, file_manager):
        """Write data of measurement to (already open) file.

        file_manager is the file object yielded by the open() context manager.
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

    def on_stop(self):
        """What happens when a stop event is requested in the CLI"""
        self.timer.stop()
        self._stop_programs()

class RecordBase:
    """Asynchronous recording of several Recordings object.

    Recordings objects are of type RecordingBase."""

    # Warnings when queue size goes over some limits
    queue_warning_limits = 1e1, 1e2, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8, 1e9

    def __init__(self,
                 recordings,
                 path='.',
                 on_start=(),
                 dt_save=1.9,
                 dt_request=0.7,
                 dt_check=1.3,
                 **ppty_kwargs):
        """Init base class for recording data

        Parameters
        ----------
        - recordings: dict {recording_name: recording_object}
        - properties: tuple of properties (ControlledProperty or subclass)
        - path: directory in which data is recorded.
        - on_start: optional iterable of objects with a .start() or .run()
                    method, that need to be started at the same time as
                    Record.start().
                    Note: for now, start() and run() need to be non-blocking.
        - dt_save: how often (in seconds) queues are checked and written to files
                   (it is also how often files are open/closed)
        - dt_request: time interval (in seconds) for checking user requests
                      (e.g. graph pop-up)
        - dt_check: time interval (in seconds) for checking queue sizes.
        - ppty_kwargs: optional initial setting of properties.
                     (example dt=10 for changing all time intervals to 10
                      or dt_P=60 to change only time interval of recording 'P')
        """
        self.recordings = recordings
        self.create_events()

        self.path = Path(path)
        self.path.mkdir(exist_ok=True)
        self.on_start = on_start

        self.dt_save = dt_save
        self.dt_request = dt_request
        self.dt_check = dt_check

        # Check if user inputs particular initial settings for recordings
        self.parse_initial_user_commands(ppty_kwargs)

        # Data is stored in a queue before being saved
        self.q_save = {name: Queue() for name in self.recordings}

        # Data queue for plotting when required
        self.q_plot = {name: Queue() for name in self.recordings}

        # Any additional functions that need to be run along the other threads
        # (to be defined in subclasses)
        self.additional_threads = []

    # =========== Optional methods and attributes for subclassing ============

    def save_metadata(self):
        """Save experimental metadata. To be defined in subclass"""
        pass

    def data_plot(self):
        """What to do with data when graph event is triggered"""
        pass

    # ============================= Misc methods =============================

    @staticmethod
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

    # ------------------------------------------------------------------------
    # ============================= INIT METHODS =============================
    # ------------------------------------------------------------------------

    def create_events(self):
        """Create event objects managed by the CLI"""
        self.e_stop = Event()  # event set to stop recording when needed.
        self.e_graph = Event()  # event set to start plotting the data in real time

        graph_event = ControlledEvent(event=self.e_graph,
                                      readable='graph',
                                      commands=('g', 'graph'))

        stop_event = ControlledEvent(event=self.e_stop,
                                     readable='stop',
                                     commands=('q', 'Q', 'quit'))

        self.events = graph_event, stop_event

    def parse_initial_user_commands(self, ppty_kwargs):
        """Check if user input contains specific properties.

        The values to apply for these properties are stored in a dict and
        will be applied to each recording when launched.

        If generic input (e.g. 'dt=10'), set all recordings to that value
        If specific input (e.g. dt_P=10), update recording to that value
        """
        self.initial_ppty_settings = {name: {} for name in self.recordings}

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
            for name, recording in self.recordings.items():
                ppty = recording.ppty_commands[ppty_cmd]
                self.initial_ppty_settings[name][ppty] = value

        # Then apply commands to specific recordings if specified ------------
        for name, (ppty_cmd, value) in specific_commands.items():
            ppty = self.recordings[name].ppty_commands[ppty_cmd]
            self.initial_ppty_settings[name][ppty] = value

    # ------------------------------------------------------------------------
    # =================== START RECORDING (MULTITHREAD) ======================
    # ------------------------------------------------------------------------

    def add_named_threads(self, function):
        for name in self.recordings:
            kwargs = {'name': name}
            self.threads.append(Thread(target=function, kwargs=kwargs))

    def add_other_threads(self):
        """Add other threads for additional functions defined by user."""
        for func in self.additional_threads:
            self.threads.append(Thread(target=func))

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

    def start(self):

        self.save_metadata()

        print(f'Recording started in folder {self.path.resolve()}')

        error_occurred = False

        try:

            self.threads = []

            self.add_named_threads(self.data_read)
            self.add_named_threads(self.data_save)
            self.threads.append(Thread(target=self.check_queue_sizes))
            self.add_other_threads()

            for thread in self.threads:
                thread.start()

            # Add CLI. This one is a bit particular because it is blocking
            # with input() and has to be manually stopped. ----------------
            self.cli_thread = Thread(target=self.cli)
            self.cli_thread.start()

            # Start any other user-supplied objects (need to be nonblocking)
            self.start_supplied_objects()

            # real time graph (triggered by CLI, runs in main thread due to
            # GUI backend problems if not) --------------------------------
            self.data_graph()

        except Exception as e:
            error_occurred = True
            print(f'\nERROR during recording: {e}. \n Stopping ... \n')
            print_exc()

        except KeyboardInterrupt:
            error_occurred = True
            print('\nManual interrupt by Ctrl-C event.\n Stopping ...\n')

        finally:

            self.e_stop.set()

            for thread in self.threads:
                thread.join()

            for obj in self.on_start:
                obj.stop()

            if error_occurred:
                print('\nIMPORTANT: CLI still running. Input "q" to stop.\n')

            self.cli_thread.join()

            print('Recording Stopped')

    # ------------------------------------------------------------------------
    # =============================== Threads ================================
    # -------------------- (CLI is defined elsewhere) ------------------------

    # =========================== Data acquisition ===========================

    @try_thread
    def cli(self):
        if self.recordings:  # if no recordings provided, no need to record.
            command_input = CommandLineInterface(self.recordings, self.events)
            command_input.run()
        else:
            self.e_stop.set()
            raise ValueError('No recordings provided. Stopping ...')


    @try_thread
    def data_read(self, name):
        """Read data from sensor and store it in data queues."""

        # Init ---------------------------------------------------------------

        recording = self.recordings[name]
        saving_queue = self.q_save[name]
        plotting_queue = self.q_plot[name]
        failed_reading = False  # True temporarily if P or T reading fails

        # Recording loop -----------------------------------------------------

        with recording.Sensor() as sensor:

            recording.sensor = sensor

            # Initial setting of properties is done here in case one of the
            # properties acts on the sensor object, which is not defined
            # before this point.
            # Note: (_set_property() does not do anything if the property
            # does not exist for the recording of interest)
            for ppty, value in self.initial_ppty_settings[name].items():
                recording._set_property(ppty=ppty, value=value)

            # Optional pre-defined program for change of recording properties
            for program in recording.programs:
                program.run()

            # Without this here, the first data points are irregularly spaced.
            recording.timer.reset()

            while not self.e_stop.is_set():

                if not recording.active:
                    if not recording.continuous:
                        # to avoid checking too frequently if active or not.
                        recording.timer.checkpt()
                    continue

                try:
                    data = sensor.read()

                # Measurement has failed .........................................
                except SensorError:
                    if not failed_reading:  # means it has not failed just before
                        recording.print_info_on_failed_reading('failed')
                    failed_reading = True

                # Measurement is OK ..............................................
                else:
                    if failed_reading:      # means it has failed just before
                        recording.print_info_on_failed_reading('resumed')
                        failed_reading = False

                    measurement = recording.format_measurement(data)
                    recording.after_measurement()

                    # Store recorded data in a first queue for saving to file
                    saving_queue.put(measurement)

                    # Store recorded data in another queue for plotting
                    if self.e_graph.is_set():
                        plotting_queue.put(measurement)

                # Below, this means that one does not try to acquire data right
                # away after a fail, but one waits for the usual time interval
                finally:
                    if not recording.continuous:
                        recording.timer.checkpt()

            else:
                recording.on_stop()

    # ========================== Write data to file ==========================

    def _try_save(self, measurement, recording, file):
        """Function to write data to file, used by data_save."""
        try:
            recording.save(measurement, file)
        except Exception:
            nmax, _ = os.get_terminal_size()
            print('\n')
            print('-' * nmax)
            print(f'Data saving error for {recording.name}:')
            print('(trying for new data at next time step)')
            print_exc()
            print('-' * nmax)
            print('\n')

    @try_thread
    def data_save(self, name):
        """Save data that is stored in a queue by data_read."""

        recording = self.recordings[name]
        saving_queue = self.q_save[name]
        saving_timer = oclock.Timer(interval=self.dt_save)

        with open(recording.file, 'a', encoding='utf8') as file:
            recording.init_file(file)

        while not self.e_stop.is_set():

            # Open and close file at each cycle to be able to save periodically
            # and for other users/programs to access the data simultaneously
            with open(recording.file, 'a', encoding='utf8') as file:

                while not saving_timer.interval_exceeded:

                    try:
                        measurement = saving_queue.get(timeout=self.dt_save)
                    except Empty:
                        pass
                    else:
                        self._try_save(measurement, recording, file)

                    if self.e_stop.is_set():  # Move to buffering waitbar
                        break

                # periodic check whether there is data to save
                saving_timer.checkpt()

        # Buffering waitbar --------------------------------------------------

        if not saving_queue.qsize():
            return

        print(f'Data buffer saving started for {name}')

        # The nested statements below, similarly to above, ensure that
        # recording.file is opened and close regularly to avoid loosing
        # too much data if there is an error.

        with tqdm(total=saving_queue.qsize()) as pbar:
            while True:
                try:
                    with open(recording.file, 'a', encoding='utf8') as file:
                        saving_timer.reset()
                        while not saving_timer.interval_exceeded:
                            measurement = saving_queue.get(timeout=self.dt_save)
                            self._try_save(measurement, recording, file)
                            pbar.update()
                except Empty:
                    break

        print(f'Data buffer saving finished for {name}')

    # =========================== Real-time graph ============================

    def data_graph(self):
        """Manage requests of real-time plotting of data during recording."""

        while not self.e_stop.is_set():

            if self.e_graph.is_set():
                # no need to reset e_graph here, because data_plot is blocking in
                # this version of the code (because of the plt.show() and
                # FuncAnimation). If data_plot is changed, it might be useful to
                # put back a e_graph.clear() here.

                self.data_plot()

            self.e_stop.wait(self.dt_request)  # check whether there is a graph request

    # ========================== Check queue sizes ===========================

    def _init_queue_size_info(self):
        """Create dict indicating that no queue limit is over among limits"""
        queue_size_over = {}
        for name in self.recordings:
            queue_size_over[name] = {limit: False
                                     for limit in self.queue_warning_limits}
        return queue_size_over

    def _check_queue_size(self, name, q, q_size_over, q_type):
        """Check that queue does not go beyond specified limits"""
        for qmax in self.queue_warning_limits:

            if q.qsize() > qmax:
                if not q_size_over[qmax]:
                    print(f'\nWARNING: {q_type} buffer size for {name} over {qmax} elements')
                    q_size_over[qmax] = True

            if q.qsize() <= qmax:
                if q_size_over[qmax]:
                    print(f'\n{q_type} buffer size now below {qmax} for {name}')
                    q_size_over[qmax] = False

    @try_thread
    def check_queue_sizes(self):
        """Periodically verify that queue sizes are not over limits"""

        self.q_save_size_over = self._init_queue_size_info()
        self.q_plot_size_over = self._init_queue_size_info()

        while not self.e_stop.is_set():

            for name in self.recordings:

                self._check_queue_size(name=name,
                                       q=self.q_save[name],
                                       q_size_over=self.q_save_size_over[name],
                                       q_type='Saving')

                if self.e_graph.is_set():

                    self._check_queue_size(name=name,
                                           q=self.q_save[name],
                                           q_size_over=self.q_save_size_over[name],
                                           q_type='Plotting')

            self.e_stop.wait(self.dt_check)

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
        - **kwargs is any keyword arguments to pass to Record __init__
          (including dt_save, ppty_kwargs etc.)
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

        recordings = {}
        for name in names:
            Recording = recording_types[name]
            Sensor = all_sensors[name]
            rec_kwargs = recording_kwargs[name]
            recordings[name] = Recording(Sensor,
                                         path=path,
                                         programs=all_programs[name],
                                         control_params=control_params,
                                         **rec_kwargs)

        return cls(recordings=recordings, path=path, **kwargs)
