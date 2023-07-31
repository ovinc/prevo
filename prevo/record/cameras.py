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


# Local imports
from .csv import CsvFile

# Optional, nonstandard
try:
    from PIL import Image
except ModuleNotFoundError:
    pass


class CameraRecording(RecordingBase):
    """Recording class to record camera images and associated timestamps."""

    def __init__(self,
                 timestamp_filename,
                 *args,
                 extension=None,
                 ndigits=5,
                 quality=None,
                 column_names=None,
                 column_formats=None,
                 path='.',
                 image_path='.',
                 csv_separator='\t',
                 **kwargs):

        super().__init__(*args, **kwargs)

        # Here, file manager manages only the timestamp file, not the images
        self.file_manager = CsvFile(filename=timestamp_filename,
                                    column_names=column_names,
                                    column_formats=column_formats,
                                    path=path,
                                    csv_separator=csv_separator)

        self.image_path = image_path
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
        n_lines = self.timestamp_file.number_of_lines()
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
        self.timestamp_file._write_line(data, file)

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
