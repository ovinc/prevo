"""Record several sensors as a function of time with interactive CLI and graph."""

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

# Non-standard
import gittools
import prevo

# Local imports
from .general import RecordingBase, Record
from ..csv import CsvFile
from ..viewers import CvWindow, CvViewer
from ..viewers import TkWindow, TkViewer
from ..viewers import MplWindow, MplViewer
from ..misc import increment_filename

# Optional, nonstandard
try:
    from PIL import Image
except ModuleNotFoundError:
    pass


Windows = {
    "cv": CvWindow,
    "mpl": MplWindow,
    "tk": TkWindow,
}

Viewers = {
    "cv": CvViewer,
    "mpl": MplViewer,
    "tk": TkViewer,
}


class ImageRecording(RecordingBase):
    """Recording class for saving images and their associated timestamps."""

    def __init__(
        self,
        Sensor,
        timestamp_filename,
        path=".",
        image_path=None,
        extension=None,
        ndigits=5,
        quality=None,
        column_names=None,
        column_formats=None,
        csv_separator="\t",
        **kwargs,
    ):
        """Initialize an ImageRecording object.

        Parameters
        ----------
        Sensor : subclass of SensorBase
            Sensor class responsible for capturing images.
        timestamp_filename : str
            Name of the CSV/TSV file where timestamp data will be saved.
        path : str, default="."
            Directory where the CSV/TSV file will be created.
        image_path : str, optional
            Path where individual images will be saved. If None, a folder named
            after the sensor will be created in the `path` directory.
        extension : str, optional
            File extension for saved images (e.g., '.tif', '.jpg'). If None,
            a default extension will be used.
        ndigits : int, default=5
            Number of digits for the image counter in the filename.
        quality : int, optional
            Quality parameter for compressed image formats (e.g., JPEG, TIFF).
            Refer to the Pillow documentation for details:
            https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html
        column_names : iterable of str, optional
            Names of the columns in the CSV file.
        column_formats : iterable of str, optional
            Optional string formatting for each column in the CSV file.
        csv_separator : str, default="\t"
            Character used to separate columns in the CSV file.

        **kwargs : dict, optional
            Additional keyword arguments inherited from RecordingBase:
            dt : float, default=1
                Time interval (in seconds) between sensor readings.
            ctrl_ppties : iterable, optional
                Iterable of ControlledProperty objects to control during
                recording, in addition to default properties.
            active : bool, default=True
                If False, data reading is disabled until `self.active` is set
                to True.
            saving : bool, default=True
                If False, data will not be saved until `self.saving` is set to
                True. Data acquired while `saving=False` will not be saved later.
            continuous : bool, default=False
                If True, data is acquired as fast as possible from the sensor.
            warnings : bool, default=False
                If True, print warnings from the Timer (e.g., loop too short).
            precise : bool, default=False
                If True, use a precise timer in `oclock` (see `oclock.Timer`).
            immediate : bool, default=True
                If False, changes to the timer occur at the next timestep. If
                True, a new data point is taken immediately.
            programs : iterable, optional
                Iterable of Program objects for predefined temporal patterns of
                property changes.
            control_params : dict, optional
                Dictionary of `{command: kwargs}` to pass to program controls.
                If None, default parameters are used (see `RecordingControl`).
            dt_save : float, default=1.3
                Time interval (in seconds) for writing queues to files.
            dt_check : float, default=0.9
                Time interval (in seconds) for checking queue sizes.
        """
        super().__init__(Sensor=Sensor, path=path, **kwargs)

        # Here, file manager manages only the timestamp file, not the images
        self.file_manager = CsvFile(
            path=self.path / timestamp_filename,
            column_names=column_names,
            column_formats=column_formats,
            csv_separator=csv_separator,
        )

        self.image_path = self.path / Sensor.name if image_path is None else image_path
        self.image_path.mkdir(exist_ok=True)

        self.column_names = column_names

        if extension is None:
            # because for fast recording, .tif saving is much faster than png
            self.extension = ".tif" if self.continuous else ".png"
        else:
            self.extension = extension

        self.quality = quality
        self.ndigits = ndigits
        self.fmt = f"0{self.ndigits}"

        # number of images already recorded when record is called
        # (e.g. due to previous recording interrupted and restared)
        # The with open creates the file if not exists yet.
        with open(self.file_manager.path, "a", encoding="utf8"):
            n_lines = self.file_manager.number_of_lines()
        self.num = n_lines - 1 if n_lines > 1 else 0

    def format_measurement(self, data):
        """How to format the data"""
        return {"name": self.name, "num": self.num, **data}

    def after_measurement(self):
        """What to do after formatting data."""
        self.num += 1  # update number of recorded images for specific sensor

    def _generate_image_filename(self, measurement):
        """How to name images. Can be subclassed."""
        basename = f"{self.name}-{measurement['num']:{self.fmt}}"
        return basename + self.extension

    def _save_image(self, measurement, file):
        """How to save images to individual files. Can be subclassed."""
        img = measurement["image"]
        if self.quality is None:
            Image.fromarray(img).save(file)
        else:
            Image.fromarray(img).save(file, quality=self.quality)

    def _save_timestamp(self, measurement, file):
        """How to save timestamps and other info to (opened) timestamp file"""
        filename = self._generate_image_filename(measurement)
        info = {"filename": filename, **measurement}
        data = [info[x] for x in self.column_names]
        self.file_manager._write_line(data, file)

    def save(self, measurement, file):
        """Write data to .tsv file with format: datetime / delta_t / value(s).

        Input
        -----
        - data: dict of data from the read() function
        - file: file in which to save the data
        """
        img_filename = self._generate_image_filename(measurement)
        self._save_image(measurement, file=self.image_path / img_filename)
        self._save_timestamp(measurement, file=file)

    @property
    def info(self):
        """Additional metadata info to save in metadata file. Subclass."""
        return {}


class ImageRecord(Record):
    """Main class for managing simultaneous temporal recordings of images."""

    def __init__(
        self,
        recordings,
        metadata_filename="Images_Metadata.json",
        checked_modules=(),
        dt_graph=0.02,
        viewer="tk",
        dirty_ok=True,
        **kwargs,
    ):
        """Initialize an ImageRecord object.

        Parameters
        ----------
        recordings : iterable
            Iterable of recording objects (RecordingBase or its subclasses).
        metadata_filename : str, default="Images_Metadata.json"
            Name of the JSON file where metadata will be saved.
        checked_modules : iterable, optional
            Iterable of Python modules whose versions will be saved in the
            metadata, in addition to the `prevo` module.
        dt_graph : float, default=0.02
            Time interval (in seconds) to refresh the numerical graph.
        viewer : str, default="tk"
            Type of viewer to display images. Possible values: 'mpl', 'tk', 'cv'.
        dirty_ok : bool, default=True
            If False, the recording cannot be started if Git repositories are
            not clean (uncommitted changes).

        **kwargs : dict, optional
            Additional keyword arguments inherited from Record:
            path : str, default="."
                Directory where recorded data will be saved.
            on_start : iterable, optional
                Iterable of objects with `.start()` or `.run()` methods. These
                methods are called when `Record.start()` is invoked. Note:
                `.start()` and `.run()` must be non-blocking.
            dt_request : float, default=0.7
                Time interval (in seconds) for checking user requests, such as
                graph pop-ups.
        """

        super().__init__(recordings=recordings, **kwargs)
        self.metadata_filename = metadata_filename
        self.checked_modules = set((prevo,) + tuple(checked_modules))

        # Viewing options -------------
        self.dt_graph = dt_graph
        self.viewer = viewer

        self.dirty_ok = dirty_ok
        self.get_image_recordings()

    def get_image_recordings(self):
        """Useful when combined with other recording types (e.g. vacuum)"""
        self.image_recordings = {}
        for name, recording in self.recordings.items():
            if issubclass(recording.__class__, ImageRecording):
                self.image_recordings[name] = recording

    def _save_metadata(self):
        """To be able to call save_metadata() with arbitrary filenames"""
        metadata_file = self.path / self.metadata_filename

        if metadata_file.exists():
            metadata_file = increment_filename(metadata_file)

        info = {}

        for name, recording in self.image_recordings.items():
            info[name] = {
                "sensor": repr(recording.Sensor),
                "initial image number": recording.num,
                "extension": recording.extension,
                "digit number": recording.ndigits,
                "quality": str(recording.quality),
                **recording.info,
            }

        gittools.save_metadata(
            metadata_file,
            info=info,
            module=self.checked_modules,
            dirty_warning=True,
            dirty_ok=self.dirty_ok,
            notag_warning=True,
            nogit_ok=True,
            nogit_warning=True,
        )

    def data_plot(self):
        """What to do when graph event is triggered"""

        Viewer = Viewers[self.viewer]
        Window = Windows[self.viewer]

        windows = []
        for name, recording in self.image_recordings.items():
            image_queue = recording.queues["plotting"]
            win = Window(
                image_queue,
                name=name,
                show_num=True,
                show_fps=True,
            )
            windows.append(win)

        viewer = Viewer(
            windows,
            external_stop=self.internal_stop,
            dt_graph=self.dt_graph,
        )
        viewer.start()
