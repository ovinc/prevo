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

from .general import ViewerBase, WindowBase

try:
    import cv2
except ModuleNotFoundError:
    opencv_available = False
else:
    opencv_available = True


ESCAPE_KEYS = (ord('q'), ord('Q'), 27)  # 27 is ESC.


class CvWindow(WindowBase):
    """Display camera images using OpenCV."""

    def __init__(
        self,
        image_queue,
        name,
        **kwargs,
    ):
        """Initialize a CvWindow object.

        Parameters
        ----------
        image_queue : queue
            Queue in which taken images are placed.
        name : str
            Name of the window, serving as the ID for OpenCV windows.
        **kwargs : dict, optional
            Additional keyword arguments passed to WindowBase.

        Other Parameters
        ----------------
        calculate_fps : bool, optional
            If True, store image times to calculate FPS.
        show_fps : bool, optional
            If True, display the current FPS on the viewer.
        show_num : bool, optional
            If True, display the current image number on the viewer.
            Note: Image data must be a dict with key 'num', or a different
            data_formatter must be provided.
        dt_fps : float, optional
            How often (in seconds) the display FPS is calculated.
        dt_num : float, optional
            How often (in seconds) the image numbers are updated.
        measurement_formatter : MeausrementFormatter object, optional
            Object that transforms elements from the queue into image arrays
            and image numbers (type MeasurementFormatter or equivalent).
        """
        super().__init__(image_queue, name=name, **kwargs)

    def _init_window(self):
        """Create window"""
        cv2.namedWindow(self.name, cv2.WINDOW_NORMAL)
        self.info = "..."

    def _display_image(self):
        # Here we need to have the info display directly in display_image
        # since the info is written directly on the image itself
        # This can cause some imprecisions in the image numbers displayed
        cv2.putText(
            self.image,
            self.info,
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        if self.image.ndim > 2:
            # openCV works with BGR data
            self.image = cv2.cvtColor(self.image, cv2.COLOR_RGB2BGR)
        cv2.imshow(self.name, self.image)


class CvViewer(ViewerBase):
    """Display several cameras at the same time using OpenCV"""

    def __init__(
        self,
        windows,
        **kwargs,
    ):
        """Initialize a CvViewer object.

        Parameters
        ----------
        windows : iterable
            Iterable of objects of type WindowBase or its subclasses.
        **kwargs : dict, optional
            Additional keyword arguments passed to ViewerBase.

        Other Parameters
        ----------------
        external_stop : threading.Event, optional
            Stopping event signaling a stop request from outside the class.
            This event is monitored but not modified.
        dt_graph : float, optional
            How often (in seconds) the viewer is updated.
        """
        if not opencv_available:
            raise ValueError('OpenCV not installed.')

        super().__init__(windows=windows, **kwargs)

    # ------------------------- Misc. useful methods -------------------------

    def _count_open_windows(self):
        """Return the number of open windows (int)"""
        open_windows = []
        for window in self.windows:
            wopen = cv2.getWindowProperty(window.name, cv2.WND_PROP_VISIBLE) > 0
            open_windows.append(wopen)
        return len(open_windows)

    # ------------------ Subclassed methods from ViewerBase ------------------

    def _run(self):
        """Loop to run live viewer"""
        while True:

            self._update_info()
            self._update_images()
            self._check_external_stop()

            if self._count_open_windows() < 1:
                break

            key = cv2.waitKey(int(self.dt_graph * 1000))

            if self.internal_stop.is_set() or key in ESCAPE_KEYS:
                cv2.destroyAllWindows()
                break

    def stop(self):
        super().stop()
