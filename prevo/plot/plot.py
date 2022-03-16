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
import matplotlib

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
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
    pass


class NumericalGraph(NumericalGraphBase):

    def __init__(self, names, data_types, colors=None):
        """Initiate figures and axes for data plot as a function of asked types.

        Input
        -----
        - names: iterable of names of recordings/sensors that will be plotted.
        - data types: dict with the recording names as keys, and the
                      corresponding data types as values.
                      (dict can have more keys than those in 'names')
        - colors: optional dict of colors with keys 'fig', 'ax', and the
                  names of the recordings.
        """
        self.timezone = local_timezone

        super().__init__(names=names, data_types=data_types, colors=colors)

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

    # ============================= Main methods =============================

    @staticmethod
    def _to_datetime_numpy(unix_times):
        """Transform iterable / array of unix times into datetimes.

        Note: this is the fastest method, but the datetimes are in UTC format
              (not local time)
        """
        return (np.array(unix_times) * 1e9).astype('datetime64[ns]')

    @staticmethod
    def _to_datetime_pandas(unix_times):
        """Transform iterable / array of datetimes into pandas Series.

        Note: here, the datetimes are in local timezone format, but this is
              slower than the numpy approach.
        """
        # For some reason, it's faster (and more precise) to convert to numpy first
        np_times = (np.array(unix_times) * 1e9).astype('datetime64[ns]')
        pd_times = pd.Series(np_times)
        return pd.to_datetime(pd_times, utc=True).dt.tz_convert(local_timezone)

    def format_measurement(self, measurement):
        """Transform measurement from the queue into something usable by plot()

        must return a dict with keys (at least):
        - 'name' (identifier of sensor)
        - 'values' (iterable of numerical values read by sensor)
        - 'time' (time)

        Subclass to adapt to your application.
        """
        data = {key: measurement[key] for key in ('name', 'values')}
        t_unix = measurement['time (unix)']
        try:
            # works if time is a single value (int or float)
            data['time'] = datetime.fromtimestamp(t_unix, local_timezone)
        except TypeError:
            # works if time is an array
            if pandas_available:
                data['time'] = self._to_datetime_pandas(t_unix)
            else:
                data['time'] = self._to_datetime_numpy(t_unix)

        return data

    def _plot(self, data):
        """Generic plot method that chooses axes depending on data type.

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
            ax.plot(time, value, '.', color=clr)

        # Use Concise Date Formatting for minimal space used on screen by time
        different_types = set(dtypes)
        for dtype in different_types:
            ax = self.axs[dtype]
            ax.xaxis.set_major_locator(self.locator[ax])
            ax.xaxis.set_major_formatter(self.formatter[ax])


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

        update_graph = UpdateGraph(self.graph,
                                   q_plot=self.queues,
                                   e_stop=self.e_stop,
                                   e_close=self.e_stop,
                                   e_graph=self.e_graph,
                                   dt_graph=self.dt_graph)
        update_graph.run()


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
