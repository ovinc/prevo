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
import time
from queue import Queue
from threading import Thread, Event
from traceback import print_exc

import numpy as np

from ..misc import get_all_from_queue, get_last_from_queue


# ========================== Appearance Parameters  ==========================


CONFIG = {
    'bgcolor': '#485a6a',
    'textcolor': '#e7eff6',
    'fontfamily': "serif",
}


# How to place elements on window as a function of number of widgets
DISPOSITIONS = {1: (1, 1),
                2: (1, 2),
                3: (1, 3),
                4: (2, 2)}


# =============================== MISC. Tools ================================


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
                 dt_check=1):
        """Init info sender object

        Parameters
        ----------

        - queue: queue into information is put
        - dt_check: how often (in seconds) information is sent
        """
        self.queue = Queue() if queue is None else queue
        self.internal_stop = Event()
        self.dt_check = dt_check

    @abstractmethod
    def _generate_info(self):
        """To be defined in subclass.

        Should return a str of info to print in the viewer.
        Should return a false-like value if no news info can be provided."""
        pass

    def _run(self):
        """Send information periodically (blocking)."""

        while not self.internal_stop.is_set():
            info = self._generate_info()
            self.queue.put(info)

            # dt_check should be long compared to the time required to
            # process and generate the info.
            self.internal_stop.wait(self.dt_check)

    def start(self):
        """Same as _run() but nonblocking."""
        Thread(target=self._run).start()

    def stop(self):
        self.internal_stop.set()


class LiveFpsCalculator(InfoSender):
    """"Calculate fps in real time from a queue supplying image times.

    fps values are sent back in another queue as str
    """

    def __init__(self,
                 time_queue,
                 queue=None,
                 dt_check=1):
        """Parameters:

        - time_queue: queue from which display times arrive
        - queue: queue into which fps values are put
        - dt_check: how often (in seconds) times are checked to calculate fps
        """
        super().__init__(queue=queue, dt_check=dt_check)
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
                 dt_check=1):
        """Parameters:

        - num_queue: queue from which image numbers arrive
        - queue: queue into which output values are put
        - dt_check: how often (in seconds) times are checked to calculate fps
        """
        super().__init__(queue=queue, dt_check=dt_check)
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


class MeasurementFormatter:
    """How to transform elements from the queue into image arrays and img number.

    Can be subclassed.
    """

    def get_image(self, measurement):
        """How to transform individual elements from the queue into an image.

        (returns an array-like object).
        Can be subclassed to accommodate different queue formats.
        """
        return measurement['image']

    def get_num(self, measurement):
        """How to get image numbers from individual elements from the queue.

        (returns an int).
        Can be subclassed to accommodate different queue formats.
        """
        return measurement['num']


default_measurement_formatter = MeasurementFormatter()



# =============================== Base classes ===============================


class WindowBase:
    """Base class for windows managing single image queues."""

    def __init__(self,
                 image_queue,
                 name=None,
                 calculate_fps=False,
                 show_fps=False,
                 show_num=False,
                 dt_fps=2,
                 dt_num=0.2,
                 measurement_formatter=default_measurement_formatter,
                 ):
        """Init Window object.

        Parameters
        ----------

        - image_queue: queue in which taken images are put.
        - name: optional name for display purposes.
        - calculate_fps: if True, store image times fo calculate fps
        - show_fps: if True, indicate current display fps on viewer
        - show_num: if True, indicate current image number on viewer
                    (note: image data must be a dict with key 'num', or
                    a different data_formatter must be provided)
        - dt_fps: how often (in seconds) display fps are calculated
        - dt_num: how often (in seconds) image numbers are updated
        - measurement_formatter: object that transforms elements from the
                                 queue into image arrays and image numbers
                                 (type MeasurementFormatter or equivalent)
        """
        self.image_queue = image_queue
        self.name = name

        self.calculate_fps = calculate_fps
        self.show_fps = show_fps
        self.show_num = show_num

        self.measurement_formatter = measurement_formatter
        self.internal_stop = Event()

        try:
            self._init_info(dt_fps=dt_fps, dt_num=dt_num)
        except Exception:
            print(f'--- !!! Error in  {self.name} Window Init !!! ---')
            print_exc()
            self.stop()

    def __repr__(self):
        return f'{self.__class__.__name__} ({self.name})'

    def _init_info(self, **kwargs):
        """Init info objects that manage printing of fps, img number etc."""

        self.info_senders = []
        self.info_queues = {}
        self.info_values = {}

        # store times at which images are shown on screen (e.g. for fps calc.)
        if self.calculate_fps:
            self.display_times = []             # to calculate fps on all times

        if self.show_fps:
            self.display_times_queue = Queue()  # to calculate fps on partial data
            fps_calculator = LiveFpsCalculator(time_queue=self.display_times_queue,
                                               dt_check=kwargs.get('dt_fps'))
            self.info_queues['fps'] = fps_calculator.queue
            self.info_values['fps'] = ''
            self.info_senders.append(fps_calculator)
            fps_calculator.start()

        if self.show_num:
            self.image_number_queue = Queue()
            image_number = LiveImageNumber(num_queue=self.image_number_queue,
                                           dt_check=kwargs.get('dt_num'))
            self.info_queues['num'] = image_number.queue
            self.info_values['num'] = ''
            self.info_senders.append(image_number)
            image_number.start()

    def _store_display_times(self):
        t = time.perf_counter()
        if self.calculate_fps:
            self.display_times.append(t)
        if self.show_fps:
            self.display_times_queue.put(t)

    def _init_window(self):
        """How to create/init window."""
        pass

    def _display_info(self):
        """How to display information from info queues on image.

        Define in subclasses.
        """
        pass

    def _display_image(self):
        """How to display image in viewer.

        Define in subclasses.
        """
        pass

    def _get_info(self):
        """Get information from info queues and display it if not None.

        Returns None if no new info to print on screen.
        """
        update = False
        for name, queue in self.info_queues.items():
            info = get_last_from_queue(queue)
            if info:
                update = True
                self.info_values[name] = info
        if update:
            new_info = ' '.join(self.info_values.values())
            return new_info

    def _update_info(self):
        """Typically one wants to call this regularly even if no new image is
        coming in the queue, because info of fps etc. is stored in queues and
        can have some delay depending on how quickly the queues are probed."""
        info = self._get_info()
        if info is not None:
            self.info = info
            self._display_info()

        # Can be useful if one must decide what to do depending on info
        # (e.g. if info is None, do nothing else)
        return info

    def _update_image(self):
        """How to process measurement from the image queue"""
        data = get_last_from_queue(self.image_queue)
        if data is not None:

            self.image = self.measurement_formatter.get_image(data)

            if self.show_num:
                num = self.measurement_formatter.get_num(data)
                self.image_number_queue.put(num)

            if self.calculate_fps or self.show_fps:
                self._store_display_times()

            self._display_image()

        # Can be useful if one must decide what to do depending on data
        # (e.g. if data is None, do nothing else)
        return data

    def stop(self):
        """What to do when live viewer is stopped"""
        self.internal_stop.set()

        # Stop threads that caculate fps, img number etc.
        for info_sender in self.info_senders:
            info_sender.stop()

        if self.calculate_fps:
            if len(self.display_times) > 1:
                fps = 1 / np.diff(self.display_times).mean()
                print(f'Average display frame rate [{self.name}]: {fps:.3f} fps. ')
            else:
                print('Impossible to calculate average FPS (not enough values). ')


class ViewerBase:
    """Base class for Viewers (contain windows)"""

    def __init__(self,
                 windows,
                 external_stop=None,
                 dt_graph=0.02):
        """Init ViewerBase object

        Parameters
        ----------
        - windows: iterable of objects of type WindowBase or subclasses
        - external_stop: stopping event (threading.Event or equivalent)
                         signaling stopping requested from outside of the class
                         (won't be set or cleared, just monitored)
        - dt_graph: how often (in seconds) the viewer is updated
        """
        self.windows = windows
        self.dt_graph = dt_graph
        self.external_stop = external_stop
        self.internal_stop = Event()

    def _init_viewer(self):
        """Define in subclasses"""

    def _run(self):
        """Define in subclasses"""
        pass

    def _init_windows(self):
        for window in self.windows:
            window._init_window()

    def _update_info(self):
        for window in self.windows:
            window._update_info()

    def _update_images(self):
        for window in self.windows:
            window._update_image()

    def _check_external_stop(self):
        if self.external_stop:
            if self.external_stop.is_set():
                self.stop()

    def start(self):
        try:
            self._init_viewer()
            self._init_windows()
            self._run()
        except Exception:
            print('--- !!! Error in Viewer !!! ---')
            print_exc()
        self.stop()

    def stop(self):
        self.internal_stop.set()
        for window in self.windows:
            window.stop()
