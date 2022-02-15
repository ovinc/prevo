"""Similar to plot.py, but to view images instead of plotting numerical data."""


from threading import Thread
import tkinter as tk
import time

# Non standard imports
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
import cv2


# The two lines below have been added following a console FutureWarning:
# "Using an implicitly registered datetime converter for a matplotlib plotting
# method. The converter was registered by pandas on import. Future versions of
# pandas will require you to explicitly register matplotlib converters."
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()


def max_possible_pixel_value(img):
    """Return max pixel value depending on image type, for use in plt.imshow.

    Input
    -----
    img: numpy array

    Output
    ------
    vmax: max pixel value (int or float or None)
    """
    if img.dtype == 'uint8':
        return 2**8 - 1
    elif img.dtype == 'uint16':
        return 2**16 - 1
    else:
        return None


class CameraViewCv:
    """View camera images with OpenCV"""

    # Tkinter Appearance parameters
    bgcolor = '#0b3c5d'
    textcolor = '#f7f7f7'

    def __init__(self, names):
        """Parameters:

        - 'names': iterable of names of sensors.
        """
        self.names = names

    def run(self, e_graph, e_close, e_stop, q_plot, timer=None):
        """Show camera images concurrently.

        Parameters
        ----------
        - e_graph is set when the graph is activated
        - e_close is set when all windows have been closed
        - e_stop is set when there is an external stop request.
        - q_plot is a dict of data queues from which images arrive
        - timer is an optional external timer that gets deactivated here if
        figure is closed
        """
        threads = []

        for name in self.names:
            q = q_plot[name]
            # self.run_window(name, q)
            thread = Thread(target=self.run_window, args=(name, q, e_stop))
            threads.append(thread)

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        cv2.destroyAllWindows()
        e_close.set()
        e_graph.clear()
        if timer is not None:
            timer.stop()

    # def gui(self, e_stop):
    #     """Tkinter GUI to display camera info"""

    #     self.root = tk.Tk()

    #     self.root.geometry("150x75")  # Width x Height
    #     self.root.title("Timer")
    #     self.root.minsize(170, 40)
    #     self.root.config(bg=self.bgcolor)

    #     self.n = 0

    #     self.display = tk.Label(self.root,
    #                             font=('Helvetica', 30),
    #                             bg=self.bgcolor,
    #                             fg=self.textcolor,
    #                             text=str(self.n)
    #                             )

    #     self.display.pack(expand=True)

    #     def update_gui():
    #         self.n += 1
    #         self.display.config(text=str(self.n))
    #         if not e_stop.is_set():
    #             self.root.after(100, update_gui)  # update every 0.1 seconds

    #     update_gui()
    #     self.root.mainloop()

    def run_window(self, name, q, e_stop):
        """Run window for a single camera.

        Parameters
        ----------
        - name: name of camera (sensor)
        - q: queue of data for this camera
        - e_stop: stopping event
        """
        cv2.namedWindow(name, cv2.WINDOW_NORMAL)

        while cv2.getWindowProperty(name, cv2.WND_PROP_VISIBLE) > 0:

            if e_stop.is_set():
                break

            # Empty queue to get last image fo each sensor -------------------

            last_measurement = None

            while q.qsize() > 0:
                last_measurement = q.get()

            if last_measurement is not None:
                name = last_measurement['name']
                img = last_measurement['image']
                cv2.imshow(name, img)
                cv2.waitKey(1)

class CameraViewMpl:
    """View camera images with Matplotlib"""

    def __init__(self, recordings, colors, dt_graph):
        """Initiate figures and axes for data plot as a function of asked types.

        Input
        -----
        - 'recordings': dict of sensor recording objects {name: object}
        - 'colors': optional dict of colors with keys 'fig', 'ax', and the
                    names of the recordings.
        - 'dt graph': time interval to update the graph
                      (only if update_plot is used)
        """
        self.recordings = recordings
        self.names = list(recordings)

        self.colors = colors
        self.dt_graph = dt_graph

        self.fig, self.axs = self.create_axes()
        self.format_graph()

    def create_axes(self):
        """Generate figure/axes as a function of input names"""

        if len(self.names) == 1:
            fig, ax = plt.subplots(1, 1, figsize=(10, 10))
            axes = ax,
        elif len(self.names) == 2:
            fig, axes = plt.subplots(1, 2, figsize=(15, 8))
        else:
            raise Exception(f'Combination {self.names} not supported yet')

        axs = {name: ax for name, ax in zip(self.names, axes)}

        return fig, axs

    def format_graph(self):
        """Set colors, color scale, etc."""

        self.fig.set_facecolor(self.colors['fig'])

        for ax in self.axs.values():
            ax.set_facecolor(self.colors['ax'])

        # Initiate image axes with black image -------------------------------

        self.imaxs = {}  # image axis objects (imshow)
        self.xlabs = {}  # xlabel objects

        for name, ax in self.axs.items():

            camera = self.recordings[name].sensor.camera
            w, h = camera.width, camera.height
            black_image = np.zeros((h, w))

            im = ax.imshow(black_image, cmap='gray', animated=True, vmin=0)
            xlabel = ax.set_xlabel('No Image')

            self.imaxs[name] = im
            self.xlabs[name] = xlabel

        # Finalize figure ----------------------------------------------------

        self.fig.tight_layout()

    def set_pixel_range(self, measurement):
        """Set range of imshow to vmin, vmax corresponding to pixel depth.

        See self.plot() for info on measurement dict.
        """
        name = measurement['name']
        img = measurement['image']
        im = self.imaxs[name]  # imshow image object
        im.set_clim(vmin=0, vmax=max_possible_pixel_value(img))

    def plot(self, measurement):
        """Generic plot method that chooses axes depending on sensor.

        measurement is a dict with (at least) the following keys:
        - 'name' (value: name of sensor, e.g 'Cam0')
        - 'image' (value: numpy array)
        - 'time (unix)' (value: epoch time in seconds)
        """
        name = measurement['name']
        img = measurement['image']

        im = self.imaxs[name]  # plot data in correct axis depending on camera
        xlabel = self.xlabs[name]

        im.set_array(img)
        xlabel.set_text(f"Image {measurement['num']}")

        return im,

    def update_plot(self, e_graph, e_close, e_stop, q_plot, timer=None):
        """Threaded function to plot data from queues.

        INPUTS
        ------
        - e_graph is set when the graph is activated
        - e_close is set when the figure has been closed
        - e_stop is set when there is an external stop request.
        - q_plot is a dict of data queues from which images arrive
        - timer is an optional external timer that gets deactivated here if
        figure is closed

        Attention, if the figure is closed, the e_close event is triggered by
        update_plot, so do not put in e_stop a threading event that is supposed
        to stay alive even if the figure gets closed. Rather, use the e_stop
        event.

        Note: any request to update_plot when a graph is already active is ignored
        because update_plot is blocking (due to the plt.show() after FuncAnimation).
        """
        def on_fig_close(event):
            """When figure is closed, set threading events accordingly."""
            e_close.set()
            e_graph.clear()
            if timer is not None:
                timer.stop()

        # Connect a figure close event to the close() function above
        self.fig.canvas.mpl_connect('close_event', on_fig_close)

        # image count for plots, used to initiate plot parameters
        self.image_count = {name: 0 for name in self.names}

        def plot_new_data(i):
            """define what to do at each loop of the matplotlib animation."""

            if e_stop.is_set():
                plt.close(self.fig)
                # since figure is closed, e_close and e_graph are taken care of
                # by the on_fig_close() function

            to_be_animated = []

            # Empty queue to get last image fo each sensor -------------------

            for name, queue in q_plot.items():
                last_measurement = None
                while queue.qsize() > 0:
                    last_measurement = queue.get()

            # Update displayed image if necessary ----------------------------

                if last_measurement is not None:
                    self.image_count[name] += 1
                    if self.image_count[name] == 1:
                        self.set_pixel_range(last_measurement)

                    animated_objects = self.plot(last_measurement)
                    to_be_animated.extend(animated_objects)

            return to_be_animated

        # Below, it does not work if there is no value = before the FuncAnimation
        ani = FuncAnimation(self.fig, plot_new_data,
                            interval=self.dt_graph * 1000,
                            blit=True,
                            cache_frame_data=False)

        plt.show(block=True)  # block=True allow the animation to work even
        # when matplotlib is in interactive mode (plt.ion()).

        return ani
