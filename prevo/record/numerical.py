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
from .general import RecordingBase, Record
from ..csv import CsvFile
from ..plot import NumericalGraph
from ..misc import increment_filename


class NumericalRecording(RecordingBase):
    """Recording class for saving numerical sensor data to CSV files."""

    def __init__(
        self,
        Sensor,
        filename,
        path=".",
        column_names=None,
        column_formats=None,
        csv_separator="\t",
        **kwargs,
    ):
        """Initialize a NumericalRecording object.

        Parameters
        ----------
        Sensor : subclass of SensorBase
            Sensor class responsible for capturing numerical data.
        filename : str
            Name of the CSV/TSV file where data will be saved.
        path : str, default="."
            Directory where the CSV/TSV file will be created.
        column_names : iterable of str, optional
            Names of the columns in the CSV file.
        column_formats : iterable of str, optional
            Optional string formatting for each column in the CSV file.
        csv_separator : str, default="\t"
            Character used to separate columns in the CSV
        """
        super().__init__(Sensor=Sensor, path=path, **kwargs)

        self.file_manager = CsvFile(
            path=self.path / filename,
            column_names=column_names,
            column_formats=column_formats,
            csv_separator=csv_separator,
        )

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
        measurement["name"] = self.name
        return measurement

    def save(self, measurement, file):
        """Save measurement data to a file.

        Parameters
        ----------
        measurement : Measurement object
            Measurement object to be saved. Assumed to be a dictionary with keys:
            'time (unix)', 'dt (s)', and 'values'.
        file : file-like object
            File object where the data will be saved.

        Returns
        -------
        iterable
            Iterable of data to be saved in the CSV file. The length of the iterable
            must match the length of `column_names`.

        Notes
        -----
        - Can be redefined in subclasses for custom behavior.
        - If `measurement` is None, `Record.data_save()` will not save the data.
        """
        time_info = (measurement["time (unix)"], measurement["dt (s)"])
        value_info = measurement["values"]
        self.file_manager._write_line(time_info + value_info, file=file)


class NumericalRecord(Record):
    """Class for managing simultaneous temporal recordings of numerical sensors."""

    def __init__(
        self,
        recordings,
        metadata_filename="Numerical_Metadata.json",
        checked_modules=(),
        data_types=None,
        dt_graph=0.1,
        graph_legends=None,
        graph_colors=None,
        graph_linestyle=".",
        dirty_ok=True,
        **kwargs,
    ):
        """Initialize a NumericalRecord object.

        Parameters
        ----------
        recordings : iterable
            Iterable of recording objects (RecordingBase or its subclasses).
        metadata_filename : str, default="Numerical_Metadata.json"
            Name of the JSON file where metadata will be saved.
        checked_modules : iterable, optional
            Iterable of Python modules whose versions will be saved in the
            metadata, in addition to the `prevo` module.
        data_types : iterable, optional
            Iterable of data types for selecting the window in which to plot
            data when graphs are active. If not supplied, graphs cannot be
            instantiated.
        dt_graph : float, default=0.1
            Time interval (in seconds) to refresh the numerical graph.
        graph_colors : dict, optional
            Dictionary of graph colors for the numerical graph (see `prevo.plot`).
        graph_legends : dict, optional
            Dictionary of graph legends for the numerical graph (see `prevo.plot`).
        graph_linestyle : str, default="."
            Linestyle of data on the numerical graph (e.g., '.-').
        dirty_ok : bool, default=True
            If False, the recording cannot be started if Git repositories are
            not clean (uncommitted changes).

        **kwargs : dict, optional
            Additional keyword arguments inherited from Record:
            path : str, default="."
                Directory where recorded data will be saved.
            on_start : iterable, optional
                Iterable of objects with `.start()` or `.run()` methods. These
                methods are called when `Record.start()` is invoked. Note:
                `.start()` and `.run()` must be non-blocking.
            dt_request : float, default=0.7
                Time interval (in seconds) for checking user requests, such as
                graph pop-ups.
        """
        super().__init__(recordings=recordings, **kwargs)
        self.metadata_filename = metadata_filename
        self.checked_modules = set((prevo,) + tuple(checked_modules))

        # Graphing options -------------
        self.data_types = data_types
        self.dt_graph = dt_graph
        self.graph_legends = graph_legends
        self.graph_colors = graph_colors
        self.graph_linestyle = graph_linestyle

        self.dirty_ok = dirty_ok
        self.get_numerical_recordings()

    def get_numerical_recordings(self):
        """Useful when vacuum combined with other recording types (e.g. camrec)"""
        self.numerical_recordings = {}
        for name, recording in self.recordings.items():
            if issubclass(recording.__class__, NumericalRecording):
                self.numerical_recordings[name] = recording

    def _save_metadata(self):
        """To call save_metadata() with custom filenames"""
        metadata_file = self.path / self.metadata_filename

        if metadata_file.exists():
            metadata_file = increment_filename(metadata_file)

        gittools.save_metadata(
            metadata_file,
            module=self.checked_modules,
            dirty_warning=True,
            dirty_ok=self.dirty_ok,
            notag_warning=True,
            nogit_ok=True,
            nogit_warning=True,
        )

    def data_plot(self):
        """What to do when graph event is triggered"""
        if self.data_types is None:
            print("WARNING --- No data types supplied. Graph not possible.")
            return

        graph = NumericalGraph(
            names=self.numerical_recordings,
            data_types=self.data_types,
            legends=self.graph_legends,
            colors=self.graph_colors,
            linestyle=self.graph_linestyle,
            data_as_array=False,
        )

        # In case the queue contains other measurements than numerical
        # (e.g. images from cameras)
        numerical_queues = [
            recording.queues["plotting"]
            for recording in self.numerical_recordings.values()
        ]

        graph.run(
            queues=numerical_queues,
            external_stop=self.internal_stop,
            dt_graph=self.dt_graph,
        )
