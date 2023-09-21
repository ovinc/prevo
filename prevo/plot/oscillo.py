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
from .general import GraphBase, MeasurementFormatter


class OscilloMeasurementFormatter(MeasurementFormatter):
    """Overwrite some formatting methods from the default."""

    def list_of_single_values_to_array(self, datalist):
        """To be able to filter on condition and concatenate"""
        return np.array(datalist, dtype=np.float64)

    def list_of_single_times_to_array(self, timelist):
        """To be able to filter on condition and concatenate"""
        return np.array(timelist, dtype=np.float64)


class OscilloGraph(GraphBase):

    def __init__(self,
                 names,
                 data_types,
                 data_ranges,
                 window_width=10,
                 fig=None,
                 colors=None,
                 legends=None,
                 linestyles=None,
                 linestyle='.',
                 data_as_array=False,
                 measurement_formatter=OscilloMeasurementFormatter()):
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
        - fig (optional): matplotlib figure in which to draw the graph.
        - colors: optional dict of colors with keys 'fig', 'ax', 'bar' and the
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
                         NOTE: data_as array can also be a dict of bools
                         with names as keys if some sensors come as arrays
                         and some not.
        - measurement_formatter: MeasurementFormatter (or subclass) object.
        """
        self.data_ranges = data_ranges
        self.window_width = window_width
        self.reference_time = None

        super().__init__(names=names,
                         data_types=data_types,
                         fig=fig,
                         colors=colors,
                         legends=legends,
                         linestyles=linestyles,
                         linestyle=linestyle,
                         data_as_array=data_as_array,
                         measurement_formatter=measurement_formatter)

        self.create_bars()
        self.previous_data = self.create_empty_data()  # current_data created by the base class

    # ================== Methods subclassed from GraphBase ===================

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
        """Misc. settings for graph (time formatting, limits etc.)"""

        w = self.window_width
        for dtype, ax in self.axs.items():
            ax.set_xlim((-0.001 * w, 1.001 * w))
            ax.set_ylim(self.data_ranges[dtype])
            ax.grid()

    def update_data(self, data):

        tmin, tmax = self.get_time_boundaries(data)

        if self.reference_time is None:
            self.reference_time = tmin   # Take time of 1st data as time 0

        self.update_stored_data(data=data,
                                stored_data=self.current_data)

        # In case measurement arrives late after window has already refreshed,
        # duplicate it to previous data so that it is remains visible
        # This is particularly useful for data arriving as arrays; in which
        # case the array will be duplicated to appear both at the beginning
        # and end of the window when the times in the arrays span values
        # across the window wrapping time.
        if tmin < self.reference_time:
            self.update_stored_data(data=data,
                                    stored_data=self.previous_data)

        # There is no need to do the same for 'future' points that would arrive
        # with tmax > reference_time + window_size, because in
        # principle all data arriving is from the past or present.


    def update(self):
        self.update_lines()
        self.update_bars()
        if self.reference_time and (self.relative_time > self.window_width):
            self.wrap()

    @property
    def animated_artists(self):
        artists = self.lines_list + list(self.bars.values())
        return artists

    # ======================= Other graph init methods =======================

    def create_bars(self):
        """Create traveling bars"""
        self.bars = {}
        for dtype, ax in self.axs.items():
            barcolor = self.colors.get('bar', 'silver')
            bar = ax.axvline(0, linestyle='-', c=barcolor, linewidth=4)
            self.bars[dtype] = bar

    # =============== Methods overriden from the parent class ================

    def on_click():
        """Here turn off autoscale, which can cause problems with blitting."""
        pass

    # ======= Methods that can be subclassed to adapt to applications ========

    def get_time_boundaries(self, data):
        """Subclass if necessary."""
        t = data['time (unix)']
        name = data['name']

        if self.data_as_array[name]:
            return t[0], t[-1]
        else:
            return t, t

    # ========================== Misc. properties ============================

    @property
    def current_time(self):
        return time.time()

    @property
    def relative_time(self):
        return self.current_time - self.reference_time

    # ========================= Graph Update Methods =========================

    def wrap(self):
        """What to do each time the bars exceeed window size"""
        self.previous_data = self.current_data
        self.current_data = self.create_empty_data()
        self.reference_time += self.window_width

    def update_stored_data(self, data, stored_data):
        """Store measurement time and values in active data lists.

        Parameters
        ----------
        data: data as output by format_measurement()
        stored_data: either self.current_data or self.previous_data.
        """
        name = data['name']
        time = data['time (unix)']
        values = data['values']

        stored_data[name]['times'].append(time)
        for i, value in enumerate(values):
            stored_data[name]['values'][i].append(value)

    def update_lines(self):
        """Update line positions with current data."""

        for name in self.lines:

            lines = self.lines[name]
            previous_data = self.previous_data[name]
            current_data = self.current_data[name]

            rel_times = []

            # Avoids problems if no data stored yet
            prev_exists = bool(previous_data['times'])
            curr_exists = bool(current_data['times'])

            if not (prev_exists or curr_exists):
                continue

            if curr_exists:
                curr_times = self.timelist_to_array[name](current_data['times'])
                curr_rel_times = curr_times - self.reference_time
                rel_times.append(curr_rel_times)

            if prev_exists:
                prev_times = self.timelist_to_array[name](previous_data['times'])
                prev_condition = (prev_times + self.window_width > self.current_time)
                prev_rel_times = prev_times[prev_condition] - self.reference_time + self.window_width
                rel_times.append(prev_rel_times)

            rel_times_array = np.concatenate(rel_times)

            for line, prev_values, curr_values in zip(lines,
                                                      previous_data['values'],
                                                      current_data['values']):

                vals = []

                if curr_exists:
                    curr_vals = self.datalist_to_array[name](curr_values)
                    vals.append(curr_vals)

                if prev_exists:
                    prev_vals = self.datalist_to_array[name](prev_values)
                    vals.append(prev_vals[prev_condition])

                values_array = np.concatenate(vals)

                line.set_data(rel_times_array, values_array)

    def update_bars(self):
        if self.reference_time:   # Avoids problems if no data arrived yet
            t = self.relative_time
            for bar in self.bars.values():
                bar.set_xdata(t)
