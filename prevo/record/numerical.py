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
                 filename,
                 *args,
                 column_names=None,
                 column_formats=None,
                 path='.',
                 csv_separator='\t',
                 **kwargs):

        super().__init__(*args, **kwargs)

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
                 *args,
                 metadata_filename='Metadata.json',
                 checked_modules=(),
                 data_types=None,
                 dt_graph=0.1,
                 graph_colors=None,
                 dirty_ok=True,
                 **kwargs):
        """If testing, do not raise errors if modules are dirty"""
        super().__init__(*args, **kwargs)
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

    def save_metadata(self):
        """Save info on code version of modules used for the recording"""

        metadata_file = self.path / self.metadata_filename

        if metadata_file.exists():
            metadata_file = self.increment_filename(metadata_file)

        gittools.save_metadata(metadata_file,
                               module=self.checked_modules,
                               dirty_warning=True,
                               dirty_ok=self.dirty_ok,
                               notag_warning=True,
                               nogit_ok=True,
                               nogit_warning=True)

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
