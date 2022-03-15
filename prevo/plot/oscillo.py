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
import matplotlib
matplotlib.use('Qt5Agg')

import matplotlib.pyplot as plt

# Local imports
from .general import NumericalGraphBase, UpdateGraph


class OscilloGraph(NumericalGraphBase):

    def __init__(self, names, data_types, window_width=10, colors=None):
        """Initiate figures and axes for data plot as a function of asked types.

        Input
        -----
        - names: iterable of names of recordings/sensors that will be plotted.
        - data types: dict with the recording names as keys, and the
                        corresponding data types as values.
        - window_width: width (in seconds) of the displayed window
        - colors: optional dict of colors with keys 'fig', 'ax', and the
                    names of the recordings.
        """
        self.window_width = window_width

        super().__init__(names=names, data_types=data_types, colors=colors)

        self.previous_drawings = []
        self.current_drawings = []

        self.reference_time = None

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
        self.ylim = 0, 1
        for ax in self.axs.values():
            ax.set_xlim((-0.1, self.window_width + 0.1))
            ax.set_ylim(self.ylim)
            ax.grid()

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
            bar, = ax.plot((0, 0), self.ylim, '-', c='grey', linewidth=4)
            self.bars[dtype] = bar

    def refresh_windows(self):
        """What to do each time the bars exceeed window size"""

        # Without this, memory keeps building up
        # Tests: 230MB build-up in 5 min without, 14MB buildup with
        for drawing in self.previous_drawings:
            for pt in drawing['pts']:
                pt.remove()

        self.previous_drawings = self.current_drawings
        self.current_drawings = []
        self.reference_time += self.window_width

    def plot(self, measurement):
        """Generic plot method that chooses axes depending on data type.

        measurement is an object from the data queue.
        """
        # The line below allows some sensors to avoid being plotted by reading
        # None when called.
        if measurement is None:
            return

        data = self.format_measurement(measurement)

        name = data['name']
        values = data['values']
        t = data['time']

        dtypes = self.data_types[name]  # all data types for this specific signal
        clrs = self.colors[name]

        if self.reference_time is None:
            self.reference_time = t  # Take time of 1st data as time 0
            self.create_bars()

        if t > self.reference_time + self.window_width:
            self.refresh_windows()

        t_relative = t - self.reference_time

        pts = []
        for value, dtype, clr in zip(values, dtypes, clrs):
            ax = self.axs[dtype]  # plot data in correct axis depending on type
            pt, = ax.plot(t_relative, value, '.', color=clr)
            pts.append(pt)

        drawing = {'time': t,
                   'relative time': t_relative,
                   'pts': pts}

        self.current_drawings.append(drawing)
        self.update_bars(dtypes=dtypes)

    @property
    def animated_artists(self):
        return self.active_pts + list(self.bars.values())

    @property
    def active_pts(self):

        pts = []

        for drawing in self.previous_drawings:
            if drawing['time'] >= self.current_time - self.window_width:
                pts.extend(drawing['pts'])

        for drawing in self.current_drawings:
            pts.extend(drawing['pts'])

        return pts

    def update_bars(self, dtypes):
        t = self.relative_time
        for dtype in dtypes:
            self.bars[dtype].set_xdata((t, t))

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
