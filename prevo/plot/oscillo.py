"""Plot data from sensors in oscilloscope-like fashion"""

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
import time

# Non standard imports
import numpy as np
import matplotlib.pyplot as plt

# Local imports
from .general import NumericalGraphBase, UpdateGraphBase


class UpdateGraph(UpdateGraphBase):

    def manage_measurement(self, measurement):

        # The line below allows some sensors to avoid being plotted by reading
        # None when called.
        if measurement is None:
            return

        data = self.graph.format_measurement(measurement)

        self.graph.manage_reference_time(data)
        self.graph.update_current_data(data)

    def after_getting_measurements(self):

        self.graph.update_lines()
        self.graph.update_bars()


class OscilloGraph(NumericalGraphBase):

    def __init__(self, names, data_types, window_width=10, colors=None):
        """Initiate figures and axes for data plot as a function of asked types.

        Input
        -----
        - names: iterable of names of recordings/sensors that will be plotted.
        - data types: dict with the recording names as keys, and the
                      corresponding data types as values.
                      (dict can have more keys than those in 'names')
        - window_width: width (in seconds) of the displayed window
        - colors: optional dict of colors with keys 'fig', 'ax', and the
                    names of the recordings.
        """
        self.window_width = window_width
        self.reference_time = None

        super().__init__(names=names, data_types=data_types, colors=colors)

        self.previous_data = self.create_empty_data()
        self.current_data = self.create_empty_data()

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
        """Generate figure/axes as a function of input data types"""

        n = len(self.all_data_types)
        self.fig, axes = plt.subplots(n, 1)

        # Transform axes into a tuple if only one ax
        try:
            iter(axes)
        except TypeError:
            axes = axes,

        self.axs = {}
        for ax, datatype in zip(axes, self.all_data_types):
            ax.set_ylabel(datatype)
            self.axs[datatype] = ax

    def format_graph(self):
        """Set colors, time formatting, etc."""
        w = self.window_width
        for ax in self.axs.values():
            ax.set_xlim((-0.05 * w, 1.05 * w))
            ax.grid()

        # Initiate line object for each value of each sensor -----------------

        self.lines = {}
        self.lines_list = []

        for name in self.names:

            dtypes = self.data_types[name]
            clrs = self.colors[name]
            self.lines[name] = []

            for dtype, clr in zip(dtypes, clrs):

                # Plot data in correct axis depending on type
                ax = self.axs[dtype]
                line, = ax.plot([], [], '.', color=clr)

                self.lines[name].append(line)
                # Below, used for returning animated artists for blitting
                self.lines_list.append(line)

        # Also initiate line objects for traveling bars ----------------------

        self.create_bars()

    def format_measurement(self, measurement):
        """How to move from measurements from the queue to data useful for plotting.

        Can be subclassed to adapt to various applications.
        """
        return measurement

    @property
    def current_time(self):
        return time.time()

    @property
    def relative_time(self):
        return self.current_time - self.reference_time

    def create_bars(self):
        """Create traveling bars"""
        self.bars = {}
        for dtype, ax in self.axs.items():
            bar = ax.axvline(0, linestyle='-', c='grey', linewidth=4)
            self.bars[dtype] = bar

    def refresh_windows(self):
        """What to do each time the bars exceeed window size"""
        self.previous_data = self.current_data
        self.current_data = self.create_empty_data()
        self.reference_time += self.window_width

    def manage_reference_time(self, data):
        """Define and update reference time if necessary"""
        t = data['time']
        if self.reference_time is None:
            self.reference_time = t  # Take time of 1st data as time 0
        if t > self.reference_time + self.window_width:
            self.refresh_windows()

    def update_current_data(self, data):
        """Store measurement time and values in active data lists."""

        name = data['name']
        rel_time = data['time'] - self.reference_time
        values = data['values']

        self.current_data[name]['times'].append(rel_time)
        for i, value in enumerate(values):
            self.current_data[name]['values'][i].append(value)

    def update_lines(self):

        # Keep only previous drawings after current bar position

        for lines, previous_data, current_data in zip(self.lines.values(),
                                                      self.previous_data.values(),
                                                      self.current_data.values()):

            prev_times = np.array(previous_data['times'], dtype=np.float64)
            curr_times = np.array(current_data['times'], dtype=np.float64)

            condition = (prev_times > self.relative_time)
            times = np.concatenate((curr_times, prev_times[condition]))

            for line, prev_values, curr_values in zip(lines,
                                                      previous_data['values'],
                                                      current_data['values']):

                prev_vals = np.array(prev_values, dtype=np.float64)
                curr_vals = np.array(curr_values, dtype=np.float64)
                values = np.concatenate((curr_vals, prev_vals[condition]))

                line.set_data(times, values)

    @property
    def animated_artists(self):
        return self.lines_list + list(self.bars.values())

    def update_bars(self):
        t = self.relative_time
        for bar in self.bars.values():
            bar.set_xdata(t)

    def run(self, q_plot, e_stop=None, e_close=None, e_graph=None,
            dt_graph=0.02, blit=True):
        """Run live view of oscilloscope with data from queues.

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
        update_oscillo = UpdateGraph(graph=self,
                                     q_plot=q_plot,
                                     e_stop=e_stop,
                                     e_close=e_close,
                                     e_graph=e_graph,
                                     dt_graph=dt_graph,
                                     blit=blit)
        update_oscillo.run()
