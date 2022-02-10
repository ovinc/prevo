"""Record several sensors as a function of time with interactive CLI and graph."""


# Standard library imports
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from queue import Queue

# Non-standard imports
import oclock
from clyo import CommandLineInterface


class RecordingBase(ABC):
    """Base class for recording object used by RecordBase. To subclass"""

    def __init__(self, dt):
        """Parameters:

        - dt: time interval between readings
        - warnings: if True, print warnings when interval cannot be satisfied
          etc. (see oclock.Timer warnings option)
        """
        self.timer = oclock.Timer(interval=dt,
                                  name=self.name,
                                  warnings=True)

    # Compulsory attributes (properties) -------------------------------------

    @property
    @abstractmethod
    def name(self):
        """Name (identifier) of recording object"""
        pass

    @property
    @abstractmethod
    def file(self):
        """File (Path object) in which data is saved.

        The file is opened at the beginning of the recording and closed in
        the end.
        """
        pass

    @property
    @abstractmethod
    def SensorError(self):
        """Exception class raised when sensor reading fails."""
        pass

    # Compulsory methods to subclass -----------------------------------------

    @abstractmethod
    def read(self):
        """How to read the data. Normally, self.sensor.read()"""
        pass

    @abstractmethod
    def format_measurement(self, data):
        """How to format the data given by self.read().

        Returns a measurement object (e.g. dict, value, custom class etc.)."""
        pass

    @abstractmethod
    def init_file(self):
        """How to init the file containing the data (columns etc.)."""
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

    def __init__(self, recordings, properties, path, dt_check, **ppty_kwargs):
        """Init base class for recording data

        Parameters
        ----------
        recordings: dict {recording_name: recording_object}
        properties: dict of dicts of properties to control (see clyo.CLI)
        path: directory in which data is recorded.
        dt_check: time interval for checking queues for saving/plotting
        ppty_kwargs: optional initial setting of properties.
                     (example dt=10 for changing all time intervals to 10
                      or dt_P=60 to change only time interval of recording 'P')
        """
        self.recordings = recordings
        self.properties = properties
        self.property_commands = self._get_commands(self.properties)

        self.path = Path(path)
        self.dt_check = dt_check

        self.init_files()  # specific files where data is saved
        self.init_properties(ppty_kwargs)  # set loop timing according to kwargs

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

    @staticmethod
    def _get_commands(input_data):
        """Create dict of which command input modifies which property/event.

        See clyo.CommandLineInterface._get_commands.
        """
        return CommandLineInterface._get_commands(input_data)

    # =========== Optional methods and attributes for subclassing ============

    def save_metadata(self):
        """Save experimental metadata. To be defined in subclass"""
        pass

    def data_plot(self):
        """What to do with data when graph event is triggered"""
        pass

    # ============================= Misc methods =============================

    def _set_property(self, ppty_cmd, recording_name, value):
        """Manage command from CLI to set a property accordingly."""
        ppty = self.property_commands[ppty_cmd]
        recording = self.recordings[recording_name]
        exec(f'recording.{ppty} = {value}')

    # ------------------------------------------------------------------------
    # ============================= INIT METHODS =============================
    # ------------------------------------------------------------------------

    def init_files(self):
        """Init files in which to store data, add column titles if needed."""
        self.path.mkdir(exist_ok=True)
        for recording in self.recordings.values():
            recording.init_file()

    def init_properties(self, ppty_kwargs):
        """Check if user input contains specific properties and apply them."""

        for ppty_cmd in self.property_commands:

            # If generic input (e.g. 'dt=10'), set all recordings to that value

            try:
                value = ppty_kwargs[ppty_cmd]   # ppty_cmd is e.g. dt, avg etc.
            except KeyError:
                values = {name: None for name in self.recordings}
            else:
                values = {name: value for name in self.recordings}

            # If specific input (e.g. dt_P=10), update recording to that value

            for recording_name in self.recordings:
                cmd = f'{ppty_cmd}_{recording_name}'
                try:
                    value = ppty_kwargs[cmd]
                except KeyError:
                    pass
                else:
                    values[recording_name] = value

                # Finally, set property value to recording if necessary
                if values[recording_name] is not None:
                    self._set_property(ppty_cmd, recording_name, value)

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
        for name, recording in self.recordings.items():
            with open(recording.file, 'a') as file:
                self.threads.append(Thread(target=self.data_save,
                                           args=(name, file)))

    def add_command_line_thread(self):
        """Interactive command line interface"""
        command_input = CommandLineInterface(self.recordings,
                                             self.properties,
                                             self.events)

        self.threads.append(Thread(target=command_input.run))

    def add_other_threads(self):
        """Add other threads for additional functions defined by user."""
        for func in self.additional_threads:
            self.threads.append(Thread(target=func))

    def start(self):

        print(f'Recording started in folder {self.path.resolve()}')

        # ========================== Define threads ==========================

        self.threads = []

        self.add_data_reading_threads()
        self.add_data_saving_threads()
        self.add_command_line_thread()
        self.add_other_threads()

        for thread in self.threads:
            thread.start()

        # real time graph (triggered by CLI, runs in main thread due to
        # matplotlib backend problems if not) --------------------------------
        self.data_graph()

        for thread in self.threads:
            thread.join()

        print('Recording stopped.')

    # ------------------------------------------------------------------------
    # =============================== Threads ================================
    # -------------------- (CLI is defined elsewhere) ------------------------

    # =========================== Data acquisition ===========================

    def data_read(self, name):
        """Read data from sensor and store it in data queues."""

        # Init ---------------------------------------------------------------

        recording = self.recordings[name]
        saving_queue = self.q_save[name]
        plotting_queue = self.q_plot[name]

        recording.timer.reset()
        failed_reading = False  # True temporarily if P or T reading fails
        SensorReadingError = recording.SensorError

        # Recording loop -----------------------------------------------------

        while not self.e_stop.is_set():

            try:
                data = recording.read()

            # Measurement has failed .........................................
            except SensorReadingError:
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
                recording.timer.checkpt()

    # ========================== Write data to file ==========================

    def data_save(self, name, file):
        """Save data that is stored in a queue by data_read."""

        recording = self.recordings[name]
        saving_queue = self.q_save[name]

        while not self.e_stop.is_set():

            while saving_queue.qsize() > 0:
                measurement = saving_queue.get()
                try:
                    recording.save(measurement, file)
                except Exception as error:
                    print(f'Data saving error for {name}: {error}')
            self.e_stop.wait(self.dt_check)   # periodic check whether there is data to save

    # =========================== Real-time graph ============================

    def data_graph(self):
        """Manage real-time plotting of data during recording."""

        while not self.e_stop.is_set():

            if self.e_graph.is_set():
                # no need to reset e_graph here, because data_plot is blocking in
                # this version of the code (because of the plt.show() and
                # FuncAnimation). If data_plot is changed, it might be useful to
                # put back a e_graph.clear() here.

                self.data_plot()

            self.e_stop.wait(self.dt_check)  # check whether there is a graph request
            # (NOT the refresh rate of the graph, which is set in data_plot)
