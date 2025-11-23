
























from typing import List

from PyQt6.QtMultimedia import (QVideoFrame, QVideoFrameFormat, QVideoSink)
from PyQt6.QtGui import QImage
from PyQt6.QtCore import QObject, pyqtSignal

from electrum.i18n import _
from electrum.logging import get_logger


_logger = get_logger(__name__)


class QrReaderVideoSurface(QVideoSink):


    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self.videoFrameChanged.connect(self._on_new_frame)

    def _on_new_frame(self, frame: QVideoFrame) -> None:
        if not frame.isValid():
            return

        image_format = QVideoFrameFormat.imageFormatFromPixelFormat(frame.pixelFormat())
        if image_format == QVideoFrameFormat.PixelFormat.Format_Invalid:
            _logger.info(_('QR code scanner for video frame with invalid pixel format'))
            return

        if not frame.map(QVideoFrame.MapMode.ReadOnly):
            _logger.info(_('QR code scanner failed to map video frame'))
            return

        try:
            img = frame.toImage()


            surface_format = frame.surfaceFormat()
            flip_x = surface_format.isMirrored()
            flip_y = surface_format.scanLineDirection() == QVideoFrameFormat.Direction.BottomToTop


            if flip_x or flip_y:
                img = img.mirrored(flip_x, flip_y)


            img = img.copy()
        finally:
            frame.unmap()

        self.frame_available.emit(img)

    frame_available = pyqtSignal(QImage)
