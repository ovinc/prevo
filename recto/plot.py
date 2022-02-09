"""Plot data from sensors (from live measurements or saved data)."""

# Standard library imports
from threading import Event, Thread
from queue import Queue
from pathlib import Path

# Non standard imports
import matplotlib
matplotlib.use('Qt5Agg')

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.animation import FuncAnimation
import oclock

from tzlocal import get_localzone

# The two lines below have been added following a console FutureWarning:
# "Using an implicitly registered datetime converter for a matplotlib plotting
# method. The converter was registered by pandas on import. Future versions of
# pandas will require you to explicitly register matplotlib converters."
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()


class GraphBase:

    def __init__(self, names, config):
        """Initiate figures and axes for data plot as a function of asked types.

        Input
        -----
        names: iterable of names of recordings/sensors that will be plotted.
        config: dict of configuration; must contain at least the keys:
                    - 'colors': dict of colors with keys 'fig', 'ax',
                       and the names of the recordings
                    - 'data types': dict with the recording names as keys,
                       and the corresponding data types as values.
                    - 'dt graph': time interval to update the graph
                      (only if data_plot is used)
        """
        self.names = names
        self.config = config
        self.timezone = get_localzone()

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

        # Set appearance of graph --------------------------------------------

        fig.set_facecolor(config['colors']['fig'])

        for ax in axes:  # Set appearance of ticks and background for all axes.
            ax.set_facecolor(config['colors']['ax'])
            ax.grid()

        # Associate axes to types --------------------------------------------

        axs = {}
        for ax, datatype in zip(axes, self.all_data_types):
            ax.set_ylabel(datatype)
            axs[datatype] = ax

        # Concise formatting of time -----------------------------------------

        self.locator = {}
        self.formatter = {}

        for ax in axes:
            self.locator[ax] = mdates.AutoDateLocator(tz=self.timezone)
            self.formatter[ax] = mdates.ConciseDateFormatter(self.locator,
                                                             tz=self.timezone)

        # Generate useful attributes -----------------------------------------

        self.fig = fig
        self.axs = axs

        # Finalize figure and add mouse event callbacks ----------------------

        self.fig.tight_layout()
        self.cid = self.fig.canvas.mpl_connect('button_press_event', self.onclick)

    # ============================ MISC. methods =============================

    @property
    def all_data_types(self):
        """Return a set of all datatypes corresponding to the active names."""
        all_types = ()
        for name in self.names:
            data_types = self.config['data types'][name]
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

        types = self.config['data types'][name]  # all data types for this specific signal
        clrs = self.config['colors'][name]

        for value, dtype, clr in zip(values, types, clrs):
            ax = self.axs[dtype]  # plot data in correct axis depending on type
            ax.plot(t, value, '.', color=clr)

        # Use Concise Date Formatting for minimal space used on screen by time
        different_types = set(types)
        for dtype in different_types:
            ax = self.axs[dtype]
            ax.xaxis.set_major_locator(self.locator[ax])
            ax.xaxis.set_major_formatter(self.formatter[ax])

    def data_plot(self, e_graph, e_close, e_stop, q, timer=None):
        """Threaded function to plot data from data received in a queue.

        INPUTS
        ------
        - g: object from the Graph class
        - e_graph is set when the graph is activated
        - e_close is set when the figure has been closed
        - e_stop is set when there is an external stop request.
        - q is the name of the data queue from which data arrives
        - timer is an optional external timer that gets deactivated here if
        figure is closed

        Attention, if the figure is closed, the e_close event is triggered by
        data_plot, so do not put in e_stop a threading event that is supposed
        to stay alive even if the figure gets closed. Rather, use the e_stop
        event.

        Note: any request to data_plot when a graph is already active is ignored
        because data_plot is blocking (due to the plt.show() after FuncAnimation).
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

            while q.qsize() > 0:
                measurement = q.get()
                self.plot(measurement)

            if e_stop.is_set():
                plt.close(self.fig)
                # since figure is closed, e_close and e_graph are taken care of
                # by the on_fig_close() function

        # Below, it does not work if there is no value = before the FuncAnimation
        dt = self.config['dt graph'] * 1000
        ani = FuncAnimation(self.fig, plot_new_data, interval=dt,
                            cache_frame_data=False)
        plt.show(block=True)

        return ani


class SavedGraph(GraphBase):
    """Class to create graphs from saved data."""

    def __init__(self, names, config, path='.'):
        """Init Graph. See GraphBase help for names, config parameters.

        Additional parameters compared to GraphBase:
        - path: optional parameters to locate saved data (not necessary when
          using only live data).
        """
        super().__init__(names=names, config=config)
        self.path = Path(path)

    # Methods that need to be defined in subclasses --------------------------

    def load_saved_measurement(self, name, nrange=None):
        """Load saved data. nrange is the range in measurement numbers.

        The output must be an object of a subclass of MeasurementBase.
        nrange = (n1, n2) with both n1 included and first measurement is n=1.
        nrange = None should load all the data
        """
        pass

    # Other methods ----------------------------------------------------------

    def show(self):
        """Static plot of saved data"""
        for name in self.names:
            measurement = self.load_saved_measurement(name)
            self.plot(measurement)
        self.fig.tight_layout()
        plt.show(block=False)


class PeriodicDataReading:
    """Class to manage periodic reading of queues to plot data."""

    def __init__(self, dt_data=1):
        """Init class.

        Parameter dt_data is how often (in s) the loop checks for new data.
        """
        self.timer = oclock.Timer(interval=dt_data, name='Data Update')

        self.queue = Queue()
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

        # data_plot is inherited later from the Graph-like classes
        self.data_plot(e_graph=self.e_graph, e_close=self.e_stop, e_stop=self.e_stop,
                       q=self.queue, timer=self.timer)
        # e_stop two times, because we want a figure closure event to also
        # trigger stopping of the recording process here.


class SensorGraphUpdated(GraphBase, PeriodicDataReading):
    """Create live graph by reading the sensors directly."""

    def __init__(self, names, config, dt_data=1):
        """Init Graph. See Parent classes for parameters."""
        GraphBase.__init__(self, names=names, config=config)
        PeriodicDataReading.__init__(self, dt_data=dt_data)

    # Methods that need to be defined in subclasses --------------------------

    def format_live_measurement(self, name, data):
        """How to format the data given by self.read()"""
        pass

    # Other methods ----------------------------------------------------------

    def get_data(self, name):
        """Check if new data is read by sensor, and put it in data queue."""
        self.timer.reset()
        Sensor = self.config['sensors'][name]
        sensor = Sensor()

        while not self.e_stop.is_set():
            try:
                data = sensor.read(avg=1)
            except self.config['sensor error']:
                pass
            else:
                measurement = self.format_live_measurement(name, data)
                self.queue.put(measurement)
                self.timer.checkpt()


class SavedGraphUpdated(SavedGraph, PeriodicDataReading):
    """Extends Saved Graph to be able to periodically read file to update."""

    def __init__(self, names, config, path='.', dt_data=1):
        """Init Graph. See Parent classes for parameters."""
        SavedGraph.__init__(self, names=names, config=config, path=path)
        PeriodicDataReading.__init__(self, dt_data=dt_data)

    # Methods that need to be defined in subclasses --------------------------

    def number_of_saved_measurements(self, name):
        """Get number of measurements of a sensor already saved in a file."""
        pass

    # Other methods ----------------------------------------------------------

    def get_data(self, name):
        """Check if new data is added to file, and put it in data queue."""
        self.timer.reset()
        n0 = self.number_of_saved_measurements(name)
        while not self.e_stop.is_set():
            n = self.number_of_saved_measurements(name)
            if n > n0:
                measurement = self.load_saved_measurement(name, nrange=(n0 + 1, n))
                if measurement.data is not None:
                    self.queue.put(measurement)
                    n0 = n
            self.timer.checkpt()
