
























from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPixmap, QPainter, QPaintEvent


class QrReaderVideoWidget(QWidget):


    USE_BILINEAR_FILTER = True

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self.pixmap = None

    def paintEvent(self, _event: QPaintEvent):
        if not self.pixmap:
            return
        painter = QPainter(self)
        if self.USE_BILINEAR_FILTER:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(self.rect(), self.pixmap, self.pixmap.rect())

    def setPixmap(self, pixmap: QPixmap):
        self.pixmap = pixmap
        self.update()
