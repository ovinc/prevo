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


import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from .general import max_possible_pixel_value
from .general import WindowBase, ViewerBase, CONFIG, DISPOSITIONS


class MplWindow(WindowBase):
    """Display camera images using Matplotlib"""

    def __init__(self,
                 image_queue,
                 **kwargs):
        """Init MplSingleViewer object.

        Parameters
        ----------

        - image_queue: queue in which taken images are put.
        _ blit: if True, use blitting for faster rendering (can cause issues
                for updating info such as fps, image number)

        Additional kwargs from WindowBase
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

        NOTE: self.ax must be defined before calling various window methods.
        """
        super().__init__(image_queue, **kwargs)

    @property
    def ax(self):
        """Matplotlib axes object in which to put the current window."""
        return self._ax

    @ax.setter
    def ax(self, value):
        self._ax = value

    def _init_window(self):
        self._format_axes()
        self.init_done = False

    def _format_axes(self):
        """"Set colors, title etc."""
        self.ax.set_title(self.name,
                          color=CONFIG['textcolor'],
                          fontfamily=CONFIG['fontfamily'])

        for location in 'bottom', 'top', 'left', 'right':
            # self.ax.spines[location].set_color(textcolor)
            self.ax.spines[location].set_visible(False)

        self.ax.xaxis.label.set_color(CONFIG['textcolor'])
        self.ax.tick_params(axis='both', colors=CONFIG['textcolor'])

    def _init_image(self, image):
        kwargs = {} if image.ndim > 2 else {'cmap': 'gray'}

        self.im = self.ax.imshow(image,
                                 animated=True,
                                 vmin=0,
                                 vmax=max_possible_pixel_value(image),
                                 **kwargs)
        self.init_done = True
        self.xlabel = self.ax.set_xlabel('...',
                                         color=CONFIG['textcolor'],
                                         fontfamily=CONFIG['fontfamily'])

    def _update(self, i=0):
        """Indicate what happens at each step of the matplotlib animation."""
        self._update_info()
        data = self._update_image()
        return () if data is None else (self.im,)

    def _display_info(self):
        try:
            self.xlabel.set_text(self.info)
        # In case the _init_image has not been called yet
        except AttributeError:
            pass

    def _display_image(self):
        """How to display image in viewer."""
        if not self.init_done:
            self._init_image(self.image)
        else:
            self.im.set_array(self.image)


class MplViewer(ViewerBase):
    """Display several cameras at the same time using Matplotlib"""

    def __init__(self,
                 windows,
                 fig=None,
                 blit=True,
                 **kwargs):
        """
        Init MplViewer object

        Parameters
        ----------

        - windows: iterable of objects of type WindowBase or subclasses
        - fig: (optional): matplotlib figure in which to create the viewer.
        - blit: if True, use blitting for faster rendering (can cause issues
                for updating info such as fps, image number)


        Additional kwargs from ViewerBase
        - external_stop: stopping event (threading.Event or equivalent)
                         signaling stopping requested from outside of the class
                         (won't be set or cleared, just monitored)
        - dt_graph: how often (in seconds) the viewer is updated
        """
        self.blit = blit
        self.fig = fig
        super().__init__(windows=windows, **kwargs)

    def _init_viewer(self):
        """Generate figure/axes as a function of input names"""

        n = len(self.windows)
        n1, n2 = DISPOSITIONS[n]  # dimensions of grid to place elements

        if self.fig is None:
            width = 4 * n2
            height = 4 * n1
            self.fig = plt.figure(figsize=(width, height))

        for i, window in enumerate(self.windows):
            ax = self.fig.add_subplot(n1, n2, i + 1)
            window.ax = ax

        self.fig.set_facecolor(CONFIG['bgcolor'])
        self.fig.tight_layout()

        # NOTE: stop() is called automatically by start() once matplotlib
        # window is destroyed. But if one wants more things to happen
        # upon figure closing, one can do something like:
        # self.fig.canvas.mpl_connect('close_event', self._on_close)

        # NOTE: I also tried to play with self.ani.event_source.stop()
        # to prevent the bug in tkinter on_timer, but no success.

    def _update(self, i=0):
        """Indicate what happens at each step of the matplotlib animation."""
        self._check_external_stop()
        to_be_animated = ()
        for window in self.windows:
            to_be_animated += window._update(i=i)
        return to_be_animated

    def _run(self):
        """Main function to run the animation"""
        self.ani = FuncAnimation(self.fig,
                                 self._update,
                                 interval=int(self.dt_graph) * 1000,
                                 blit=self.blit,
                                 cache_frame_data=False)
        plt.show(block=True)
        return self.ani

    def stop(self):
        plt.close(self.fig)
        super().stop()
