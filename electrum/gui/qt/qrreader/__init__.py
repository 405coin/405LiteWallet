






















import sys
from typing import Callable, Optional, TYPE_CHECKING, Mapping, Sequence

from PyQt6.QtWidgets import QMessageBox, QWidget
from PyQt6.QtGui import QImage, QPainter, QColor
from PyQt6.QtCore import QRect, QCoreApplication
from PyQt6 import QtCore

from electrum.i18n import _
from electrum.util import UserFacingException
from electrum.logging import get_logger
from electrum.qrreader import get_qr_reader, QrCodeResult, MissingQrDetectionLib

from electrum.gui.qt.util import MessageBoxMixin, custom_message_box


if TYPE_CHECKING:
    from electrum.simple_config import SimpleConfig


_logger = get_logger(__name__)


def scan_qrcode_from_camera(
        *,
        parent: Optional[QWidget],
        config: 'SimpleConfig',
        callback: Callable[[bool, str, Optional[str]], None],
) -> None:

    assert parent is None or isinstance(parent, QWidget), f"parent should be a QWidget, not {parent!r}"
    def do_scan():
        _scan_qrcode_from_camera(parent=parent, config=config, callback=callback)

    if _has_camera_permission():
        do_scan()
    else:


        app = QCoreApplication.instance()
        app.requestPermission(QtCore.QCameraPermission(), lambda _x: do_scan())


def scan_qr_from_image(image: QImage) -> Sequence[QrCodeResult]:

    qr_reader = get_qr_reader()

    for attempt in range(4):
        image_y800 = image.convertToFormat(QImage.Format.Format_Grayscale8)
        res = qr_reader.read_qr_code(
            image_y800.constBits().__int__(),
            image_y800.sizeInBytes(),
            image_y800.bytesPerLine(),
            image_y800.width(),
            image_y800.height(),
        )
        if res:
            break

        image = _reduce_qr_code_density(image)
    return res

def _reduce_qr_code_density(image: QImage) -> QImage:

    new_image = QImage(image.width(), image.height(), QImage.Format.Format_RGB32)
    new_image.fill(QColor(255, 255, 255))

    painter = QPainter(new_image)
    source_rect = QRect(0, 0, image.width(), image.height())
    target_rect = QRect(0, 0, int(image.width() * 0.75), int(image.height() * 0.75))
    painter.drawImage(target_rect, image, source_rect)
    painter.end()

    return new_image

def find_system_cameras() -> Mapping[str, str]:

    if sys.platform == 'darwin' or sys.platform in ('windows', 'win32'):
        try:
            from .qtmultimedia import find_system_cameras
        except (ImportError, RuntimeError) as e:
            _logger.exception('error importing .qtmultimedia')
            return {}
        else:
            return find_system_cameras()
    else:
        from electrum import qrscanner
        return qrscanner.find_system_cameras()




def _scan_qrcode_using_zbar(
        *,
        parent: Optional[QWidget],
        config: 'SimpleConfig',
        callback: Callable[[bool, str, Optional[str]], None],
) -> None:
    from electrum import qrscanner
    data = None
    try:
        data = qrscanner.scan_barcode(config.get_video_device())
    except UserFacingException as e:
        success = False
        error = str(e)
    except BaseException as e:
        _logger.exception('camera error')
        success = False
        error = repr(e)
    else:
        success = True
        error = ""
    if data is None:

        success = False
    callback(success, error, data)



_qr_dialog = None


def _scan_qrcode_using_qtmultimedia(
        *,
        parent: Optional[QWidget],
        config: 'SimpleConfig',
        callback: Callable[[bool, str, Optional[str]], None],
) -> None:
    try:
        from .qtmultimedia import QrReaderCameraDialog, CameraError
    except (ImportError, RuntimeError) as e:
        icon = QMessageBox.Icon.Warning
        title = _("QR Reader Error")
        message = _("QR reader failed to load. This may happen if "
                    "you are using an older version of PyQt.") + "\n\n" + str(e)
        _logger.exception(message)
        if isinstance(parent, MessageBoxMixin):
            parent.msg_box(title=title, text=message, icon=icon, parent=None)
        else:
            custom_message_box(title=title, text=message, icon=icon, parent=parent)
        return

    global _qr_dialog
    if _qr_dialog:
        _logger.warning("QR dialog is already presented, ignoring.")
        return
    _qr_dialog = None
    try:
        _qr_dialog = QrReaderCameraDialog(parent=parent, config=config)

        def _on_qr_reader_finished(success: bool, error: str, data):
            global _qr_dialog
            if _qr_dialog:
                _qr_dialog.deleteLater()
                _qr_dialog = None
            callback(success, error, data)

        _qr_dialog.qr_finished.connect(_on_qr_reader_finished)
        _qr_dialog.start_scan(config.get_video_device())
    except (MissingQrDetectionLib, CameraError) as e:
        _qr_dialog = None
        callback(False, str(e), None)
    except Exception as e:
        _logger.exception('camera error')
        _qr_dialog = None
        callback(False, repr(e), None)


def _scan_qrcode_from_camera(
        *,
        parent: Optional[QWidget],
        config: 'SimpleConfig',
        callback: Callable[[bool, str, Optional[str]], None],
) -> None:

    assert parent is None or isinstance(parent, QWidget), f"parent should be a QWidget, not {parent!r}"
    if not _has_camera_permission():
        callback(False, _("Missing camera permission."), None)
        return
    if sys.platform == 'darwin' or sys.platform in ('windows', 'win32'):
        _scan_qrcode_using_qtmultimedia(parent=parent, config=config, callback=callback)
    else:
        _scan_qrcode_using_zbar(parent=parent, config=config, callback=callback)


def _has_camera_permission() -> bool:
    if not hasattr(QtCore, "QCameraPermission"):
        _logger.info(f"QtCore does not support QCameraPermission. This requires Qt 6.5+")
        return True
    app = QCoreApplication.instance()
    permission_status = app.checkPermission(QtCore.QCameraPermission())
    return permission_status == QtCore.Qt.PermissionStatus.Granted

