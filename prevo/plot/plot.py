"""Plot data from sensors (from live measurements or saved data)."""

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
from threading import Event, Thread
from queue import Queue
from pathlib import Path


import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import oclock

from .general import GraphBase, MeasurementFormatter
from .general import DISPOSITIONS, local_timezone
from ..record import SensorError


# =============================== Main classes ===============================


class NumericalGraph(GraphBase):

    def __init__(self,
                 names,
                 data_types,
                 fig=None,
                 colors=None,
                 legends=None,
                 linestyles=None,
                 linestyle='.',
                 data_as_array=False,
                 time_conversion='numpy',
                 measurement_formatter=MeasurementFormatter()):
        """Initiate figures and axes for data plot as a function of asked types.

        Input
        -----
        - names: iterable of names of recordings/sensors that will be plotted.
        - data types: dict with the recording names as keys, and the
                      corresponding data types as values.
                      (dict can have more keys than those in 'names')
        - fig (optional): matplotlib figure in which to draw the graph.
        - colors: optional dict of colors with keys 'fig', 'ax', and the
                  names of the recordings.
        - legends: optional dict of legend names (iterable) corresponding to
                   all channels of each sensor, with the names of the
                   recordings as keys.
        - linestyles: optional dict of linestyles (iterable) to distinguish
                      channels and sensors, with the names of the recordings
                      as keys. If not specified (None), all lines have the
                      linestyle defined by the `linestyle=` parameter (see
                      below). If only some recordings are specified, the other
                      recordings have the default linestyle or the linestyle
                      defined by the `linestyle=` parameter.
        - linestyle: Matplotlib linestyle (e.g. '.', '-', '.-' etc.)
        - data_as_array: if sensors return arrays of values for different times
                         instead of values for a single time, put this
                         bool as True (default False)
        - time_conversion: how to convert from unix time to datetime for arrays;
                           possible values: 'numpy', 'pandas'.
        - measurement_formatter: MeasurementFormatter (or subclass) object.
        """
        super().__init__(names=names,
                         data_types=data_types,
                         fig=fig,
                         colors=colors,
                         legends=legends,
                         linestyles=linestyles,
                         linestyle=linestyle,
                         data_as_array=data_as_array,
                         time_conversion=time_conversion,
                         measurement_formatter=measurement_formatter)

    # ================== Methods subclassed from GraphBase ===================

    def create_axes(self):
        """Generate figure/axes as a function of input data types"""

        n = len(self.all_data_types)
        if n > 4:
            msg = f'Mode combination {self.all_data_types} not supported yet'
            raise Exception(msg)

        n1, n2 = DISPOSITIONS[n]  # dimensions of grid to place elements

        if self.fig is None:
            self.fig = plt.figure()

        width = 5 * n2
        height = 3 * n1
        self.fig.set_figheight(height)
        self.fig.set_figwidth(width)

        self.axs = {}
        for i, datatype in enumerate(self.all_data_types):
            ax = self.fig.add_subplot(n1, n2, i + 1)
            ax.set_ylabel(datatype)
            self.axs[datatype] = ax

    def format_graph(self):
        """Misc. settings for graph (time formatting, limits etc.)"""
        self.locator = {}  # For concise formatting of time -----------------------------------------
        self.formatter = {}
        for ax in self.axs.values():
            self.locator[ax] = mdates.AutoDateLocator(tz=local_timezone)
            self.formatter[ax] = mdates.ConciseDateFormatter(self.locator,
                                                             tz=local_timezone)

    def update_data(self, data):
        """Store measurement time and values in active data lists."""

        name = data['name']
        values = data['values']
        time = self.time_converters[name](data['time (unix)'])

        self.current_data[name]['times'].append(time)
        for i, value in enumerate(values):
            self.current_data[name]['values'][i].append(value)

    def update(self):
        self.update_lines()
        self.update_time_formatting()

    @property
    def animated_artists(self):
        return self.lines_list

    # ======================== Local update methods ==========================


    def update_lines(self):
        """Update line positions with current data."""

        for name in self.names:

            lines = self.lines[name]
            current_data = self.current_data[name]

            if current_data['times']:  # Avoids problems if no data stored yet

                times = self.timelist_to_array[name](current_data['times'])

                for line, curr_values in zip(lines,
                                             current_data['values']):

                    values = self.datalist_to_array[name](curr_values)
                    line.set_data(times, values)

    def update_time_formatting(self):
        """Use Concise Date Formatting for minimal space used on screen by time"""
        for ax in self.axs.values():
            ax.xaxis.set_major_locator(self.locator[ax])
            ax.xaxis.set_major_formatter(self.formatter[ax])
            # Lines below are needed for autoscaling to work
            ax.relim()
            ax.autoscale_view(tight=True, scalex=True, scaley=True)



# ============== Classes using Graph-like objects to plot data ===============


# ------------------------------- Static graph -------------------------------


class PlotSavedData:
    """Class to create graphs from saved data."""

    def __init__(self, names, graph, SavedData, file_names, path='.'):
        """Parameters:

        - names: names of sensors/recordings to consider
        - graph: object of GraphBase class and subclasses
        - SavedData: subclass of measurement.SavedDataBase
                            must have (name, filename, path) as arguments
                            and must define load() and format_as_measurement()
                            (see measurements.py)
        - file_names: dict {name: filename (str)} of files containing data
        - path: directory in which data is saved
        """
        self.names = names
        self.graph = graph
        self.SavedData = SavedData
        self.file_names = file_names
        self.path = Path(path)

    def show(self):
        """Static plot of saved data"""
        for name in self.names:
            saved_data = self.SavedData(name,
                                        filename=self.file_names[name],
                                        path=self.path)
            saved_data.load()
            measurement = saved_data.format_as_measurement()
            self.graph.plot(measurement)
        self.graph.fig.tight_layout()
        plt.show(block=False)


# ------------------------------ Updated graphs ------------------------------


class PlotUpdatedData:
    """Class to initiate and manage periodic reading of queues to plot data.

    Is subclassed to define get_data(), which indicates how to get the data
    (e.g. from live sensors, or from reading a file, etc.)
    """

    def __init__(self, graph, dt_data=1, dt_graph=1):
        """Parameters:

        - graph: object of GraphBase class and subclasses
        - dt_data is how often (in s) the loop checks for (or gets) new data.
        - dt_graph is how often (in s) the graph animation is updated
        """
        self.graph = graph
        self.timer = oclock.Timer(interval=dt_data, name='Data Update')
        self.dt_graph = dt_graph
        self.queues = {name: Queue() for name in self.names}
        self.internal_stop = Event()

    # Methods that need to be defined in subclasses --------------------------

    def get_data(self, name):
        """Get data and put it in queue"""
        pass

    # Other methods ----------------------------------------------------------

    def run(self):
        """Run reading of all data sources concurrently"""

        for name in self.names:
            Thread(target=self.get_data, args=(name,)).start()

        self.graph.run(queues=self.queues,
                       external_stop=self.internal_stop,
                       dt_graph=self.dt_graph)


class PlotLiveSensors(PlotUpdatedData):
    """Create live graph by reading the sensors directly."""

    def __init__(self, graph, recordings, dt_data=1, dt_graph=1):
        """Parameters:

        - graph: object of GraphBase class and subclasses
        - recordings: dict {name: recording(RecordingBase) object}
        - dt_data: how often (in s) sensors are probed
        - dt_graph is how often (in s) the graph animation is updated
        """
        self.recordings = recordings
        self.names = list(recordings)

        super().__init__(graph=graph, dt_data=dt_data, dt_graph=dt_graph)

    def get_data(self, name):
        """Check if new data is read by sensor, and put it in data queue."""
        self.timer.reset()
        recording = self.recordings[name]

        with recording.Sensor() as sensor:

            while not self.internal_stop.is_set():
                try:
                    data = sensor.read()
                except SensorError:
                    pass
                else:
                    measurement = recording.format_measurement(data)
                    recording.after_measurement()
                    self.queues[name].put(measurement)
                    self.timer.checkpt()
            else:
                print('WHILE LOOP STOPPED')


class PlotSavedDataUpdated(PlotUpdatedData, PlotSavedData):
    """Extends PlotSavedData to be able to periodically read file to update."""

    def __init__(self, names, graph, SavedData, file_names,
                 path='.', dt_data=1, dt_graph=1):
        """Parameters:

        - names: names of sensors/recordings to consider
        - graph: object of GraphBase class and subclasses
        - SavedData: Measurement class that manages data loading
                     must have (name, filename, path) as arguments and
                     must define load(), format_as_measurement() and
                     number_of_measurements() methods (see measurements.py)
        - file_names: dict {name: filename (str)} of files containing data
        - path: directory in which data is saved
        - dt_data: how often (in s) the files are checked for updates.
        - dt_graph: how often (in s) the graph animation is updated.
        """
        PlotSavedData.__init__(self,
                               names=names,
                               graph=graph,
                               SavedData=SavedData,
                               file_names=file_names,
                               path=path)

        PlotUpdatedData.__init__(self,
                                 graph=graph,
                                 dt_data=dt_data,
                                 dt_graph=dt_graph)

    def get_data(self, name):
        """Check if new data is added to file, and put it in data queue."""
        self.timer.reset()

        saved_data = self.SavedData(name,
                                    filename=self.file_names[name],
                                    path=self.path)

        n0 = saved_data.number_of_measurements()

        while not self.internal_stop.is_set():

            n = saved_data.number_of_measurements()

            if n > n0:
                saved_data.load(nrange=(n0 + 1, n))
                if saved_data.data is not None:
                    measurement = saved_data.format_as_measurement()
                    self.queues[name].put(measurement)
                    n0 = n

            self.timer.checkpt()
