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

import sys
import itertools

from .general import ViewerBase, WindowBase, CONFIG, DISPOSITIONS

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QLabel
    from PySide6.QtWidgets import QGridLayout, QWidget, QVBoxLayout
    from PySide6.QtGui import QPixmap, QImage, QFont
    from PySide6.QtCore import QTimer, Qt
except ModuleNotFoundError:
    pyside6_available = False
    print('No PySide!')
else:
    pyside6_available = True


class PysideWindow(WindowBase):
    """Sub-window (QLabel) for displaying a single camera feed."""

    def _create_labels(self):

        self.widget = QWidget()
        layout = QVBoxLayout(self.widget)

        # Image label
        self.image_label = QLabel(self.name)
        self.image_label.setMinimumSize(320, 240)
        layout.addWidget(self.image_label)

        # Info label
        self.info_label = QLabel("...")
        self.info_label.setFont(QFont('Arial', 15))

        style = f"color: {CONFIG['textcolor']}; background-color: {CONFIG['bgcolor']};"
        self.info_label.setStyleSheet(style)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center the text

        layout.addWidget(self.info_label)

    def _display_image(self):
        """Display the current image"""
        if self.image is not None:

            height, width, *channels = self.image.shape
            bytes_per_line = 3 * width if channels else width
            img_format = QImage.Format_RGB888 if channels else QImage.Format_Grayscale8

            q_image = QImage(
                self.image.data,
                width,
                height,
                bytes_per_line,
                img_format,
            )

            pixmap = QPixmap.fromImage(q_image)
            self.image_label.setPixmap(pixmap)

    def _display_info(self):
        self.info_label.setText(self.info)


class PysideMultiViewer(ViewerBase):
    """Display several camera feeds in a single parent window using PySide6."""
    def __init__(self, windows, **kwargs):

        super().__init__(windows, **kwargs)

        self.app = QApplication.instance() or QApplication(sys.argv)

        self.parent_window = QMainWindow()
        self.parent_window.setWindowTitle("Qt Camera Viewer")
        self.parent_window.setStyleSheet(f"background-color: {CONFIG['bgcolor']};")

        self.central_widget = QWidget()
        self.layout = QGridLayout(self.central_widget)
        self.parent_window.setCentralWidget(self.central_widget)

        # Add each sub-window to the layout
        n = len(self.windows)
        n1, n2 = DISPOSITIONS[n]  # dimensions of grid to place elements
        positions = itertools.product(range(n1), range(n2))

        for window, position in zip(self.windows, positions):
            window._create_labels()
            i, j = position
            self.layout.addWidget(window.widget, i, j)

        self.parent_window.resize(1024, 768)
        self.parent_window.show()

        # Timer for updating images
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_viewer)
        self.timer.start(int(self.dt_graph * 1000))

    def _update_viewer(self):
        """Single iteration of the viewer loop."""

        self._update_info()
        self._update_images()
        self._check_external_stop()

        if self.internal_stop.is_set():
            self.stop()

    def _run(self):
        """Run the viewer event loop."""
        self.app.exec()

    def stop(self):
        """Stop the viewer and close the parent window."""
        super().stop()
        self.timer.stop()
        self.parent_window.close()
        QApplication.instance().quit()
