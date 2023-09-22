"""General tools and base classes for the prevo.plot module."""

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
from threading import Event

# Non standard imports
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib import cm
import tzlocal

# Local imports
from ..misc import get_last_from_queue

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


# How to place elements on window as a function of number of widgets
DISPOSITIONS = {1: (1, 1),
                2: (1, 2),
                3: (1, 3),
                4: (2, 2)}



# Misc =======================================================================


local_timezone = tzlocal.get_localzone()



class MeasurementFormatter:
    """Format lists, arrays etc. for plotting in matplotlib.

    Can be subclassed or replaced to adapt to applications."""

    @staticmethod
    def format_measurement(measurement):
        """Transform measurement from the queue into something usable by manage_data()

        Can be subclassed to adapt to various applications.
        Here, assumes data is incoming in the form of a dictionary with at
        least keys:
        - 'name' (str, identifier of sensor)
        - 'time (unix)' (floar or array of floats)
        - 'values' (iterable of values, or iterable of arrays of values)

        Subclass possible to adapt to applications.
        """
        data = {key: measurement[key] for key in ('name', 'values', 'time (unix)')}
        return data

    # ==== Methods to transform lists into arrays for matplotlib plotting ====

    @staticmethod
    def list_of_single_values_to_array(datalist):
        """How to convert list of single values to a numpy array."""
        return datalist

    @staticmethod
    def list_of_single_times_to_array(timelist):
        """How to convert list of single times to a numpy array."""
        return timelist

    @staticmethod
    def list_of_value_arrays_to_array(datalist):
        """How to convert list of arrays of values to a numpy array."""
        return np.concatenate(datalist)

    @staticmethod
    def list_of_time_arrays_to_array(timelist):
        """How to convert list array of times to a numpy array."""
        return np.concatenate(timelist)

    # ============= Methods to convert unix times into datetimes =============

    @staticmethod
    def to_datetime_datetime(unix_time):
        """Transform single value of unix time into timezone-aware datetime."""
        return datetime.fromtimestamp(unix_time, local_timezone)

    @staticmethod
    def to_datetime_numpy(unix_times):
        """Transform iterable / array of unix times into datetimes.

        Note: this is the fastest method, but the datetimes are in UTC format
              (not local time)
        """
        return (np.array(unix_times) * 1e9).astype('datetime64[ns]')

    @staticmethod
    def to_datetime_pandas(unix_times):
        """Transform iterable / array of datetimes into pandas Series.

        Note: here, the datetimes are in local timezone format, but this is
              slower than the numpy approach.
        """
        # For some reason, it's faster (and more precise) to convert to numpy first
        np_times = (np.array(unix_times) * 1e9).astype('datetime64[ns]')
        pd_times = pd.Series(np_times)
        return pd.to_datetime(pd_times, utc=True).dt.tz_convert(local_timezone)


class GraphBase(ABC):
    """Base class for managing plotting of arbitrary measurement data"""

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
                         bool as True (default False).
                         NOTE: data_as array can also be a dict of bools
                         with names as keys if some sensors come as arrays
                         and some not.
        - time_conversion: how to convert from unix time to datetime for arrays;
                           possible values: 'numpy', 'pandas'.
        - measurement_formatter: MeasurementFormatter (or subclass) object.
        """
        self.names = names
        self.data_types = {name: data_types[name] for name in self.names}
        self.fig = fig
        self.colors = colors
        self.legends = legends if legends is not None else {}
        self.linestyles = linestyles if linestyles is not None else {}
        self.linestyle = linestyle

        self.current_data = self.create_empty_data()

        self.measurement_formatter = measurement_formatter
        self.manage_array_conversion(data_as_array=data_as_array)
        self.manage_time_conversion(time_conversion=time_conversion)

        self.create_axes()
        self.set_colors()
        self.format_graph()
        self.create_lines()
        self.fig.tight_layout()

        # Create onclick callback to activate / deactivate autoscaling
        self.cid = self.fig.canvas.mpl_connect('button_press_event',
                                               self.onclick)

    # ========================== Methods to subclass =========================

    @abstractmethod
    def create_axes(self):
        """To be defined in subclasses. Returns fig, axs"""
        pass

    @abstractmethod
    def format_graph(self):
        """To be defined in subclasses.

        Misc. settings for graph (time formatting, limits etc.)"""
        pass

    @abstractmethod
    def update_data(self, data):
        """Store measurement time and values in active data lists."""
        pass

    @abstractmethod
    def update(self):
        """How to update graph after adding measurements to it (graph.add())."""
        pass

    @property
    def animated_artists(self):
        """Optional property to define for graphs updated with blitting."""
        return ()

    # =========================== Static Plotting methods ===========================

    def add(self, measurement):
        """Add measurement on graph, possibly adding to existing ones."""
        # The line below allows some sensors to avoid being plotted by reading
        # None when called, and also to not consider empty queues.
        if measurement is not None:
            data = self.measurement_formatter.format_measurement(measurement)
            self.update_data(data)

    # ===================== Graph initialization methods =====================

    @property
    def all_data_types(self):
        """Return a set of all datatypes corresponding to the active names."""
        all_types = ()
        for name in self.names:
            data_types = self.data_types[name]
            all_types += data_types
        return set(all_types)

    def set_colors(self):
        """"Define fig/ax colors if supplied"""
        if self.colors is None:
            self.colors = {}
        else:
            figcolor = self.colors.get('fig', 'white')
            self.fig.set_facecolor(figcolor)
            for ax in self.axs.values():
                axcolor = self.colors.get('ax', 'white')
                ax.set_facecolor(axcolor)
                ax.grid()

        missing_color_names = []
        n_missing_colors = 0
        for name, dtypes in self.data_types.items():
            try:
                self.colors[name]
            except (KeyError, TypeError):
                missing_color_names.append(name)
                n_missing_colors += len(dtypes)

        if not n_missing_colors:
            return

        m = cm.get_cmap('tab10', n_missing_colors)
        i = 0
        for name in missing_color_names:
            dtypes = self.data_types[name]
            colors = []
            for _ in dtypes:
                colors.append(m.colors[i])
                i += 1
            self.colors[name] = tuple(colors)

    def create_lines(self):
        """Create lines for each value of each sensor"""
        self.lines = {}
        self.lines_list = []

        for name in self.names:

            dtypes = self.data_types[name]
            clrs = self.colors[name]
            labels = self.legends.get(name, [None] * len(dtypes))
            lstyles = self.linestyles.get(name, [self.linestyle] * len(dtypes))

            self.lines[name] = []

            for dtype, clr, label, lstyle in zip(dtypes, clrs, labels, lstyles):

                # Plot data in correct axis depending on type
                ax = self.axs[dtype]
                line, = ax.plot([], [], lstyle, color=clr, label=label)

                self.lines[name].append(line)
                # Below, used for returning animated artists for blitting
                self.lines_list.append(line)

        if self.legends:
            legend_clr = self.colors.get('legend')
            for ax in self.axs.values():
                ax.legend(loc='lower left', facecolor=legend_clr)

    def create_empty_data(self):
        data = {}
        for name in self.names:
            times = []
            values = []
            for _ in self.data_types[name]:
                values.append([])
            data[name] = {'times': times, 'values': values}
        return data

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

    # ========================== Conversion methods ==========================

    def manage_array_conversion(self, data_as_array):
        """Determine conversion methods from data to arrays"""
        try:
            data_as_array.get   # no error if dict
        except AttributeError:  # it's a bool: put info for all sensors
            self.data_as_array = {name: data_as_array for name in self.names}
        else:
            self.data_as_array = data_as_array

        self.datalist_to_array = {}
        self.timelist_to_array = {}

        for name, data_as_array in self.data_as_array.items():
            if data_as_array:
                self.datalist_to_array[name] = self.measurement_formatter.list_of_value_arrays_to_array
                self.timelist_to_array[name] = self.measurement_formatter.list_of_time_arrays_to_array
            else:
                self.datalist_to_array[name] = self.measurement_formatter.list_of_single_values_to_array
                self.timelist_to_array[name] = self.measurement_formatter.list_of_single_times_to_array

    def manage_time_conversion(self, time_conversion):
        """How to convert input times into datetimes manageable for plotting."""

        time_converters = {
            'datetime': self.measurement_formatter.to_datetime_datetime,
            'numpy': self.measurement_formatter.to_datetime_numpy,
            'pandas': self.measurement_formatter.to_datetime_pandas,
        }

        self.time_converters = {}
        for name in self.names:
            if self.data_as_array[name]:
                self.time_converters[name] = time_converters[time_conversion]
            else:
                self.time_converters[name] = time_converters['datetime']

    # ================= Update graph with data from queue(s) =================

    def run(self,
            queues,
            external_stop=None,
            dt_graph=0.1,
            blit=False):
        """Run live view of plot with data from queues.

        (Convenience method to instantiate a UpdateGraph object)

        Parameters
        ----------
        - queues: iterable of queues to read data from
        - external_stop (optional): external stop request, closes the figure if set
        - dt graph: time interval to update the graph
        - blit: if True, use blitting to speed up the matplotlib animation
        """
        update_graph = UpdateGraph(graph=self,
                                   queues=queues,
                                   external_stop=external_stop,
                                   dt_graph=dt_graph,
                                   blit=blit)
        update_graph.run()

    def close(self):
        """Close matplotlib figure associated with graph"""
        plt.close(self.graph.fig)

class UpdateGraph:

    def __init__(self,
                 graph,
                 queues,
                 external_stop=None,
                 dt_graph=0.1,
                 blit=False):
        """Update plot with data received from a queue.

        INPUTS
        ------
        - graph: object of GraphBase class and subclasses
        - queues: iterable of queues to read data from
        - external_stop: stopping event (threading.Event or equivalent)
                         signaling stopping requested from outside of the class
                         (won't be set or cleared, just monitored)
        - dt_graph: time interval to update the graph
        - blit: if True, use blitting to speed up the matplotlib animation
        """
        self.graph = graph
        self.queues = queues
        self.dt_graph = dt_graph
        self.blit = blit

        self.external_stop = external_stop
        self.internal_stop = Event()

        self.graph.fig.canvas.mpl_connect('close_event', self.on_fig_close)

    def on_fig_close(self, event):
        """What to do when figure is closed."""
        self.stop()

    def plot_new_data(self, i=0):
        """define what to do at each loop of the matplotlib animation."""

        if self.internal_stop.is_set():
            return

        if self.external_stop and self.external_stop.is_set():
            self.stop()
            self.graph.close()

        for queue in self.queues:
            measurement = get_last_from_queue(queue)
            self.graph.add(measurement)

        self.graph.update()

        if self.blit:
            return self.graph.animated_artists

    def run(self):

        # Below, it does not work if there is no value = before the FuncAnimation
        ani = FuncAnimation(fig=self.graph.fig,
                            func=self.plot_new_data,
                            interval=self.dt_graph * 1000,
                            cache_frame_data=False,
                            save_count=0,
                            blit=self.blit)

        plt.show(block=True)  # block=True allows the animation to work even
        # when matplotlib is in interactive mode (plt.ion()).

        return ani

    def stop(self):
        self.internal_stop.set()
