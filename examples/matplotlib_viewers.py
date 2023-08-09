"""Examples for matplotlib viewers outside of Jupyter"""


from prevo.viewers import MplSingleViewer, MplMultipleViewer
from prevo.viewers import TkSingleViewer
from prevo.misc import PeriodicSensor
import numpy as np


class LapseCamera(PeriodicSensor):
    """Mock time-lapse camera returning white-noise images periodically"""

    name = 'Mock Lapse Camera'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.num = 0

    def _read(self):
        """Return image in a dict (see explanation below)"""
        img = np.random.randint(256, size=(480, 640), dtype='uint8')
        data = {'image': img, 'num': self.num}
        self.num += 1
        return data


def test_single(blit=False):
    camera = LapseCamera(interval=0.04)
    camera.start()
    MplSingleViewer(camera.queue, blit=blit, show_fps=True, show_num=True).start()
    camera.stop()


def test_multiple(blit=False):

    camera1 = LapseCamera(interval=0.1)
    camera2 = LapseCamera(interval=3)
    camera1.start()
    camera2.start()

    camera_queues = {
        'Camera 1': camera1.queue,
        'Camera 2': camera2.queue,
    }

    MplMultipleViewer(camera_queues, blit=blit, show_fps=True, show_num=True).start()

    camera1.stop()
    camera2.stop()


if __name__ == '__main__':
    test_multiple()