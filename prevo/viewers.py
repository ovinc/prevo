"""Viewers for live series of images (e.g. from cameras) arriving as queues."""


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


from abc import ABC, abstractmethod
import tkinter as tk
import time
from queue import Queue, Empty
from threading import Thread, Event
import itertools
from traceback import print_exc

import numpy as np
from PIL import Image, ImageTk

try:
    import cv2
except ModuleNotFoundError:
    pass

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# ====================== Parameters for Tkinter viewers ======================


bgcolor = '#485a6a'
textcolor = '#e7eff6'
fontfamily = "serif"



# =============================== MISC. Tools ================================


def get_last_from_queue(queue):
    """Function to empty queue to get last element from it.

    Return None if queue is initially empty, return last element otherwise.
    """
    element = None
    while True:
        try:
            element = queue.get(timeout=0)
        except Empty:
            break
    return element


def get_all_from_queue(queue):
    """Function to empty queue to get all elements from it as a list

    Return None if queue is initially empty, return last element otherwise.
    """
    elements = []
    while True:
        try:
            elements.append(queue.get(timeout=0))
        except Empty:
            break
    return elements


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


class InfoSender(ABC):
    """Class to send information to display in Image Viewer.

    For example: fps, image info, etc.
    """
    def __init__(self,
                 queue=None,
                 e_stop=None,
                 dt_check=1):
        """Parameters:

        - queue: queue into information is put
        - e_stop: stopping event (threading.Event or equivalent)
        - dt_check: how often (in seconds) information is sent
        """
        self.queue = Queue() if queue is None else queue
        self.e_stop = Event() if e_stop is None else e_stop
        self.dt_check = dt_check

    @abstractmethod
    def _generate_info(self):
        """To be defined in subclass.

        Should return a str of info to print in the viewer.
        Should return a false-like value if no news info can be provided."""
        pass

    def _run(self):
        """Send information periodically (blocking)."""

        while not self.e_stop.is_set():
            info = self._generate_info()
            self.queue.put(info)

            # dt_check should be long compared to the time required to
            # process and generate the info.
            self.e_stop.wait(self.dt_check)

    def start(self):
        """Same as _run() but nonblocking."""
        Thread(target=self._run).start()


class LiveFpsCalculator(InfoSender):
    """"Calculate fps in real time from a queue supplying image times.

    fps values are sent back in another queue as str
    """

    def __init__(self,
                 time_queue,
                 queue=None,
                 e_stop=None,
                 dt_check=1):
        """Parameters:

        - time_queue: queue from which display times arrive
        - queue: queue into which fps values are put
        - e_stop: stopping event (threading.Event or equivalent)
        - dt_check: how often (in seconds) times are checked to calculate fps
        """
        super().__init__(queue=queue, e_stop=e_stop, dt_check=dt_check)
        self.time_queue = time_queue

    def _generate_info(self):
        """Calculate fps from display times, print '...' if none available"""
        times = get_all_from_queue(self.time_queue)
        if times:
            if len(times) > 1:
                fps = 1 / np.diff(times).mean()
                return f'[{fps:.1f} fps]'
        return '[... fps]'


class LiveImageNumber(InfoSender):
    """"Calculate fps in real time from a queue supplying image times.

    fps values are sent back in another queue as str
    """

    def __init__(self,
                 num_queue,
                 queue=None,
                 e_stop=None,
                 dt_check=1):
        """Parameters:

        - num_queue: queue from which image numbers arrive
        - queue: queue into which output values are put
        - e_stop: stopping event (threading.Event or equivalent)
        - dt_check: how often (in seconds) times are checked to calculate fps
        """
        super().__init__(queue=queue, e_stop=e_stop, dt_check=dt_check)
        self.num_queue = num_queue
        self.last_num = None

    def _generate_info(self):
        """Return last image number received from queue."""
        num = get_last_from_queue(self.num_queue)
        if num is not None:
            self.last_num = num

        if self.last_num is None:
            return '[# ...]'
        else:
            return f'[# {self.last_num}]'


# =============================== Base classes ===============================


class ViewerBase:
    """Only useful to provide general start() function"""

    def __init__(self, e_stop=None, e_close=None, dt_graph=0.02):
        """Init ViewerBase object

        Parameters
        ----------
        - e_stop: stopping event (threading.Event or equivalent)
        - e_close: event that is triggered when viewer is closed
                   (can be the same as e_stop)
        - dt_graph: how often (in seconds) the viewer is updated
        """
        self.dt_graph = dt_graph
        self.e_stop = e_stop if e_stop is not None else Event()
        self.e_close = e_close if e_stop is not None else Event()

    def start(self):
        try:
            self._init_window()
            self._init_run()
            self._run()
        except Exception:
            print('--- !!! Error in Viewer !!! ---')
            print_exc()
        self.on_stop()


class SingleViewer(ViewerBase):
    """Base class for GUIs for viewing images from image queues."""

    def __init__(self,
                 image_queue,
                 name='Camera',
                 e_stop=None,
                 e_close=None,
                 calculate_fps=False,
                 show_fps=False,
                 show_num=False,
                 dt_graph=0.02,
                 dt_fps=2,
                 dt_num=0.2,
                 update_info_with_every_image=False,
                 ):
        """Init Single Viewer object.

        Parameters
        ----------

        - image_queue: queue in which taken images are put.
        - name: optional name for display purposes.
        - e_stop: stopping event (threading.Event or equivalent)
        - e_close: event that is triggered when viewer is closed
                   (can be the same as e_stop)
        - calculate_fps: if True, store image times fo calculate fps
        - show_fps: if True, indicate current display fps on viewer
        - show_num: if True, indicate current image number on viewer
                    (note: image data must be a dict with key 'num', or
                    self._measurement_to_num must be subclassed)
        - dt_graph: how often (in seconds) the viewer is updated
        - dt_fps: how often (in seconds) display fps are calculated
        - dt_num: how often (in seconds) image numbers are updated
        - update_info_with_every_image: if True, any info (fps, num etc.) is
                                        sent for printing at every new
                                        displayed image (useful if info is
                                        printed on the image directly instead
                                        of on a surrounding GUI).
        """
        super().__init__(dt_graph=dt_graph, e_stop=e_stop, e_close=e_close)

        self.image_queue = image_queue
        self.name = name

        self.calculate_fps = calculate_fps
        self.show_fps = show_fps
        self.show_num = show_num

        self.update_info_with_every_image = update_info_with_every_image

        self._init_info(dt_fps=dt_fps, dt_num=dt_num)

    def _init_info(self, **kwargs):
        """Init info objects that manage printing of fps, img number etc."""

        self.info_queues = {}
        self.info_values = {}

        # store times at which images are shown on screen (e.g. for fps calc.)
        if self.calculate_fps:
            self.display_times = []             # to calculate fps on all times

        if self.show_fps:
            self.display_times_queue = Queue()  # to calculate fps on partial data
            fps_calculator = LiveFpsCalculator(time_queue=self.display_times_queue,
                                               e_stop=self.e_stop,
                                               dt_check=kwargs.get('dt_fps'))
            self.info_queues['fps'] = fps_calculator.queue
            self.info_values['fps'] = ''
            fps_calculator.start()

        if self.show_num:
            self.image_number_queue = Queue()
            image_number = LiveImageNumber(num_queue=self.image_number_queue,
                                           e_stop=self.e_stop,
                                           dt_check=kwargs.get('dt_num'))
            self.info_queues['num'] = image_number.queue
            self.info_values['num'] = ''
            image_number.start()

    def _init_window(self):
        """How to create/init window."""
        pass

    def _init_run(self):
        """Anything to be done just before starting the viewer."""
        pass

    def _measurement_to_image(self, measurement):
        """How to transform individual elements from the queue into an image.

        (returns an array-like object).
        Can be subclassed to accommodate different queue formats.
        """
        return measurement['image']

    def _measurement_to_num(self, measurement):
        """How to get image numbers from individual elements from the queue.

        (returns an int).
        Can be subclassed to accommodate different queue formats.
        """
        return measurement['num']

    def _store_display_times(self):
        t = time.perf_counter()
        if self.calculate_fps:
            self.display_times.append(t)
        if self.show_fps:
            self.display_times_queue.put(t)

    def _display_info(self, info):
        """How to display information from info queues on image.

        Define in subclasses.
        """
        pass

    def _display_image(self, image):
        """How to display image in viewer.

        Define in subclasses.
        """
        pass

    def _manage_info(self):
        """Get information from info queues and display it if not None."""
        update = self.update_info_with_every_image
        for name, queue in self.info_queues.items():
            info = get_last_from_queue(queue)
            if info:
                print(name, info)
                update = True
                self.info_values[name] = info
        if update:
            new_info = ' '.join(self.info_values.values())
            self._display_info(new_info)

    def _process_image_queue(self):
        """How to process measurement from the image queue"""
        data = get_last_from_queue(self.image_queue)

        if data is not None:

            image = self._measurement_to_image(data)

            if self.show_num:
                num = self._measurement_to_num(data)
                self.image_number_queue.put(num)

            if self.calculate_fps or self.show_fps:
                self._store_display_times()

            self._manage_info()
            self._display_image(image)

    def on_stop(self):
        """What to do when live viewer is stopped"""
        # This is e.g. to stop camera readings in live() when window is closed.
        # In record() situations, this needs to be subclassed to avoid stopping
        # the recording when closing the window.
        self.e_close.set()

        if self.calculate_fps:
            if len(self.display_times) > 1:
                fps = 1 / np.diff(self.display_times).mean()
                print(f'Average display frame rate [{self.name}]: {fps:.3f} fps')
            else:
                print('Impossible to calculate average FPS (not enough values)')



class MultipleViewer(ViewerBase):

    def __init__(self,
                 viewers,
                 **kwargs
                 ):
        """Init MultipleViewer object

        Parameters
        ----------
        - viewers: dict {name: single viewer object}

        Additional kwargs from ViewerBase:

        """
        super().__init__(**kwargs)
        self.viewers = viewers

    def on_stop(self):
        for viewer in self.viewers.values():
            viewer.on_stop()


# ----------------------------------------------------------------------------
# ============================== OpenCV viewers ==============================
# ----------------------------------------------------------------------------


class CvSingleViewer(SingleViewer):
    """Display camera images using OpenCV"""

    def _init_window(self):
        """Create window"""
        cv2.namedWindow(self.name, cv2.WINDOW_NORMAL)
        self.info = '...'

    def _manage_info(self, *args, **kwargs):
        """Redefined here because info needs to be printed on every image."""
        if self.info_queue:
            info = get_last_from_queue(self.info_queue)
            if info:
                self.info = info
            self._display_info(self.info, *args, **kwargs)

    def _update_window(self):
        """Indicate what happens at each step of the event loop."""
        data = get_last_from_queue(self.image_queue)
        if data is not None:

            image = self._measurement_to_image(data)
            self._manage_info(image=image)

            if image.ndim > 2:
                # openCV works with BGR data
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            cv2.imshow(self.name, image)
            self._store_display_times()

    def _display_info(self, info, image=None):
        cv2.putText(image, info, (50, 50), cv2.FONT_HERSHEY_SIMPLEX,
                    1, (255, 255, 255), 2, cv2.LINE_AA)

    def run(self):
        """Loop to run live viewer"""
        while (cv2.getWindowProperty(self.name, cv2.WND_PROP_VISIBLE) > 0):
            self._update_window()
            if self.e_stop.is_set():
                cv2.destroyWindow(self.name)
                break
            cv2.waitKey(int(self.dt_graph * 1000))


# class CvMultipleViewer(MultipleViewer):
#     """Display several cameras at the same time using OpenCV"""

#     def __init__(self,
#                  image_queues,
#                  e_stop=None,
#                  dt_graph=0.01,
#                  Viewer=CvSingleViewer,
#                  **kwargs):
#         """Parameters:

#         - image_queues: dict {camera name: queue in which taken images are put.}
#         - e_stop: stopping event (threading.Event or equivalent)
#         - dt_graph: how often (in seconds) the GUI window is updated
#         - Viewer: which Viewer to use (e.g. CvSingleViewer, CvStreamViewer, etc.)
#         - **kwargs: any optional keyword arguments required by the Viewer.
#         """
#         super().__init__(image_queues=image_queues,
#                          e_stop=e_stop,
#                          dt_graph=dt_graph,
#                          Viewer=Viewer,
#                          **kwargs)

#     def run(self):
#         threads = []

#         for viewer in self.viewers.values():
#             threads.append(Thread(target=viewer.start))

#         for thread in threads:
#             thread.start()

#         for thread in threads:
#             thread.join()

#         cv2.destroyAllWindows()


# ----------------------------------------------------------------------------
# ============================ Matplotlib Viewers ============================
# ----------------------------------------------------------------------------


class MplAnimation:
    """Tools common to single-image and multiple-image animations"""

    def _update_figure(self, i):
        """Indicate what happens at each step of the matplotlib animation.

        Define in subclass.
        """
        pass

    def run(self):
        """Main function to run the animation"""
        ani = FuncAnimation(self.fig,
                            self._update_figure,
                            interval=int(self.dt_graph) * 1000,
                            blit=True,
                            cache_frame_data=False)
        plt.show(block=True)
        plt.close(self.fig)
        return ani

    def on_fig_close(self, event):
        """Anything to triggeer when figure is closed.

        A callback to on_fig_close must be declared in the subclass for this
        to be called.
        """

        # To be able to trigger on_stop() in a multiple image environment
        self.on_stop()


class MplSingleViewer(MplAnimation, SingleViewer):
    """Display camera images using Matplotlib"""

    def __init__(self, *args, dt_graph=0.04, ax=None, **kwargs):
        """Parameters:

        - dt_graph: interval (s) to update matplotlib animation
        - ax (optional): axes into which images are shown
        """
        super().__init__(*args, dt_graph=dt_graph, **kwargs)
        self.ax = ax

    def _init_window(self):

        if self.ax is None:
            self.fig, self.ax = plt.subplots()
        else:
            self.fig = self.ax.figure

            # To be able to trigger on_stop() in a multiple image environment
            self.fig.canvas.mpl_connect('close_event', self.on_fig_close)

        self._format_figure()

        self.init_done = False

    def _format_figure(self):
        """"Set colors, title etc."""
        self.fig.set_facecolor(bgcolor)
        self.ax.set_title(self.name, color=textcolor, fontfamily=fontfamily)

        for location in 'bottom', 'top', 'left', 'right':
            # self.ax.spines[location].set_color(textcolor)
            self.ax.spines[location].set_visible(False)

        self.ax.xaxis.label.set_color(textcolor)
        self.ax.tick_params(axis='both', colors=textcolor)

    def _init_image(self, image):
        self.im = self.ax.imshow(image,
                                 cmap='gray',
                                 animated=True,
                                 vmin=0,
                                 vmax=max_possible_pixel_value(image))
        self.init_done = True
        self.fig.tight_layout()
        self.xlabel = self.ax.set_xlabel('...', color=textcolor, fontfamily=fontfamily)

    def _update_figure(self, i):
        """Indicate what happens at each step of the matplotlib animation."""

        if self.e_stop.is_set():
            plt.close(self.fig)

        data = get_last_from_queue(self.image_queue)

        if data is not None:

            image = self._measurement_to_image(data)

            if not self.init_done:
                self._init_image(image)
            else:
                self.im.set_array(image)

            self._store_display_times()
            self._manage_info()

            return self.im,
        else:
            return ()

    def _display_info(self, info):
        self.xlabel.set_text(info)


# class MplMultipleViewer(MplAnimation, MultipleViewer):
#     """Display several cameras at the same time using Matplotlib"""

#     def __init__(self,
#                  image_queues,
#                  e_stop=None,
#                  dt_graph=0.04,
#                  Viewer=MplSingleViewer,
#                  **kwargs):
#         """Parameters:

#         - image_queues: dict {camera name: queue in which taken images are put.}
#         - e_stop: stopping event (threading.Event or equivalent)
#         - dt_graph: how often (in seconds) the GUI window is updated
#         - Viewer: which Viewer to use (e.g. MplSingleViewer, MplStreamViewer, etc.)
#         - **kwargs: any optional keyword arguments required by the Viewer.
#         """
#         self._create_axes(image_queues)

#         super().__init__(image_queues=image_queues,
#                          e_stop=e_stop,
#                          dt_graph=dt_graph,
#                          Viewer=Viewer,
#                          add_ppties=self.axs,
#                          add_ppty_name='ax',
#                          **kwargs)

#     def _create_axes(self, image_queues):
#         """Generate figure/axes as a function of input names"""

#         if len(image_queues) == 1:
#             fig, ax = plt.subplots(1, 1, figsize=(10, 10))
#             axes = ax,
#         elif len(image_queues) == 2:
#             fig, axes = plt.subplots(1, 2, figsize=(15, 8))
#         else:
#             raise Exception('Only 2 simultaneous cameras supported for now.')

#         axs = {name: ax for name, ax in zip(image_queues, axes)}

#         self.fig, self.axs = fig, axs

#     def _init_window(self):
#         for viewer in self.viewers.values():
#             viewer._init_window()

#     def _init_run(self):
#         for viewer in self.viewers.values():
#             viewer._init_run()

#     def _update_figure(self, i):
#         """Indicate what happens at each step of the matplotlib animation."""
#         to_be_animated = ()
#         for viewer in self.viewers.values():
#             to_be_animated += viewer._update_figure(i)
#         return to_be_animated


# ----------------------------------------------------------------------------
# ============================= Tkinter viewers ==============================
# ----------------------------------------------------------------------------


class TkSingleViewer(SingleViewer):
    """Live view of camera images using tkinter"""

    def __init__(self,
                 image_queue,
                 auto_size=True,
                 fit_to_screen=True,
                 root=None,
                 **kwargs,
                 ):
        """Init TkSingleViewer object

        Parameters
        ----------

        - image_queue: queue in which taken images are put.
        - auto_size: autoscale image to window in real time
        - fit_to_screen: maximize window size when instantiated
        - root: Tkinter parent in which to display viewer (if not, tk.Tk())

        Additional kwargs from SingleViewer:
        - name: optional name for display purposes.
        - e_stop: stopping event (threading.Event or equivalent)
        - e_close: event that is triggered when viewer is closed
                   (can be the same as e_stop)
        - calculate_fps: if True, store image times fo calculate fps
        - show_fps: if True, indicate current display fps on viewer
        - show_num: if True, indicate current image number on viewer
                    (note: image data must be a dict with key 'num', or
                    self._measurement_to_num must be subclassed)
        - dt_graph: how often (in seconds) the viewer is updated
        - dt_fps: how often (in seconds) display fps are calculated
        - dt_num: how often (in seconds) image numbers are updated
        """
        super().__init__(image_queue,
                         update_info_with_every_image=False,
                         **kwargs)

        self.auto_size = auto_size
        self.fit_to_screen = fit_to_screen
        self.root = tk.Tk() if root is None else root
        self.root.configure(bg=bgcolor)

    def _fit_to_screen(self):
        """Adapt window size to screen resolution/size"""
        w_screen = self.root.winfo_screenwidth()
        h_screen = self.root.winfo_screenheight()
        self.root.geometry(f"{0.9 * w_screen:.0f}x{0.9 * h_screen:.0f}")

    def _init_window(self):
        """Create tkinter window and elements."""

        if self.fit_to_screen:
            self._fit_to_screen()

        self.title_label = tk.Label(self.root, text=self.name,
                                    font=(fontfamily, 14),
                                    bg=bgcolor, fg=textcolor)
        self.title_label.pack(expand=True)

        self.image_label = tk.Label(self.root, highlightthickness=0)
        self.image_label.pack(expand=True)

        if self.info_queues:
            self.info_label = tk.Label(self.root,
                                       bg=bgcolor,
                                       fg=textcolor,
                                       font=(fontfamily, 12),
                                       text=str('...'))
            self.info_label.pack(expand=True)

    def _init_run(self):
        """If things need to be done before running (subclass if necessary)"""
        self.image_count = 0

    def _run(self):
        """Main  loop for Tkinter GUI viewer"""
        self.update_window()
        self.root.mainloop()

    def _display_image(self, image):
        """How to display image in viewer."""
        self.image_count += 1

        img = Image.fromarray(image)
        img_disp = self.prepare_displayed_image(img)

        self.img = ImageTk.PhotoImage(image=img_disp)
        self.image_label.configure(image=self.img)

    def update_window(self):
        """Update window, with the after() method."""
        self._process_image_queue()
        if not self.e_stop.is_set():
            self.root.after(int(1000 * self.dt_graph), self.update_window)
        else:
            self.root.destroy()

    def prepare_displayed_image(self, img):
        """Resize image and/or calculate aspect ratio if necessary"""

        if self.image_count > 1:
            if self.auto_size:
                dimensions = self.adapt_image_to_window()
                try:
                    img_disp = img.resize(dimensions, Image.ANTIALIAS)
                except ValueError:  # somtimes dimensions are (0, 0) for some reason
                    img_disp = img
            else:
                img_disp = img

        else:  # Calculate aspect ratio on first image received
            self.aspect_ratio = img.height / img.width
            img_disp = img

        return img_disp

    def adapt_image_to_window(self):
        """Calculate new dimensions of image to accommodate window resizing."""

        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()

        target_width = 0.98 * window_width
        target_height = 0.85 * window_height

        target_ratio = target_height / target_width

        if target_ratio > self.aspect_ratio:
            width = int(target_width)
            height = int(target_width * self.aspect_ratio)
        else:
            height = int(target_height)
            width = int(target_height / self.aspect_ratio)

        return width, height

    def _display_info(self, info):
        self.info_label.config(text=info)


class TkMultipleViewer(MultipleViewer):
    """Live view of images from multiple cameras using tkinter"""

    def __init__(self,
                 image_queues,
                 fit_to_screen=True,
                 root=None,
                 auto_size=True,
                 calculate_fps=False,
                 show_fps=False,
                 show_num=False,
                 **kwargs):
        """Init TkMultipleViewerObject

        Parameters
        ----------

        - image_queues: dict {camera name: queue in which taken images are put.}
        - fit_to_screen: maximize window size when instantiated
        - root: Tkinter parent in which to display viewer (if not, tk.Tk())

        Arguments to pass to TkSingleViewers
        - auto_size: autoscale image to window in real time
        - calculate_fps: if True, store image times fo calculate fps
        - show_fps: if True, indicate current display fps on viewer
        - show_num: if True, indicate current image number on viewer
                    (note: image data must be a dict with key 'num', or
                    self._measurement_to_num must be subclassed)

        Additional kwargs from MultipleViewer
        - e_stop: stopping event (threading.Event or equivalent)
        - e_close: event that is triggered when viewer is closed
                   (can be the same as e_stop)
        - dt_graph: how often (in seconds) the viewer is updated
        """
        self.root = tk.Tk() if root is None else root
        self.root.configure(bg=bgcolor)
        self.fit_to_screen = fit_to_screen

        viewers = {}
        for name, image_queue in image_queues.items():
            viewers[name] = TkSingleViewer(
                image_queue=image_queue,
                name=name,
                root=tk.Frame(master=self.root),
                fit_to_screen=False,  # Important to keep False
                auto_size=auto_size,
                calculate_fps=calculate_fps,
                show_fps=show_fps,
                show_num=show_num,
            )

        super().__init__(viewers=viewers, **kwargs)

        # How to place elements on window as a function of number of widgets
        dispositions = {1: (1, 1),
                        2: (1, 2),
                        3: (1, 3),
                        4: (2, 2)}

        n = len(self.viewers)
        n1, n2 = dispositions[n]  # dimensions of grid to place elements
        positions = itertools.product(range(n1), range(n2))

        for viewer, position in zip(self.viewers.values(), positions):
            i, j = position
            viewer.root.grid(row=i, column=j, padx=5, pady=5, sticky='nsew')

        # Make columns and rows expand and be all the same size
        # Note: the str in uniform= is just an identifier
        # all columns / rows sharing the same string are kept of same size
        for i in range(n1):
            self.root.grid_rowconfigure(i, weight=1,
                                        uniform='same size rows')
        for j in range(n2):
            self.root.grid_columnconfigure(j, weight=1,
                                           uniform='same size columns')

    def _init_window(self):
        if self.fit_to_screen:
            TkSingleViewer._fit_to_screen(self)
        for viewer in self.viewers.values():
            viewer._init_window()

    def _init_run(self):
        for viewer in self.viewers.values():
            viewer._init_run()

    def _run(self):
        self.update_window()
        self.root.mainloop()

    def _process_image_queues(self):
        for viewer in self.viewers.values():
            viewer._process_image_queue()

    def update_window(self):
        self._process_image_queues()
        if not self.e_stop.is_set():
            self.root.after(int(1000 * self.dt_graph), self.update_window)
        else:
            self.root.destroy()


# # ============ For live streaming with real-time fps calculation =============


# class CvStreamViewer(SingleStreamViewer, CvSingleViewer):
#     pass


# class MplStreamViewer(SingleStreamViewer, MplSingleViewer):
#     pass


# class TkStreamViewer(SingleStreamViewer, TkSingleViewer):
#     pass


# # ================ Integration into prevo.Record environments ================


# class RecordInfoSender(InfoSender):
#     """Class to send information to display in Image Viewer.

#     For example: fps, image number, etc.
#     """
#     def __init__(self, recording, info_queue, e_stop, dt_check=0.2):
#         """Parameters:

#         - recording: object of subclass of prevo.RecordingBase
#         - info_queue: queue into which information is put
#         - e_stop: stopping event (threading.Event or equivalent)
#         - dt_check: how often (in seconds) information is sent
#         """
#         self.recording = recording
#         super().__init__(info_queue=info_queue,
#                          e_stop=e_stop,
#                          dt_check=dt_check)

#     def _generate_info(self):
#         """To be defined in subclass.

#         Should return a str of info to print in the viewer.
#         Should return a false-like value if no news info can be provided."""
#         return f'# {self.recording.num}'


# class RecordSingleViewer:
#     """Additional methods to SingleViewer and subclasses.

#     For use in prevo.RecordBase environments."""

#     def __init__(self, recordings, dt_check=0.2, **kwargs):

#         super().__init__(info_queue=Queue(), **kwargs)

#         self.recording = recordings[self.name]  # self.name defined in super()
#         self.dt_check = dt_check

#     def _init_run(self):
#         super()._init_run()
#         if self.info_queue:
#             info_sender = RecordInfoSender(recording=self.recording,
#                                            info_queue=self.info_queue,
#                                            e_stop=self.e_stop,
#                                            dt_check=self.dt_check)
#             info_sender.start()

#     def on_stop(self):
#         """Here one does not want to stop recording when window is closed."""
#         pass


# class CvRecordSingleViewer(RecordSingleViewer, CvSingleViewer):
#     pass


# class MplRecordSingleViewer(RecordSingleViewer, MplSingleViewer):
#     pass


# class TkRecordSingleViewer(RecordSingleViewer, TkSingleViewer):
#     pass


# class RecordMultipleViewer:
#     """Additional methods to MultipleViewers-type classes.

#     For use in prevo.RecordBase environments."""

#     def __init__(self, e_graph, **kwargs):
#         super().__init__(Viewer=self.SingleViewer, **kwargs)
#         self.e_graph = e_graph

#     def on_stop(self):
#         self.e_graph.clear()


# class CvRecordMultipleViewer(RecordMultipleViewer, CvMultipleViewer):
#     SingleViewer = CvRecordSingleViewer
#     pass


# class MplRecordMultipleViewer(RecordMultipleViewer, MplMultipleViewer):
#     SingleViewer = MplRecordSingleViewer
#     pass


# class TkRecordMultipleViewer(RecordMultipleViewer, TkMultipleViewer):
#     SingleViewer = TkRecordSingleViewer
#     pass
