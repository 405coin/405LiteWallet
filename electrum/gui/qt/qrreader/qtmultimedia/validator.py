
























from typing import List, Dict, Callable, Any
from abc import ABC, abstractmethod

from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt

from electrum.i18n import _
from electrum.qrreader import QrCodeResult

from electrum.gui.qt.util import ColorScheme, QColorLerp


class QrReaderValidatorResult():


    def __init__(self):
        self.accepted: bool = False

        self.message: str = None
        self.message_color: QColor = None

        self.simple_result : str = None

        self.result_usable: Dict[QrCodeResult, bool] = {}
        self.result_colors: Dict[QrCodeResult, QColor] = {}
        self.result_messages: Dict[QrCodeResult, str] = {}

        self.selected_results: List[QrCodeResult] = []


class AbstractQrReaderValidator(ABC):


    @abstractmethod
    def validate_results(self, results: List[QrCodeResult]) -> QrReaderValidatorResult:
        pass


class QrReaderValidatorCounting(AbstractQrReaderValidator):


    result_counts: Dict[QrCodeResult, int] = {}

    def validate_results(self, results: List[QrCodeResult]) -> QrReaderValidatorResult:
        res = QrReaderValidatorResult()

        for result in results:

            if result not in self.result_counts:
                self.result_counts[result] = 0
            self.result_counts[result] += 1


        for result in self.result_counts.copy():

            if result in results:
                continue
            self.result_counts[result] -= 2

            if self.result_counts[result] < 1:
                del self.result_counts[result]

        return res

class QrReaderValidatorColorizing(QrReaderValidatorCounting):


    WEAK_COLOR: QColor = QColor(Qt.GlobalColor.red)
    STRONG_COLOR: QColor = QColor(Qt.GlobalColor.green)

    strong_count: int = 2



    def validate_results(self, results: List[QrCodeResult]) -> QrReaderValidatorResult:
        res = super().validate_results(results)


        for result in results:

            self.result_counts[result] = min(self.result_counts[result], self.strong_count)


            lerp_factor = (self.result_counts[result] - 1) / self.strong_count
            lerped_color = QColorLerp(self.WEAK_COLOR, self.STRONG_COLOR, lerp_factor)
            res.result_colors[result] = lerped_color

        return res

class QrReaderValidatorStrong(QrReaderValidatorColorizing):


    def validate_results(self, results: List[QrCodeResult]) -> QrReaderValidatorResult:
        res = super().validate_results(results)

        for result in results:
            if self.result_counts[result] >= self.strong_count:
                res.selected_results.append(result)
                break

        return res

class QrReaderValidatorCounted(QrReaderValidatorStrong):


    def __init__(self, minimum: int = 1, maximum: int = 1):
        super().__init__()
        self.minimum = minimum
        self.maximum = maximum

    def validate_results(self, results: List[QrCodeResult]) -> QrReaderValidatorResult:
        res = super().validate_results(results)

        num_results = len(res.selected_results)
        if num_results < self.minimum:
            if num_results > 0:
                res.message = _('Too few QR codes detected.')
                res.message_color = ColorScheme.RED.as_color()
        elif num_results > self.maximum:
            res.message = _('Too many QR codes detected.')
            res.message_color = ColorScheme.RED.as_color()
        else:
            res.accepted = True
            res.simple_result = (results and results[0].data) or ''

        return res
