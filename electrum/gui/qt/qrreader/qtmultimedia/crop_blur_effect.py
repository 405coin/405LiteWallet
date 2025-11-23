
























from PyQt6.QtWidgets import QGraphicsBlurEffect, QGraphicsEffect
from PyQt6.QtGui import QPainter, QTransform, QRegion
from PyQt6.QtCore import QObject, QRect, QPoint, Qt


class QrReaderCropBlurEffect(QGraphicsBlurEffect):
    CROP_OFFSET_ENABLED = False
    CROP_OFFSET = QPoint(5, 5)

    BLUR_DARKEN = 0.25
    BLUR_RADIUS = 8

    def __init__(self, parent: QObject, crop: QRect = None):
        super().__init__(parent)
        self.crop = crop
        self.setBlurRadius(self.BLUR_RADIUS)

    def setCrop(self, crop: QRect = None):
        self.crop = crop

    def draw(self, painter: QPainter):
        assert self.crop, 'crop must be set'


        all_region = QRegion(painter.viewport())
        crop_region = QRegion(self.crop)
        blur_region = all_region.subtracted(crop_region)


        painter.setClipRegion(blur_region)


        if self.BLUR_DARKEN > 0.0:
            painter.fillRect(painter.viewport(), Qt.GlobalColor.black)
            painter.setOpacity(1 - self.BLUR_DARKEN)


        super().draw(painter)


        painter.setClipping(False)
        painter.setOpacity(1.0)


        pixmap, offset = self.sourcePixmap(Qt.CoordinateSystem.DeviceCoordinates, QGraphicsEffect.PixmapPadMode.NoPad)
        painter.setWorldTransform(QTransform())


        source = self.crop
        if self.CROP_OFFSET_ENABLED:
            source = source.translated(self.CROP_OFFSET)
        painter.drawPixmap(self.crop.topLeft() + offset, pixmap, source)
