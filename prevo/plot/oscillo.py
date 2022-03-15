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

        self.previous_measurements = []
        self.current_measurements = []

        self.reference_time = None

    def create_axes(self):
        self.fig, self.ax = plt.subplots()

    def format_graph(self):
        self.ax.set_xlim((-0.1, self.window_width + 0.1))
        self.ylim = 0, 1
        self.ax.set_ylim(self.ylim)
        self.ax.grid()

    def format_measurement(self, measurement):
        """How to move from measurements from the queue to data useful for plotting."""
        return measurement

    @property
    def current_time(self):
        return time.time()

    @property
    def relative_time(self):
        return self.current_time - self.reference_time

    def plot(self, measurement):

        measurement = self.format_measurement(measurement)

        t = measurement['time']
        value, = measurement['values']

        if self.reference_time is None:
            # Take time of first measurement as time zero
            self.reference_time = t
            self.bar, = self.ax.plot((0, 0), self.ylim, '-', c='grey', linewidth=4)

        if t > self.reference_time + self.window_width:
            # Start new displaying cycle with bar on left of screen

            # Without this, memory keeps building up
            # Tests: 230MB build-up in 5 min without, 14MB buildup with
            for measurement in self.previous_measurements:
                for pt in measurement['pts']:
                    pt.remove()

            self.previous_measurements = self.current_measurements
            self.current_measurements = []
            self.reference_time += self.window_width

        t_relative = t - self.reference_time
        pt, = self.ax.plot(t_relative, value, 'ok')

        measurement['relative time'] = t_relative
        measurement['pts'] = pt,

        self.current_measurements.append(measurement)
        self.update_bar()

    @property
    def animated_artists(self):
        return self.active_pts + [self.bar]

    @property
    def active_pts(self):

        pts = []

        for measurement in self.previous_measurements:
            if measurement['time'] >= self.current_time - self.window_width:
                pts.extend(measurement['pts'])

        for measurement in self.current_measurements:
            pts.extend(measurement['pts'])

        return pts

    def update_bar(self):
        t = self.relative_time
        self.bar.set_xdata((t, t))

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
