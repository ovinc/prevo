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


import tkinter as tk
import itertools
from PIL import Image, ImageTk

from .general import WindowBase, ViewerBase, CONFIG, DISPOSITIONS


class TkWindow(WindowBase):
    """Live view of images using tkinter"""

    def __init__(self,
                 image_queue,
                 auto_size=True,
                 **kwargs,
                 ):
        """Init TkSingleViewer object

        Parameters
        ----------

        - image_queue: queue in which taken images are put.
        - auto_size: autoscale image to window in real time

        Additional kwargs from WindowBase:
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
        super().__init__(image_queue, **kwargs)
        self.auto_size = auto_size

    @property
    def parent(self):
        """Tkinter parent in which to put the current window."""
        return self._parent

    @parent.setter
    def parent(self, value):
        self._parent = value
        self._parent.configure(bg=CONFIG['bgcolor'])

    def _init_window(self):
        """Create tkinter window and elements."""
        if self.name is not None:
            self.title_label = tk.Label(self.parent,
                                        text=self.name,
                                        font=(CONFIG['fontfamily'], 14),
                                        bg=CONFIG['bgcolor'],
                                        fg=CONFIG['textcolor'])
            self.title_label.pack(expand=True)

        self.image_label = tk.Label(self.parent, highlightthickness=0)
        self.image_label.pack(expand=True)

        if self.info_queues:
            self.info_label = tk.Label(self.parent,
                                       bg=CONFIG['bgcolor'],
                                       fg=CONFIG['textcolor'],
                                       font=(CONFIG['fontfamily'], 12),
                                       text=str('...'))
            self.info_label.pack(expand=True)

        self.image_count = 0

    def _display_info(self):
        self.info_label.config(text=self.info)

    def _display_image(self):
        """How to display image in viewer."""
        self.image_count += 1

        img = Image.fromarray(self.image)
        img_disp = self._prepare_displayed_image(img)

        self.img = ImageTk.PhotoImage(image=img_disp)
        self.image_label.configure(image=self.img)

    def _prepare_displayed_image(self, img):
        """Resize image and/or calculate aspect ratio if necessary"""

        if self.image_count > 1:
            if self.auto_size:
                dimensions = self._adapt_image_to_window()
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

    def _adapt_image_to_window(self):
        """Calculate new dimensions of image to accommodate window resizing."""

        window_width = self.parent.winfo_width()
        window_height = self.parent.winfo_height()

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


class TkViewer(ViewerBase):
    """Live view of images from multiple cameras using tkinter"""

    def __init__(self,
                 windows,
                 fit_to_screen=True,
                 **kwargs):
        """Init TkViewer object

        Parameters
        ----------

        - windows: iterable of objects of type WindowBase or subclasses
        - fit_to_screen: maximize window size when instantiated
        - root: Tkinter parent in which to display viewer (if not, tk.Tk())

        Additional kwargs from ViewerBase
        - external_stop: stopping event (threading.Event or equivalent)
                         signaling stopping requested from outside of the class
                         (won't be set or cleared, just monitored)
        - dt_graph: how often (in seconds) the viewer is updated
        """
        self.fit_to_screen = fit_to_screen
        super().__init__(windows=windows, **kwargs)

    def _create_root(self):
        self.root = tk.Tk()
        self.root.configure(bg=CONFIG['bgcolor'])
        # Detect manual closing of window
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_grid(self, parent=None):
        """This allows to create the elements in other parents for child classes."""
        parent = self.root if parent is None else parent

        for window in self.windows:
            window.parent = tk.Frame(master=parent)

        n = len(self.windows)
        n1, n2 = DISPOSITIONS[n]  # dimensions of grid to place elements
        positions = itertools.product(range(n1), range(n2))

        for window, position in zip(self.windows, positions):
            i, j = position
            window.parent.grid(row=i, column=j, padx=5, pady=5, sticky='nsew')

        # Make columns and rows expand and be all the same size
        # Note: the str in uniform= is just an identifier
        # all columns / rows sharing the same string are kept of same size
        for i in range(n1):
            parent.grid_rowconfigure(i, weight=1, uniform='same rows')
        for j in range(n2):
            parent.grid_columnconfigure(j, weight=1, uniform='same columns')

    def _init_viewer(self):
        self._create_root()
        self._create_grid(parent=self.root)
        if self.fit_to_screen:
            self._fit_to_screen()

    def _fit_to_screen(self):
        """Adapt window size to screen resolution/size"""
        w_screen = self.root.winfo_screenwidth()
        h_screen = self.root.winfo_screenheight()
        self.root.geometry(f"{0.8 * w_screen:.0f}x{0.8 * h_screen:.0f}")

    def _run(self):
        self._update()
        self.root.mainloop()

    def _update(self):
        self._update_info()
        self._update_images()
        self._check_external_stop()
        self.loop = self.root.after(int(1000 * self.dt_graph), self._update)

    def _cancel_loop(self):
        try:
            loop = self.loop
        except AttributeError:  # in case after() has not been called yet
            pass
        else:
            self.root.after_cancel(loop)

    def _on_close(self):
        """Callback to user manually closing window"""
        self._cancel_loop()
        self.root.destroy()  # without this the window doesn't get closed

    def stop(self):
        self._cancel_loop()
        # If application still active, close tk window
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        super().stop()
