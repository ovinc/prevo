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
from abc import ABC, abstractmethod
from threading import Event, Thread
from queue import Queue
from pathlib import Path

# Non standard imports
import tzlocal
import matplotlib

matplotlib.use('Qt5Agg')

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.animation import FuncAnimation
import oclock

from .record import SensorError

# The two lines below have been added following a console FutureWarning:
# "Using an implicitly registered datetime converter for a matplotlib plotting
# method. The converter was registered by pandas on import. Future versions of
# pandas will require you to explicitly register matplotlib converters."
try:
    from pandas.plotting import register_matplotlib_converters
    register_matplotlib_converters()
except ModuleNotFoundError:
    pass


class GraphBase(ABC):
    """Base class for managing plotting of arbitrary measurement data"""

    @abstractmethod
    def plot(self, measurement):
        """Plot individual measurement on existing graph."""
        pass

    @abstractmethod
    def update_plot(self, e_graph, e_close, e_stop, q_plot, timer=None):
        """Animation function to plot data received from queues.

        INPUTS
        ------
        - e_graph is set when the graph is activated
        - e_close is set when the figure has been closed
        - e_stop is set when there is an external stop request.
        - q_plot: dict {name: queue} with sensor names and data queues
        - timer is an optional external timer that gets deactivated here if
          figure is closed
        """
        pass


class NumericalGraph(GraphBase):

    def __init__(self, names, data_types, colors=None, dt_graph=1):
        """Initiate figures and axes for data plot as a function of asked types.

        Input
        -----
        - names: iterable of names of recordings/sensors that will be plotted.
        - 'data types': dict with the recording names as keys, and the
                        corresponding data types as values.
        - 'colors': optional dict of colors with keys 'fig', 'ax', and the
                    names of the recordings.
        - 'dt graph': time interval to update the graph
                      (only if update_plot is used)
        """
        self.names = names
        self.data_types = data_types
        self.colors = colors
        self.dt_graph = dt_graph

        self.timezone = tzlocal.get_localzone()

        self.fig, self.axs = self.create_axes()

        self.format_graph()

        # Create onclick callback to activate / deactivate autoscaling
        self.cid = self.fig.canvas.mpl_connect('button_press_event',
                                               self.onclick)

    def create_axes(self):
        """Generate figure/axes as a function of input data types"""

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

        return fig, axs

    def format_graph(self):
        """Set colors, time formatting, etc."""

        # Colors -------------------------------------------------------------

        if self.colors is not None:

            self.fig.set_facecolor(self.colors['fig'])

            for ax in self.axs.values():
                ax.set_facecolor(self.colors['ax'])
                ax.grid()

        else:

            self.colors = {name: None for name in self.names}

        # Concise formatting of time -----------------------------------------

        self.locator = {}
        self.formatter = {}

        for ax in self.axs.values():
            self.locator[ax] = mdates.AutoDateLocator(tz=self.timezone)
            self.formatter[ax] = mdates.ConciseDateFormatter(self.locator,
                                                             tz=self.timezone)

        # Finalize figure ----------------------------------------------------

        self.fig.tight_layout()

    # ============================ MISC. methods =============================

    @property
    def all_data_types(self):
        """Return a set of all datatypes corresponding to the active names."""
        all_types = ()
        for name in self.names:
            data_types = self.data_types[name]
            all_types += data_types
        return set(all_types)

    @staticmethod
    def onclick(event):
        """Activate/deactivate autoscale by clicking to allow for data inspection.

        - Left click (e.g. when zooming, panning, etc.): deactivate autoscale
        - Right click: reactivate autoscale.
        """
        ax = event.inaxes
        if ax is None:
            pass
        elif event.button == 1:                        # left click
            ax.axes.autoscale(False, axis='both')
        elif event.button == 3:                        # right click
            ax.axes.autoscale(True, axis='both')
        else:
            pass

    # ============================= Main methods =============================

    def plot(self, measurement):
        """Generic plot method that chooses axes depending on data type.

        measurement is an object of Measurement() or SavedMeasurment() classes
        """
        # The line below allows some sensors to avoid being plotted by reading
        # None when called.
        if measurement is None:
            return

        measurement.format_for_plot()

        name = measurement.name
        values = measurement.values
        t = measurement.time

        dtypes = self.data_types[name]  # all data types for this specific signal
        clrs = self.colors[name]

        for value, dtype, clr in zip(values, dtypes, clrs):
            ax = self.axs[dtype]  # plot data in correct axis depending on type
            ax.plot(t, value, '.', color=clr)

        # Use Concise Date Formatting for minimal space used on screen by time
        different_types = set(dtypes)
        for dtype in different_types:
            ax = self.axs[dtype]
            ax.xaxis.set_major_locator(self.locator[ax])
            ax.xaxis.set_major_formatter(self.formatter[ax])

    def update_plot(self, e_graph, e_close, e_stop, q_plot, timer=None):
        """Threaded function to plot data from data received in a queue.

        INPUTS
        ------
        - e_graph is set when the graph is activated
        - e_close is set when the figure has been closed
        - e_stop is set when there is an external stop request.
        - q_plot: dict {name: queue} with sensor names and data queues
        - timer is an optional external timer that gets deactivated here if
        figure is closed

        Attention, if the figure is closed, the e_close event is triggered by
        update_plot, so do not put in e_stop a threading event that is supposed
        to stay alive even if the figure gets closed. Rather, use the e_stop
        event.

        Note: any request to update_plot when a graph is already active is ignored
        because update_plot is blocking (due to the plt.show() after FuncAnimation).
        """
        def on_fig_close(event):
            """When figure is closed, set threading events accordingly."""
            e_close.set()
            e_graph.clear()
            if timer is not None:
                timer.stop()

        # Connect a figure close event to the close() function above
        self.fig.canvas.mpl_connect('close_event', on_fig_close)

        def plot_new_data(i):
            """define what to do at each loop of the matplotlib animation."""

            for queue in q_plot.values():
                while queue.qsize() > 0:
                    measurement = queue.get()
                    self.plot(measurement)

            if e_stop.is_set():
                plt.close(self.fig)
                # since figure is closed, e_close and e_graph are taken care of
                # by the on_fig_close() function

        # Below, it does not work if there is no value = before the FuncAnimation
        ani = FuncAnimation(self.fig, plot_new_data,
                            interval=self.dt_graph * 1000,
                            cache_frame_data=False)

        plt.show(block=True)  # block=True allow the animation to work even
        # when matplotlib is in interactive mode (plt.ion()).

        return ani


# ============== Classes using Graph-like objects to plot data ===============


# ------------------------------- Static graph -------------------------------


class PlotSavedData:
    """Class to create graphs from saved data."""

    def __init__(self, names, graph, SavedMeasurement, file_names, path='.'):
        """Parameters:

        - names: names of sensors/recordings to consider
        - graph: object of GraphBase class and subclasses
        - SavedMeasurement: Measurement class that manages data loading
                            must have (name, filename, path) as arguments
                            and must define load() and format_for_plot()
                            (see measurements.py)
        - file_names: dict {name: filename (str)} of files containing data
        - path: directory in which data is saved
        """
        self.names = names
        self.graph = graph
        self.SavedMeasurement = SavedMeasurement
        self.file_names = file_names
        self.path = Path(path)

    def show(self):
        """Static plot of saved data"""
        for name in self.names:
            measurement = self.SavedMeasurement(name,
                                                filename=self.file_names[name],
                                                path=self.path)
            measurement.load()
            self.graph.plot(measurement)
        self.graph.fig.tight_layout()
        plt.show(block=False)


# ------------------------------ Updated graphs ------------------------------


class PlotUpdatedData:
    """Class to initiate and manage periodic reading of queues to plot data.

    Is subclassed to define get_data(), which indicates how to get the data
    (e.g. from live sensors, or from reading a file, etc.)
    """

    def __init__(self, graph, dt_data=1):
        """Parameters:

        - graph: object of GraphBase class and subclasses
        - dt_data is how often (in s) the loop checks for (or gets) new data.
        """
        self.graph = graph
        self.timer = oclock.Timer(interval=dt_data, name='Data Update')

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

        # update_plot is inherited later from the Graph-like classes
        self.graph.update_plot(e_graph=self.e_graph, e_close=self.e_stop,
                               e_stop=self.e_stop, q_plot=self.queues,
                               timer=self.timer)
        # e_stop two times, because we want a figure closure event to also
        # trigger stopping of the recording process here.


class PlotLiveSensors(PlotUpdatedData):
    """Create live graph by reading the sensors directly."""

    def __init__(self, names, graph, Sensors, LiveMeasurement, dt_data=1):
        """Parameters:

        - names: names of sensors/recordings to consider
        - graph: object of GraphBase class and subclasses
        - Sensors: dict{name: Sensor class}
        - LiveMeasurement: Measurement class that manages live data formatting
                           must have (name, data) as arguments and must
                           a format_for_plot() method.
                           (see measurements.py)
        - dt_data: how often (in s) sensors are probed"""
        self.names = names
        self.Sensors = Sensors
        self.LiveMeasurement = LiveMeasurement

        super().__init__(graph=graph, dt_data=dt_data)

    def get_data(self, name):
        """Check if new data is read by sensor, and put it in data queue."""
        self.timer.reset()
        Sensor = self.Sensors[name]

        with Sensor() as sensor:

            while not self.e_stop.is_set():
                try:
                    data = sensor.read()
                except SensorError:
                    pass
                else:
                    measurement = self.LiveMeasurement(name, data)
                    self.queues[name].put(measurement)
                    self.timer.checkpt()


class PlotSavedDataUpdated(PlotUpdatedData, PlotSavedData):
    """Extends PlotSavedData to be able to periodically read file to update."""

    def __init__(self, names, graph, SavedMeasurement, file_names,
                 path='.', dt_data=1):
        """Parameters:

        - names: names of sensors/recordings to consider
        - graph: object of GraphBase class and subclasses
        - SavedMeasurement: Measurement class that manages data loading
                            must have (name, filename, path) as arguments and
                            must define load(), format_for_plot() and
                            number_of_measurements() methods
                            (see measurements.py)
        - file_names: dict {name: filename (str)} of files containing data
        - path: directory in which data is saved
        - dt_data: how often (in s) the files are checked for updates.
        """
        PlotSavedData.__init__(self,
                               names=names,
                               graph=graph,
                               SavedMeasurement=SavedMeasurement,
                               file_names=file_names,
                               path=path)

        PlotUpdatedData.__init__(self,
                                 graph=graph,
                                 dt_data=dt_data)

    def get_data(self, name):
        """Check if new data is added to file, and put it in data queue."""
        self.timer.reset()

        measurement = self.SavedMeasurement(name,
                                            filename=self.file_names[name],
                                            path=self.path)

        n0 = measurement.number_of_measurements()

        while not self.e_stop.is_set():

            n = measurement.number_of_measurements()

            if n > n0:
                measurement.load(nrange=(n0 + 1, n))
                if measurement.data is not None:
                    self.queues[name].put(measurement)
                    n0 = n

            self.timer.checkpt()
