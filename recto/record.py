"""Record several sensors as a function of time with interactive CLI and graph."""


# Standard library imports
from pathlib import Path
from threading import Event, Thread
from queue import Queue

# Non-standard imports
from clyo import CommandLineInterface


class RecordBase:

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

        self.q_save = Queue()  # data is stored in a queue before being saved
        self.q_plot = Queue()  # data queue for plotting when required

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

    # ============= Methods and attributes that need subclassing =============

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

    def start(self):

        print(f'Recording started in folder {self.path.resolve()}')

        threads = []

        # ========================== Define threads ==========================

        # read data from each sensor and put in queue ------------------------

        for recording in self.recordings.values():
            threads.append(Thread(target=self.data_read, args=(recording,)))

        # save data present in the data queue whenever it's not empty) -------

        threads.append(Thread(target=self.data_save))

        # interactive Command Line Interface ---------------------------------

        command_input = CommandLineInterface(self.recordings,
                                             self.properties,
                                             self.events)

        threads.append(Thread(target=command_input.run))

        # any additional threads ---------------------------------------------

        for func in self.additional_threads:
            threads.append(Thread(target=func))

        # ====================================================================

        for thread in threads:
            thread.start()

        # real time graph (triggered by CLI, runs in main thread due to
        # matplotlib backend problems if not) --------------------------------
        self.data_graph()

        for thread in threads:
            thread.join()

        print('Recording stopped.')

    # ------------------------------------------------------------------------
    # =============================== Threads ================================
    # -------------------- (CLI is defined elsewhere) ------------------------

    # =========================== Data acquisition ===========================

    def data_read(self, recording):
        """Read data from sensor and store it in data queues."""

        # Init ---------------------------------------------------------------

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
                self.q_save.put(measurement)

                # Store recorded data in another queue for plotting
                if self.e_graph.is_set():
                    self.q_plot.put(measurement)

            # Below, this means that one does not try to acquire data right
            # away after a fail, but one waits for the usual time interval
            finally:
                recording.timer.checkpt()

    # ========================== Write data to file ==========================

    def data_save(self):
        """Save data that is stored in a queue by data_read."""

        while not self.e_stop.is_set():
            while self.q_save.qsize() > 0:
                measurement = self.q_save.get()
                recording = self.recordings[measurement.name]
                try:
                    recording.save(measurement)
                except Exception as error:
                    print(f'Data saving error for {measurement.name}: {error}')
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
