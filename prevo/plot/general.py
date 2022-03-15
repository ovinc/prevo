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
import matplotlib
matplotlib.use('Qt5Agg')

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib import cm


# ----------------------------------------------------------------------------


class GraphBase(ABC):
    """Base class for managing plotting of arbitrary measurement data"""

    @abstractmethod
    def format_measurement(self, measurement):
        """Transform measurement from the queue into something usable by plot()

        must return a dict with keys (at least):
        - 'name' (identifier of sensor)
        - 'values' (iterable of numerical values read by sensor)
        - 'time' (time)

        Subclass to adapt to your application.
        """
        pass

    @abstractmethod
    def plot(self, measurement):
        """Plot individual measurement on existing graph.

        Uses output of self.format_measurement()
        """
        pass

    @property
    def animated_artists(self):
        """Optional property to define for graphs updated with blitting."""
        return ()


class NumericalGraphBase(GraphBase):

    def __init__(self, names, data_types, colors=None):
        """Initiate figures and axes for data plot as a function of asked types.

        Input
        -----
        - names: iterable of names of recordings/sensors that will be plotted.
        - data types: dict with the recording names as keys, and the
                        corresponding data types as values.
        - colors: optional dict of colors with keys 'fig', 'ax', and the
                    names of the recordings.
        """
        self.names = names
        self.data_types = data_types
        self.colors = colors

        self.create_axes()
        self.format_graph()
        self.set_colors()
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

    def set_colors(self):
        """"Define fig/ax colors if supplied"""
        if self.colors is None:
            self.colors = {}
        else:
            self.fig.set_facecolor(self.colors['fig'])
            for ax in self.axs.values():
                ax.set_facecolor(self.colors['ax'])
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

        m = cm.get_cmap('tab20', n_missing_colors)
        i = 0
        for name in missing_color_names:
            dtypes = self.data_types[name]
            colors = []
            for _ in dtypes:
                colors.append(m.colors[i])
                i += 1
            self.colors[name] = tuple(colors)

    def create_axes(self):
        """To be defined in subclasses. Returns fig, axs"""
        pass

    def format_graph(self):
        """To be defined in subclasses."""
        pass


class UpdateGraph:

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
        - dt graph: time interval to update the graph
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

        for queue in self.q_plot.values():
            while True:
                try:
                    measurement = queue.get(timeout=0)
                except Empty:
                    break
                else:
                    self.graph.plot(measurement)

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

        plt.show(block=True)  # block=True allow the animation to work even
        # when matplotlib is in interactive mode (plt.ion()).

        return ani
