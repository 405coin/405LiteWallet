





























from typing import Mapping

from .camera_dialog import (QrReaderCameraDialog, CameraError, NoCamerasFound,
                            get_camera_path)
from .validator import (QrReaderValidatorResult, AbstractQrReaderValidator,
                        QrReaderValidatorCounting, QrReaderValidatorColorizing,
                        QrReaderValidatorStrong, QrReaderValidatorCounted)


def find_system_cameras() -> Mapping[str, str]:

    from PyQt6.QtMultimedia import QMediaDevices
    system_cameras = QMediaDevices.videoInputs()
    return {cam.description(): get_camera_path(cam) for cam in system_cameras}
