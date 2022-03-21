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

    def _manage_data(self, data):
        self.graph.manage_reference_time(data)
        self.graph.update_current_data(data)

    def after_getting_measurements(self):
        self.graph.update_lines()
        self.graph.update_bars()


class OscilloGraph(NumericalGraphBase):

    def __init__(self,
                 names,
                 data_types,
                 data_ranges,
                 window_width=10,
                 colors=None,
                 linestyle='.-',
                 data_as_array=False):
        """Initiate figures and axes for data plot as a function of asked types.

        Input
        -----
        - names: iterable of names of recordings/sensors that will be plotted.
        - data_types: dict with the recording names as keys, and the
                      corresponding data types as values.
                      (dict can have more keys than those in 'names')
        - data_ranges: dict with the possible data types as keys, and the
                       corresponding range of values expected for this data
                       as values. Used to set ylims of graph initially.
                      (dict can have more keys than actual data types used)
        - window_width: width (in seconds) of the displayed window
        - colors: optional dict of colors with keys 'fig', 'ax', 'bar' and the
                  names of the recordings.
        - linestyle: Matplotlib linestyle (e.g. '.', '-', '.-' etc.)
        - data_as_array: if sensors return arrays of values for different times
                         instead of values for a single time, put this
                         bool as True (default False)
        """
        self.data_ranges = data_ranges
        self.window_width = window_width
        self.reference_time = None

        super().__init__(names=names,
                         data_types=data_types,
                         colors=colors,
                         linestyle=linestyle,
                         data_as_array=data_as_array)

        self.current_data = self.create_empty_data()
        self.previous_data = self.create_empty_data()

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
        for dtype, ax in self.axs.items():
            ax.set_xlim((-0.01 * w, 1.01 * w))
            ax.set_ylim(self.data_ranges[dtype])
            ax.grid()

        self.create_lines()
        self.create_bars()

    def format_measurement(self, measurement):
        """How to move from measurements from the queue to data useful for plotting.

        Can be subclassed to adapt to various applications.
        Here, assumes data is incoming in the form of a dictionary with at
        least keys:
        - 'name'
        - 'time (unix)'
        - 'values'
        """
        return measurement

    def on_click():
        """Here turn off autoscale, which can cause problems with blitting."""
        pass

    def _list_of_single_values_to_array(self, datalist):
        """How to convert list of single values to a numpy array.

        This is to transform measurements stored in self.current_values
        into an array manageable by matplotlib for plotting.

        Can be subclassed to adapt to applications."""
        return np.array(datalist, dtype=np.float64)

    def _list_of_single_times_to_array(self, timelist):
        """How to convert list of single times to a numpy array.

        This is to transform measurements stored in self.current_values
        into an array manageable by matplotlib for plotting.

        Can be subclassed to adapt to applications."""
        return np.array(timelist, dtype=np.float64)

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
            barcolor = self.colors.get('bar', 'silver')
            bar = ax.axvline(0, linestyle='-', c=barcolor, linewidth=4)
            self.bars[dtype] = bar

    def refresh_windows(self):
        """What to do each time the bars exceeed window size"""
        self.previous_data = self.current_data
        self.current_data = self.create_empty_data()
        self.reference_time += self.window_width

    def manage_reference_time(self, data):
        """Define and update reference time if necessary"""
        t = data['time (unix)']
        if self.reference_time is None:
            self.reference_time = t  # Take time of 1st data as time 0
        if t > self.reference_time + self.window_width:
            self.refresh_windows()

    def update_current_data(self, data):
        """Store measurement time and values in active data lists."""

        name = data['name']
        rel_time = data['time (unix)'] - self.reference_time
        values = data['values']

        self.current_data[name]['times'].append(rel_time)
        for i, value in enumerate(values):
            self.current_data[name]['values'][i].append(value)

    def update_lines(self):
        """Update line positions with current data."""

        # Keep only previous drawings after current bar position

        for lines, previous_data, current_data in zip(self.lines.values(),
                                                      self.previous_data.values(),
                                                      self.current_data.values()):

            prev_times = self.timelist_to_array(previous_data['times'])
            curr_times = self.timelist_to_array(current_data['times'])

            condition = (prev_times > self.relative_time)
            times = np.concatenate((curr_times, prev_times[condition]))

            for line, prev_values, curr_values in zip(lines,
                                                      previous_data['values'],
                                                      current_data['values']):

                prev_vals = self.datalist_to_array(prev_values)
                curr_vals = self.datalist_to_array(curr_values)
                values = np.concatenate((curr_vals, prev_vals[condition]))

                line.set_data(times, values)

    def update_bars(self):
        t = self.relative_time
        for bar in self.bars.values():
            bar.set_xdata(t)

    @property
    def animated_artists(self):
        return self.lines_list + list(self.bars.values())

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
