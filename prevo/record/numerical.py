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


# Non-standard imports
import gittools
import prevo

# Local imports
from .general import RecordBase, RecordingBase
from ..csv import CsvFile
from ..plot import NumericalGraph


class NumericalRecording(RecordingBase):
    """Recording class that saves numerical sensor data to csv files."""

    def __init__(self,
                 Sensor,
                 filename,
                 path='.',
                 column_names=None,
                 column_formats=None,
                 csv_separator='\t',
                 **kwargs):
        """Init NumericalRecording object.

        Parameters
        ----------
        - Sensor: subclass of SensorBase.
        - filename: name of csv/tsv file in which data will be saved.
        - column_names: iterable of str (name of columns in csv file)
        - column_formats: iterable of str (optional, str formatting)
        - csv_separator: character to separate columns in CSV file.

        Additional kwargs from RecordingBase:
        - path: directory in which csv/tsv file will be created.
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
        super().__init__(Sensor=Sensor, path=path, **kwargs)

        self.file_manager = CsvFile(filename=filename,
                                    column_names=column_names,
                                    column_formats=column_formats,
                                    path=path,
                                    csv_separator=csv_separator)


    def format_measurement(self, measurement):
        """Format raw sensor data into a measurement object.

        This object is put in the saving queue and in the plotting queue
        if active.

        Here we assume that measurements are in the form of dictionaries, but
        this can be changed by subclassing.
        """

        if measurement is None:
            return
        # Adding the name is useful e.g. for plotting.
        measurement['name'] = self.name
        return measurement

    def save(self, measurement, file):
        """Save to file

        Inputs
        ------
        - measurement: Measurement object
        - file:

        Output
        ------
        Iterable of data to be saved in CSV file

        The length of the iterable must be equal to that of column_names.

        Here, we assume a standard measurement as a dict with keys
        'time (unix)', 'dt (s)', 'values'

        Can be redefined in subclasses.
        NOTE: if measurement is None, Record.data_save() does not save the data
        """
        time_info = (measurement['time (unix)'], measurement['dt (s)'])
        value_info = measurement['values']
        self.file_manager._write_line(time_info + value_info, file=file)


class NumericalRecord(RecordBase):
    """Class managing simultaneous temporal recordings of numerical sensors"""

    def __init__(self,
                 recordings,
                 metadata_filename='Numerical_Metadata.json',
                 checked_modules=(),
                 data_types=None,
                 dt_graph=0.1,
                 graph_colors=None,
                 dirty_ok=True,
                 **kwargs):
        """Init NumericalRecord object.

        Parameters
        ----------
        - recordings: iterable of recording objects (RecordingBase or subclass)
        - metadata_filename: name of .json file in which metadata is saved
        - checked_modules: iterable of python modules, the version of which
                           will be saved in metadata, in addition to prevo.
        - data_types: iterable of data types (for selecting window in which
                      which to plot data when graphs are active);
                      if not supplied, graphs can not be instantiated.
        - dt_graph: time interval to refresh numerical graph.
        - graph_colors: dict of graph colors for numerical graph
                        (see prevo.plot)
        - dirty_ok: if False, record cannot be started if git repositories are
                    not clean (commited).

        Additional kwargs from RecordingBase:
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
        """
        super().__init__(recordings=recordings, **kwargs)
        self.metadata_filename = metadata_filename
        self.checked_modules = set((prevo,) + tuple(checked_modules))

        # Graphing options -------------
        self.data_types = data_types
        self.dt_graph = dt_graph
        self.graph_colors = graph_colors

        self.dirty_ok = dirty_ok
        self.get_numerical_recordings()

    def get_numerical_recordings(self):
        """Useful when vacuum combined with other recording types (e.g. camrec)"""
        self.numerical_recordings = {}
        for name, recording in self.recordings.items():
            if issubclass(recording.__class__, NumericalRecording):
                self.numerical_recordings[name] = recording

    def _save_metadata(self, filename):
        """To call save_metadata() with custom filenames"""
        metadata_file = self.path / filename

        if metadata_file.exists():
            metadata_file = self.increment_filename(metadata_file)

        gittools.save_metadata(metadata_file,
                               module=self.checked_modules,
                               dirty_warning=True,
                               dirty_ok=self.dirty_ok,
                               notag_warning=True,
                               nogit_ok=True,
                               nogit_warning=True)

    def save_metadata(self):
        """Save info on code version of modules used for the recording"""
        self._save_metadata(filename=self.metadata_filename)

    def data_plot(self):
        """What to do when graph event is triggered"""
        if self.data_types is None:
            print('WARNING --- No data types supplied. Graph not possible.')
            self.e_graph.clear()
            return

        graph = NumericalGraph(names=self.numerical_recordings,
                               data_types=self.data_types,
                               colors=self.graph_colors,
                               data_as_array=False)

        # In case the queue contains other measurements than numerical
        # (e.g. images from cameras)
        numerical_queue = {name: self.q_plot[name]
                           for name in self.numerical_recordings}

        graph.run(q_plot=numerical_queue,
                  e_stop=self.e_stop,
                  e_graph=self.e_graph,
                  dt_graph=self.dt_graph)
