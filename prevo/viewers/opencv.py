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
    pass


class CvWindow(WindowBase):
    """Display camera images using OpenCV"""

    def __init__(self, image_queue, name, **kwargs):
        """Init Window object.

        Parameters
        ----------

        - image_queue: queue in which taken images are put.
        - name: NOT optional here because it serves as ID for openCV windows

        Additional kwargs from WindowBase:
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
        super().__init__(image_queue, name=name, **kwargs)

    def _init_window(self):
        """Create window"""
        cv2.namedWindow(self.name, cv2.WINDOW_NORMAL)
        self.info = '...'

    def _display_image(self):
        # Here we need to have the info display directly in display_image
        # since the info is written directly on the image itself
        # This can cause some imprecisions in the image numbers displayed
        cv2.putText(self.image, self.info, (50, 50), cv2.FONT_HERSHEY_SIMPLEX,
                    1, (255, 255, 255), 2, cv2.LINE_AA)

        if self.image.ndim > 2:
            # openCV works with BGR data
            self.image = cv2.cvtColor(self.image, cv2.COLOR_RGB2BGR)
        cv2.imshow(self.name, self.image)


class CvViewer(ViewerBase):
    """Display several cameras at the same time using OpenCV"""

    def __init__(self,
                 windows,
                 **kwargs):
        """Init CvViewer object

        Parameters
        ----------

        - windows: iterable of objects of type WindowBase or subclasses

        Additional kwargs from ViewerBase
        - external_stop: stopping event (threading.Event or equivalent)
                         signaling stopping requested from outside of the class
                         (won't be set or cleared, just monitored)
        - dt_graph: how often (in seconds) the viewer is updated
        """
        super().__init__(windows=windows, **kwargs)

    def _run(self):
        """Loop to run live viewer"""
        open_windows = []
        for window in self.windows:
            wopen = cv2.getWindowProperty(window.name, cv2.WND_PROP_VISIBLE) > 0
            open_windows.append(wopen)

        while (any(open_windows)):
            self._update_info()
            self._update_images()
            self._check_external_stop()
            if self.internal_stop.is_set():
                for window in self.windows:
                    cv2.destroyWindow(window.name)
                break
            cv2.waitKey(int(self.dt_graph * 1000))

    def stop(self):
        super().stop()
        cv2.destroyAllWindows()
