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

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from .general import GraphBase, MeasurementFormatter
from .general import DISPOSITIONS, local_timezone


# =============================== Main classes ===============================


class NumericalGraph(GraphBase):
    def __init__(
        self,
        names,
        data_types,
        fig=None,
        colors=None,
        legends=None,
        linestyles=None,
        linestyle=".",
        data_as_array=False,
        time_conversion="numpy",
        measurement_formatter=MeasurementFormatter(),
    ):
        """Initialize figures and axes for plotting data as a function of types.

        Parameters
        ----------
        names : iterable
            Names of recordings/sensors to be plotted.
        data_types : dict
            Dictionary with recording names as keys and corresponding data types
            as values. Can contain more keys than those in `names`.
        fig : matplotlib.figure.Figure, optional
            Matplotlib figure in which to draw the graph.
        colors : dict, optional
            Dictionary of colors with keys 'fig', 'ax', and recording names.
        legends : dict, optional
            Dictionary of legend names (iterable) for all channels of each sensor,
            keyed by recording names.
        linestyles : dict, optional
            Dictionary of linestyles (iterable) to distinguish channels and
            sensors, keyed by recording names. If None, all lines use the
            `linestyle` parameter. If only some recordings are specified, others
            use the default or `linestyle`.
        linestyle : str, default='.'
            Matplotlib linestyle (e.g., '.', '-', '.-').
        data_as_array : bool, default=False
            If sensors return arrays of values for different times, set to True.
        time_conversion : str, default='numpy'
            Method to convert Unix time to datetime for arrays. Possible: 'numpy',
            'pandas'.
        measurement_formatter : MeasurementFormatter, optional
            MeasurementFormatter (or subclass) object.
        """
        super().__init__(
            names=names,
            data_types=data_types,
            fig=fig,
            colors=colors,
            legends=legends,
            linestyles=linestyles,
            linestyle=linestyle,
            data_as_array=data_as_array,
            time_conversion=time_conversion,
            measurement_formatter=measurement_formatter,
        )

    # ================== Methods subclassed from GraphBase ===================

    def create_axes(self):
        """Generate figure/axes as a function of input data types"""

        n = len(self.all_data_types)
        if n > 4:
            msg = f"Mode combination {self.all_data_types} not supported yet"
            raise Exception(msg)

        n1, n2 = DISPOSITIONS[n]  # dimensions of grid to place elements

        if self.fig is None:
            self.fig = plt.figure()

        width = 5 * n2
        height = 3 * n1
        self.fig.set_figheight(height)
        self.fig.set_figwidth(width)

        self.axs = {}
        for i, datatype in enumerate(self.all_data_types):
            ax = self.fig.add_subplot(n1, n2, i + 1)
            ax.set_ylabel(datatype)
            self.axs[datatype] = ax

    def format_graph(self):
        """Misc. settings for graph (time formatting, limits etc.)"""
        self.locators = {}  # For concise formatting of time -----------------
        self.formatters = {}
        for ax in self.axs.values():
            locator = mdates.AutoDateLocator(tz=local_timezone)
            self.locators[ax] = locator
            self.formatters[ax] = mdates.ConciseDateFormatter(locator, tz=local_timezone)

    def update_data(self, data):
        """Store measurement time and values in active data lists."""

        name = data["name"]
        values = data["values"]
        time = self.time_converters[name](data["time (unix)"])

        self.current_data[name]["times"].append(time)
        for i, value in enumerate(values):
            self.current_data[name]["values"][i].append(value)

    def update(self):
        self.update_lines()
        self.update_time_formatting()

    @property
    def animated_artists(self):
        return self.lines_list

    # ======================== Local update methods ==========================

    def update_lines(self):
        """Update line positions with current data."""

        for name in self.names:
            lines = self.lines[name]
            current_data = self.current_data[name]

            if current_data["times"]:  # Avoids problems if no data stored yet
                times = self.timelist_to_array[name](current_data["times"])

                for line, curr_values in zip(lines, current_data["values"]):
                    values = self.datalist_to_array[name](curr_values)
                    line.set_data(times, values)

    def update_time_formatting(self):
        """Use Concise Date Formatting for minimal space used on screen by time"""
        for ax in self.axs.values():
            ax.xaxis.set_major_locator(self.locators[ax])
            ax.xaxis.set_major_formatter(self.formatters[ax])
            # Lines below are needed for autoscaling to work
            ax.relim()
            ax.autoscale_view(tight=True, scalex=True, scaley=True)
