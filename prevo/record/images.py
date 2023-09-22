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


Windows = {'cv': CvWindow,
           'mpl': MplWindow,
           'tk': TkWindow}

Viewers = {'cv': CvViewer,
           'mpl': MplViewer,
           'tk': TkViewer}


class ImageRecording(RecordingBase):
    """Recording class to record images and associated timestamps."""

    def __init__(self,
                 Sensor,
                 timestamp_filename,
                 path='.',
                 image_path=None,
                 extension=None,
                 ndigits=5,
                 quality=None,
                 column_names=None,
                 column_formats=None,
                 csv_separator='\t',
                 **kwargs):
        """Init ImageRecording object.

        Parameters
        ----------
        - Sensor: subclass of SensorBase.
        - timestamp_filename: name of csv/tsv file in which timestamp data
                              will be saved.
        - path: directory in which csv/tsv file will be created.
        - image_path: path in which individual images will be recorded. By
                      default, creates a folder with the name of the sensor
                      in the 'path' directory defined above.
        - extension: e.g. '.tif', '.jpg', etc. of the saved images (None: default)
        - ndigits: number of digits for the image counter in the filename
        - quality: for compressed image formats (e.g. jpg, tif), see
        https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html
        - column_names: iterable of str (name of columns in csv file)
        - column_formats: iterable of str (optional, str formatting)
        - csv_separator: character to separate columns in CSV file.

        Additional kwargs from RecordingBase:
        - dt: time interval between readings (default 1s).
        - ctrl_ppties: optional iterable of properties (ControlledProperty
                       objects) to control on the recording in addition to
                       default ones (time interval and active on/off)
        - active: if False, do not read data until self.active set to True.
        - saving: if False, do not save data to file until self.saving set to
                  True (note: data acquired during periods with saving=False
                  will not be saved later. This happens e.g. when one just
                  want to plot data without saving it).
        - continuous: if True, take data as fast as possible from sensor.
        - warnings: if True, print warnings of Timer (e.g. loop too short).
        - precise: if True, use precise timer in oclock (see oclock.Timer).
        - immediate: if False, changes in the timer (e.g interval) occur
                     at the next timestep. If True, a new data point is
                     taken immediately.
        - programs: iterable of programs, which are object of the
                    prevo.control.Program class or subclasses.
                    --> optional pre-defined temporal pattern of change of
                    properties of recording (e.g. define some times during
                    which sensor is active or not, or change time interval
                    between data points after some time, etc.)
        - control_params: dict {command: kwargs} containing any kwargs to pass
                          to the program controls (e.g. dt, range_limits, etc.)
                          Note: if None, use default params
                          (see RecordingControl class)
        - dt_save: how often (in seconds) queues are checked and written to files
                   (it is also how often files are open/closed)
        - dt_check: time interval (in seconds) for checking queue sizes.
        """
        super().__init__(Sensor=Sensor, path=path, **kwargs)

        # Here, file manager manages only the timestamp file, not the images
        self.file_manager = CsvFile(filename=timestamp_filename,
                                    column_names=column_names,
                                    column_formats=column_formats,
                                    path=path,
                                    csv_separator=csv_separator)

        self.image_path = self.path / Sensor.name if image_path is None else image_path
        self.image_path.mkdir(exist_ok=True)

        self.column_names = column_names

        if extension is None:
            # because for fast recording, .tif saving is much faster than png
            self.extension = '.tif' if self.continuous else '.png'
        else:
            self.extension = extension

        self.quality = quality
        self.ndigits = ndigits
        self.fmt = f'0{self.ndigits}'

        # number of images already recorded when record is called
        # (e.g. due to previous recording interrupted and restared)
        # The with open creates the file if not exists yet.
        with open(self.file_manager.file, 'a', encoding='utf8'):
            n_lines = self.file_manager.number_of_lines()
        self.num = n_lines - 1 if n_lines > 1 else 0

    def format_measurement(self, data):
        """How to format the data"""
        return {'name': self.name, 'num': self.num, **data}

    def after_measurement(self):
        """What to do after formatting data."""
        self.num += 1  # update number of recorded images for specific sensor

    def _generate_image_filename(self, measurement):
        """How to name images. Can be subclassed."""
        basename = f"{self.name}-{measurement['num']:{self.fmt}}"
        return basename + self.extension

    def _save_image(self, measurement, file):
        """How to save images to individual files. Can be subclassed."""
        img = measurement['image']
        if self.quality is None:
            Image.fromarray(img).save(file)
        else:
            Image.fromarray(img).save(file, quality=self.quality)

    def _save_timestamp(self, measurement, file):
        """How to save timestamps and other info to (opened) timestamp file"""
        filename = self._generate_image_filename(measurement)
        info = {'filename': filename, **measurement}
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
    """Main class managing simultaneous temporal recordings of images."""

    def __init__(self,
                 recordings,
                 metadata_filename='Images_Metadata.json',
                 checked_modules=(),
                 dt_graph=0.02,
                 viewer='tk',
                 dirty_ok=True,
                 **kwargs):
        """Init ImageRecord object.

        Parameters
        ----------
        - recordings: iterable of recording objects (RecordingBase or subclass)
        - metadata_filename: name of .json file in which metadata is saved
        - checked_modules: iterable of python modules, the version of which
                           will be saved in metadata, in addition to prevo.
        - dt_graph: time interval to refresh numerical graph.
        - viewer: type of viewer to display images ('mpl', 'tk' or 'cv)
        - dirty_ok: if False, record cannot be started if git repositories are
                    not clean (commited).

        Additional kwargs from RecordingBase:
        - path: directory in which data is recorded.
        - on_start: optional iterable of objects with a .start() or .run()
                    method, that need to be started at the same time as
                    Record.start().
                    Note: for now, start() and run() need to be non-blocking.
        - dt_request: time interval (in seconds) for checking user requests
                      (e.g. graph pop-up)
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

    def _save_metadata(self, filename):
        """To be able to call save_metadata() with arbitrary filenames"""
        metadata_file = self.path / filename

        if metadata_file.exists():
            metadata_file = increment_filename(metadata_file)

        info = {}

        for name, recording in self.image_recordings.items():

            info[name] = {
                'sensor': repr(recording.Sensor),
                'initial image number': recording.num,
                'extension': recording.extension,
                'digit number': recording.ndigits,
                'quality': str(recording.quality),
                **recording.info,
            }

        gittools.save_metadata(metadata_file,
                               info=info,
                               module=self.checked_modules,
                               dirty_warning=True,
                               dirty_ok=self.dirty_ok,
                               notag_warning=True,
                               nogit_ok=True,
                               nogit_warning=True)

    def save_metadata(self):
        """Save sensor info and version of modules used"""
        self._save_metadata(filename=self.metadata_filename)

    def data_plot(self):
        """What to do when graph event is triggered"""

        Viewer = Viewers[self.viewer]
        Window = Windows[self.viewer]

        windows = []
        for name, recording in self.image_recordings.items():
            image_queue = recording.queues['plotting']
            win = Window(image_queue, name=name, show_num=True, show_fps=True)
            windows.append(win)

        viewer = Viewer(windows,
                        external_stop=self.internal_stop,
                        dt_graph=self.dt_graph)
        viewer.start()
