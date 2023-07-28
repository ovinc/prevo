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
from queue import Empty

# Non standard imports
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib import cm


# ----------------------------------------------------------------------------


class GraphBase(ABC):
    """Base class for managing plotting of arbitrary measurement data"""

    @abstractmethod
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
        pass

    def _plot(self, data):
        """Plot individual measurement on existing graph.

        Uses output of self.format_measurement() (data)
        To subclass.
        """
        pass

    def plot(self, measurement):
        """Wrapper around _plot()."""
        # The line below allows some sensors to avoid being plotted by reading
        # None when called.
        if measurement is None:
            return

        data = self.format_measurement(measurement)
        self._plot(data)

    @property
    def animated_artists(self):
        """Optional property to define for graphs updated with blitting."""
        return ()


class NumericalGraphBase(GraphBase):

    def __init__(self,
                 names,
                 data_types,
                 colors=None,
                 legends=None,
                 linestyles=None,
                 linestyle='.',
                 data_as_array=False):
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
                         bool as True (default False).
                         NOTE: data_as array can also be a dict of bools
                         with names as keys if some sensors come as arrays
                         and some not.
        """
        self.names = names
        self.data_types = {name: data_types[name] for name in self.names}
        self.colors = colors
        self.legends = legends if legends is not None else {}
        self.linestyles = linestyles if linestyles is not None else {}
        self.linestyle = linestyle

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
                self.datalist_to_array[name] = self._list_of_value_arrays_to_array
                self.timelist_to_array[name] = self._list_of_time_arrays_to_array
            else:
                self.datalist_to_array[name] = self._list_of_single_values_to_array
                self.timelist_to_array[name] = self._list_of_single_times_to_array

        self.create_axes()
        self.set_colors()
        self.format_graph()
        self.fig.tight_layout()

        # Create onclick callback to activate / deactivate autoscaling
        self.cid = self.fig.canvas.mpl_connect('button_press_event',
                                               self.onclick)

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

    def _list_of_single_values_to_array(self, datalist):
        """How to convert list of single values to a numpy array.

        This is to transform measurements stored in self.current_values
        into an array manageable by matplotlib for plotting.

        Can be subclassed to adapt to applications."""
        return datalist

    def _list_of_single_times_to_array(self, timelist):
        """How to convert list of single times to a numpy array.

        This is to transform measurements stored in self.current_values
        into an array manageable by matplotlib for plotting.

        Can be subclassed to adapt to applications."""
        return timelist

    def _list_of_value_arrays_to_array(self, datalist):
        """How to convert list of arrays of values to a numpy array.

        This is to transform measurements stored in self.current_values
        into an array manageable by matplotlib for plotting.

        Can be subclassed to adapt to applications."""
        return np.concatenate(datalist)

    def _list_of_time_arrays_to_array(self, timelist):
        """How to convert list array of times to a numpy array.

        This is to transform measurements stored in self.current_values
        into an array manageable by matplotlib for plotting.

        Can be subclassed to adapt to applications."""
        return np.concatenate(timelist)

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
            for ax in self.axs.values():
                ax.legend(loc='lower left')

    def create_empty_data(self):
        data = {}
        for name in self.names:
            times = []
            values = []
            for _ in self.data_types[name]:
                values.append([])
            data[name] = {'times': times, 'values': values}
        return data

    def create_axes(self):
        """To be defined in subclasses. Returns fig, axs"""
        pass

    def format_graph(self):
        """To be defined in subclasses."""
        pass


class UpdateGraphBase:

    def __init__(self, graph, q_plot,
                 e_stop=None, e_close=None, e_graph=None,
                 dt_graph=1, blit=False):
        """Update plot with data received from a queue.

        INPUTS
        ------
        - graph: object of GraphBase class and subclasses
        - q_plot: dict {name: queue} with sensor names and data queues
        - e_stop (optional): external stop request, closes the figure if set
        - e_close (optional) is set when the figure has been closed
        - e_graph (optional) is set when the graph is activated
        - dt_graph: time interval to update the graph
        - blit: if True, use blitting to speed up the matplotlib animation

        Attention, if the figure is closed, the e_close event is triggered so
        do not put in e_close a threading event that is supposed to stay alive
        even if the figure gets closed. Rather, use the e_stop event.
        """
        self.graph = graph
        self.q_plot = q_plot
        self.e_stop = e_stop
        self.e_close = e_close
        self.e_graph = e_graph
        self.dt_graph = dt_graph
        self.blit = blit

        self.graph.fig.canvas.mpl_connect('close_event', self.on_fig_close)

    def on_fig_close(self, event):
        """When figure is closed, set threading events accordingly."""
        if self.e_close:
            self.e_close.set()
        if self.e_graph:
            self.e_graph.clear()

    def plot_new_data(self, i):
        """define what to do at each loop of the matplotlib animation."""

        if self.e_stop:
            if self.e_stop.is_set():
                plt.close(self.graph.fig)
                # since figure is closed, e_close and e_graph are taken care of
                # by the on_fig_close() function

        self.before_getting_measurements()

        for queue in self.q_plot.values():
            while True:
                try:
                    measurement = queue.get(timeout=0)
                except Empty:
                    break
                else:
                    self.manage_measurement(measurement)

        self.after_getting_measurements()

        if self.blit:
            return self.graph.animated_artists

    def _manage_data(self, data):
        """What to do with individual measurements coming from live data.

        (Measurement already formatted into data by format_measurement())
        Define in subclass
        """
        pass

    def manage_measurement(self, measurement):
        """Wrapper around _manage_data()."""
        # The line below allows some sensors to avoid being plotted by reading
        # None when called.
        if measurement is None:
            return

        data = self.graph.format_measurement(measurement)
        self._manage_data(data)

    def before_getting_measurements(self):
        """Anything to do before measurements from queue have been processed.

        Define in subclass (optional)
        """
        pass

    def after_getting_measurements(self):
        """Anything to do when all measurements from queue have been processed.

        (i.e. manage_measurement() has been called for all elements in queue.)
        Define in subclass (optional)
        """
        pass

    def run(self):

        # Below, it does not work if there is no value = before the FuncAnimation
        ani = FuncAnimation(fig=self.graph.fig,
                            func=self.plot_new_data,
                            interval=self.dt_graph * 1000,
                            cache_frame_data=False,
                            save_count=0,
                            blit=self.blit)

        plt.show(block=True)  # block=True allow the animation to work even
        # when matplotlib is in interactive mode (plt.ion()).

        return ani
