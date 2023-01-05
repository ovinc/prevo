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
from datetime import datetime
from threading import Event, Thread
from queue import Queue
from pathlib import Path

# Non standard imports
import tzlocal
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
import oclock

from .general import NumericalGraphBase, UpdateGraphBase
from ..record import SensorError

# The two lines below have been added following a console FutureWarning:
# "Using an implicitly registered datetime converter for a matplotlib plotting
# method. The converter was registered by pandas on import. Future versions of
# pandas will require you to explicitly register matplotlib converters."
try:
    import pandas as pd
    from pandas.plotting import register_matplotlib_converters
    register_matplotlib_converters()
except ModuleNotFoundError:
    pandas_available = False
else:
    pandas_available = True


# Misc =======================================================================


local_timezone = tzlocal.get_localzone()


# =============================== Main classes ===============================


class UpdateGraph(UpdateGraphBase):

    def _manage_data(self, data):
        self.graph.update_current_data(data)

    def after_getting_measurements(self):
        self.graph.update_lines()
        self.graph.update_time_formatting()


class NumericalGraph(NumericalGraphBase):

    def __init__(self,
                 names,
                 data_types,
                 colors=None,
                 legends=None,
                 linestyles=None,
                 linestyle='.',
                 data_as_array=False,
                 time_conversion='numpy'):
        """Initiate figures and axes for data plot as a function of asked types.

        Input
        -----
        - names: iterable of names of recordings/sensors that will be plotted.
        - data types: dict with the recording names as keys, and the
                      corresponding data types as values.
                      (dict can have more keys than those in 'names')
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
        """
        self.timezone = local_timezone

        super().__init__(names=names,
                         data_types=data_types,
                         colors=colors,
                         legends=legends,
                         linestyles=linestyles,
                         linestyle=linestyle,
                         data_as_array=data_as_array)

        time_converters = {'datetime': self._to_datetime_datetime,
                           'numpy': self._to_datetime_numpy,
                           'pandas': self._to_datetime_pandas}

        self.time_converters = {}
        for name in self.names:
            if self.data_as_array[name]:
                self.time_converters[name] = time_converters[time_conversion]
            else:
                self.time_converters[name] = time_converters['datetime']

        self.current_data = self.create_empty_data()  # For live updates

    def create_axes(self):
        """Generate figure/axes as a function of input data types"""

        if len(self.all_data_types) == 4:
            fig, axes = plt.subplots(2, 2, figsize=(10, 9))
        if len(self.all_data_types) == 3:
            fig, axes = plt.subplots(1, 3, figsize=(14, 4))
        elif len(self.all_data_types) == 2:
            fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        elif len(self.all_data_types) == 1:
            fig, ax = plt.subplots(1, 1, figsize=(6, 4))
            axes = ax,
        else:
            msg = f'Mode combination {self.all_data_types} not supported yet'
            raise Exception(msg)

        axs = {}
        for ax, datatype in zip(axes, self.all_data_types):
            ax.set_ylabel(datatype)
            axs[datatype] = ax

        self.fig = fig
        self.axs = axs

    def format_graph(self):
        """Set colors, time formatting, etc."""

        # Concise formatting of time -----------------------------------------

        self.locator = {}
        self.formatter = {}

        for ax in self.axs.values():
            self.locator[ax] = mdates.AutoDateLocator(tz=self.timezone)
            self.formatter[ax] = mdates.ConciseDateFormatter(self.locator,
                                                             tz=self.timezone)

        # Create line objects for every sensor channel -----------------------
        self.create_lines()

    @property
    def animated_artists(self):
        return self.lines_list

    # ============================= Main methods =============================

    def _to_datetime_datetime(self, unix_time):
        """Transform single value of unix time into timezone-aware datetime."""
        return datetime.fromtimestamp(unix_time, self.timezone)

    @staticmethod
    def _to_datetime_numpy(unix_times):
        """Transform iterable / array of unix times into datetimes.

        Note: this is the fastest method, but the datetimes are in UTC format
              (not local time)
        """
        return (np.array(unix_times) * 1e9).astype('datetime64[ns]')

    def _to_datetime_pandas(self, unix_times):
        """Transform iterable / array of datetimes into pandas Series.

        Note: here, the datetimes are in local timezone format, but this is
              slower than the numpy approach.
        """
        # For some reason, it's faster (and more precise) to convert to numpy first
        np_times = (np.array(unix_times) * 1e9).astype('datetime64[ns]')
        pd_times = pd.Series(np_times)
        return pd.to_datetime(pd_times, utc=True).dt.tz_convert(self.timezone)

    def format_measurement(self, measurement):
        """Transform measurement from the queue into something usable by manage_data()

        Can be subclassed to adapt to various applications.
        Here, assumes data is incoming in the form of a dictionary with at
        least keys:
        - 'name' (str, identifier of sensor)
        - 'time (unix)' (floar or array of floats)
        - 'values' (iterable of values, or iterable of arrays of values)

        Subclass to adapt to applications.
        """
        data = {key: measurement[key] for key in ('name', 'values')}

        name = measurement['name']
        t_unix = measurement['time (unix)']

        data['time'] = self.time_converters[name](t_unix)

        return data

    # For static plots -------------------------------------------------------

    def _plot(self, data):
        """Generic plot method for static data.

        data is a dict obtained from format_measurement(measurement)
        where measurement is an object from the data queue.
        """
        name = data['name']
        values = data['values']
        time = data['time']

        dtypes = self.data_types[name]  # all data types for this specific signal
        clrs = self.colors[name]

        for value, dtype, clr in zip(values, dtypes, clrs):
            ax = self.axs[dtype]  # plot data in correct axis depending on type
            ax.plot(time, value, self.linestyle, color=clr)

        # Use Concise Date Formatting for minimal space used on screen by time
        different_types = set(dtypes)
        for dtype in different_types:
            ax = self.axs[dtype]
            ax.xaxis.set_major_locator(self.locator[ax])
            ax.xaxis.set_major_formatter(self.formatter[ax])

    # For updated plots ------------------------------------------------------

    def update_current_data(self, data):
        """Store measurement time and values in active data lists."""

        name = data['name']
        values = data['values']
        time = data['time']

        self.current_data[name]['times'].append(time)
        for i, value in enumerate(values):
            self.current_data[name]['values'][i].append(value)

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

    def run(self, q_plot, e_stop=None, e_close=None, e_graph=None,
            dt_graph=0.1, blit=False):
        """Run live view of plot with data from queues.

        (Convenience method to instantiate a UpdateGraph object)

        Parameters
        ----------
        - q_plot: dict {name: queue} with sensor names and data queues
        - e_stop (optional): external stop request, closes the figure if set
        - e_close (optional) is set when the figure has been closed
        - e_graph (optional) is set when the graph is activated
        - dt graph: time interval to update the graph
        - blit: if True, use blitting to speed up the matplotlib animation
        """
        update_plot = UpdateGraph(graph=self,
                                  q_plot=q_plot,
                                  e_stop=e_stop,
                                  e_close=e_close,
                                  e_graph=e_graph,
                                  dt_graph=dt_graph,
                                  blit=blit)
        update_plot.run()


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
        self.e_graph = Event()
        self.e_stop = Event()

    # Methods that need to be defined in subclasses --------------------------

    def get_data(self, name):
        """Get data and put it in queue"""
        pass

    # Other methods ----------------------------------------------------------

    def run(self):
        """Run reading of all data sources concurrently"""

        for name in self.names:
            Thread(target=self.get_data, args=(name,)).start()

        self.e_graph.set()  # This is supposed to be set when graph is active.

        # e_stop two times, because we want a figure closure event to also
        # trigger stopping of the recording process here.

        self.graph.run(q_plot=self.queues,
                       e_stop=self.e_stop,
                       e_close=self.e_stop,
                       e_graph=self.e_graph,
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

            while not self.e_stop.is_set():
                try:
                    data = sensor.read()
                except SensorError:
                    pass
                else:
                    measurement = recording.format_measurement(data)
                    recording.after_measurement()
                    self.queues[name].put(measurement)
                    self.timer.checkpt()


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

        while not self.e_stop.is_set():

            n = saved_data.number_of_measurements()

            if n > n0:
                saved_data.load(nrange=(n0 + 1, n))
                if saved_data.data is not None:
                    measurement = saved_data.format_as_measurement()
                    self.queues[name].put(measurement)
                    n0 = n

            self.timer.checkpt()
