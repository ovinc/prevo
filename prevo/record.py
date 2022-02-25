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

# Non-standard imports
from tqdm import tqdm
import oclock
from clivo import CommandLineInterface as ClI


# ================================ MISC Tools ================================


def try_thread(function):
    """Decorator to make threaded functions return & print errors if errors occur"""
    def wrapper(*args, **kwargs):
        try:
            function(*args, **kwargs)
        except Exception as e:
            _, name = args
            print(f'\nERROR for {function.__name__} with {name} !!! \n{e}')
            return
    return wrapper


# ========================== Sensor base classes =============================


class SensorError(Exception):
    pass


class SensorBase(ABC):
    """Abstract base class for sensor acquisition."""

    def __init__(self):
        # (optional) : specific sensor errors to catch, can be an Exception
        # class or an iterable of exceptions; if not specified in subclass,
        # any exception is catched.
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
        """Name of sensor, Must be a class attribute.
        """
        pass

    @abstractmethod
    def _read(self):
        """Read sensor, method must be defined in sensor subclass."""
        pass

    def read(self):
        """Read sensor and throw SensorError if measurement fails."""
        try:
            data = self._read()
        except self.exceptions:
            raise SensorError(f'Impossible to read {self.name} sensor')
        else:
            return data


# ========================== Recording base class ============================


class RecordingBase(ABC):
    """Base class for recording object used by RecordBase. To subclass"""

    def __init__(self, Sensor, dt, continuous=False, warnings=True, precise=False):
        """Parameters:

        - Sensor: subclass of SensorBase.
        - dt: time interval between readings.
        - continuous: if True, take data as fast as possible from sensor.
        - warnings: if True, print warnings of Timer (e.g. loop too short).
        - precise: if True, use precise timer in oclock (see oclock.Timer).
        """
        self.Sensor = Sensor
        self.name = Sensor.name
        self.timer = oclock.Timer(interval=dt,
                                  name=self.name,
                                  warnings=warnings,
                                  precise=precise)
        self.continuous = continuous

        # Subclasses must define the following attributes upon init ----------

        # File (Path object) in which data is saved. The file is opened at the
        # beginning of the recording and closed in the end.
        self.file = None

        # Iterable of the name of properties of the object that the CLI controls.
        # e.g. 'timer.interval', 'averaging', etc.
        self.controlled_properties = []

    # Compulsory methods to subclass -----------------------------------------

    @abstractmethod
    def format_measurement(self, data):
        """How to format the data given by self.Sensor.read().

        Returns a measurement object (e.g. dict, value, custom class etc.)."""
        pass

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


class RecordBase:
    """Asynchronous recording of several Recordings object.

    Recordings objects are of type RecordingBase.
    """

    # Warnings when queue size goes over some limits
    queue_warning_limits = 100, 1000, 10000

    def __init__(self,
                 recordings,
                 properties,
                 path='.',
                 dt_save=1.9,
                 dt_request=0.7,
                 dt_check=1.3,
                 **ppty_kwargs):
        """Init base class for recording data

        Parameters
        ----------
        - recordings: dict {recording_name: recording_object}
        - properties: dict of dicts of properties to control (see clivo.CLI)
        - path: directory in which data is recorded.
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
        self.properties = properties

        self.property_commands = ClI._get_commands(self.properties)
        self.object_properties = ClI._get_controlled_properties(self,
                                                                self.recordings)

        self.path = Path(path)
        self.path.mkdir(exist_ok=True)

        self.dt_save = dt_save
        self.dt_request = dt_request
        self.dt_check = dt_check

        # Check if user inputs particular initial settings for recordings
        self.initial_property_settings = self.init_properties(ppty_kwargs)

        self.e_stop = Event()  # event set to stop recording when needed.
        self.e_graph = Event()  # event set to start plotting the data in real time

        # Data is stored in a queue before being saved
        self.q_save = {name: Queue() for name in self.recordings}

        # Data queue for plotting when required
        self.q_plot = {name: Queue() for name in self.recordings}

        self.events = {'graph': {'event': self.e_graph,
                                 'commands': ('g', 'graph')
                                 },
                       'stop': {'event': self.e_stop,
                                'commands': ('q', 'Q', 'quit')
                                }
                       }

        self.save_metadata()

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

    def init_properties(self, ppty_kwargs):
        """Check if user input contains specific properties and apply them."""

        # Dict of dict managing initial settings passed by user
        initial_ppty_settings = {name: {ppty_cmd: None
                                        for ppty_cmd in self.property_commands}
                                 for name in self.recordings}

        for ppty_cmd in self.property_commands:

            # If generic input (e.g. 'dt=10'), set all recordings to that value

            try:
                value = ppty_kwargs[ppty_cmd]   # ppty_cmd is e.g. dt, avg etc.
            except KeyError:
                pass
            else:
                for name in self.recordings:
                    initial_ppty_settings[name][ppty_cmd] = value

            # If specific input (e.g. dt_P=10), update recording to that value

            for recording_name in self.recordings:
                cmd = f'{ppty_cmd}_{recording_name}'
                try:
                    value = ppty_kwargs[cmd]
                except KeyError:
                    pass
                else:
                    initial_ppty_settings[name][ppty_cmd] = value

        return initial_ppty_settings

    # ------------------------------------------------------------------------
    # =================== START RECORDING (MULTITHREAD) ======================
    # ------------------------------------------------------------------------

    def add_data_reading_threads(self):
        """Read data from each sensor and put in queue"""
        for name in self.recordings:
            self.threads.append(Thread(target=self.data_read, args=(name,)))

    def add_data_saving_threads(self):
        """save data present in the data queues whenever they are not empty.

        The with statement allows the file to stay open during measurement.
        """
        for name in self.recordings:
            self.threads.append(Thread(target=self.data_save, args=(name,)))

    def add_queue_check_thread(self):
        """Check size of queues periodically"""
        self.threads.append(Thread(target=self.check_queue_sizes))

    def add_other_threads(self):
        """Add other threads for additional functions defined by user."""
        for func in self.additional_threads:
            self.threads.append(Thread(target=func))

    def start(self):

        print(f'Recording started in folder {self.path.resolve()}')

        error_occurred = False

        try:

            self.threads = []

            self.add_data_reading_threads()
            self.add_data_saving_threads()
            self.add_queue_check_thread()
            self.add_other_threads()

            for thread in self.threads:
                thread.start()

            # Add CLI. This one is a bit particular because it is blocking
            # with input() and has to be manually stopped. ----------------
            command_input = ClI(self.recordings, self.properties, self.events)
            self.cli_thread = Thread(target=command_input.run)
            self.cli_thread.start()

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

            if error_occurred:
                print('\nIMPORTANT: CLI still running. Input "q" to stop.\n')

            self.cli_thread.join()

            print('Recording Stopped')

    # ------------------------------------------------------------------------
    # =============================== Threads ================================
    # -------------------- (CLI is defined elsewhere) ------------------------

    # =========================== Data acquisition ===========================

    @try_thread
    def data_read(self, name):
        """Read data from sensor and store it in data queues."""

        # Init ---------------------------------------------------------------

        recording = self.recordings[name]
        initial_ppty_settings = self.initial_property_settings[name]
        saving_queue = self.q_save[name]
        plotting_queue = self.q_plot[name]

        recording.timer.reset()
        failed_reading = False  # True temporarily if P or T reading fails

        # Recording loop -----------------------------------------------------

        with recording.Sensor() as sensor:

            recording.sensor = sensor

            # Initial setting of properties is done here in case one of the
            # properties acts on the sensor object, which is not defined
            # before this point.
            # Note: (_set_property_base() does not do anything if the property
            # does not exist for the recording of interest)
            for ppty_cmd, value in initial_ppty_settings.items():
                if value is not None:
                    ClI._set_property_base(self, ppty_cmd, name,
                                           value, objects=self.recordings)

                    # To avoid geting another image immediately
                    recording.timer.checkpt()

            while not self.e_stop.is_set():

                try:
                    data = sensor.read()

                # Measurement has failed .........................................
                except SensorError:
                    if not failed_reading:  # means it has not failed just before
                        recording.print_info_on_failed_reading(recording.name,
                                                               'failed')
                    failed_reading = True

                # Measurement is OK ..............................................
                else:
                    if failed_reading:      # means it has failed just before
                        recording.print_info_on_failed_reading(recording.name,
                                                               'resumed')
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

    # ========================== Write data to file ==========================

    def _try_save(self, measurement, recording, file):
        """Function to write data to file, used by data_save."""
        try:
            recording.save(measurement, file)
        except Exception as error:
            print(f'Data saving error for {recording.name}: {error}')
            print_exc()

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
