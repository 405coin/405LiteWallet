import copy
import os
import threading
from abc import abstractmethod
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QSize, QMetaObject
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QDialog, QPushButton, QWidget, QLabel, QVBoxLayout, QScrollArea,
                             QHBoxLayout, QLayout, QFrame, QSizePolicy)

from electrum.i18n import _
from electrum.logging import get_logger
from electrum.gui.qt.util import Buttons, icon_path, MessageBoxMixin, WWLabel, ResizableStackedWidget, AbstractQWidget
from electrum import constants

if TYPE_CHECKING:
    from electrum.simple_config import SimpleConfig
    from electrum.gui.qt import QElectrumApplication
    from electrum.wizard import WizardViewState


APP_NAME = getattr(constants.net, "APP_NAME", "405 Lite Wallet")


class QEAbstractWizard(QDialog, MessageBoxMixin):

    _logger = get_logger(__name__)

    requestNext = pyqtSignal()
    requestPrev = pyqtSignal()

    def __init__(self, config: 'SimpleConfig', app: 'QElectrumApplication', *, start_viewstate: 'WizardViewState' = None):
        QDialog.__init__(self, None)
        self.app = app
        self.config = config


        self.gui_thread = threading.current_thread()

        self.setMinimumSize(1320, 900)
        self.setObjectName("WizardWindow")

        self.title = QLabel()
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setObjectName("WizardTitle")
        self.window_title = ''
        self.finish_label = _('Finish')

        self.main_widget = ResizableStackedWidget(self)

        self.back_button = QPushButton(_("Back"), self)
        self.back_button.clicked.connect(self.on_back_button_clicked)
        self.back_button.setEnabled(False)
        self.back_button.setDefault(False)
        self.back_button.setAutoDefault(False)
        self.back_button.setProperty("class", "WizardGhostButton")
        self.next_button = QPushButton(_("Next"), self)
        self.next_button.clicked.connect(self.on_next_button_clicked)
        self.next_button.setEnabled(False)
        self.next_button.setDefault(True)
        self.next_button.setAutoDefault(True)
        self.next_button.setProperty("class", "WizardPrimaryButton")
        self.requestPrev.connect(self.on_back_button_clicked)
        self.requestNext.connect(self.on_next_button_clicked)
        self.logo = QLabel()

        please_wait_layout = QVBoxLayout()
        please_wait_layout.addStretch(1)
        self.please_wait_l = QLabel(_("Please wait..."))
        self.please_wait_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        please_wait_layout.addWidget(self.please_wait_l)
        please_wait_layout.addStretch(1)
        self.please_wait = QWidget()
        self.please_wait.setVisible(False)
        self.please_wait.setLayout(please_wait_layout)

        error_layout = QVBoxLayout()
        error_layout.addStretch(1)
        error_icon = QLabel()
        error_icon.setPixmap(QPixmap(icon_path('warning.png')).scaledToWidth(48, mode=Qt.TransformationMode.SmoothTransformation))
        error_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_layout.addWidget(error_icon)
        self.error_msg = WWLabel()
        self.error_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_layout.addWidget(self.error_msg)
        error_layout.addStretch(1)
        self.error = QWidget()
        self.error.setVisible(False)
        self.error.setLayout(error_layout)

        inner_vbox = QVBoxLayout()
        inner_vbox.addWidget(self.title)
        inner_vbox.addWidget(self.main_widget)
        inner_vbox.addWidget(self.please_wait)
        inner_vbox.addWidget(self.error)

        scroll_widget = QWidget()
        scroll_widget.setObjectName("WizardScrollContent")
        scroll_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        scroll_widget.setLayout(inner_vbox)
        scroll = QScrollArea()
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll.setWidget(scroll_widget)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)

        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setMinimumHeight(140)

        self.card = QFrame()
        self.card.setObjectName("WizardCard")
        self.card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(48, 32, 48, 40)
        card_layout.setSpacing(14)
        card_layout.addWidget(self.logo, alignment=Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(scroll)

        outer_vbox = QVBoxLayout(self)
        outer_vbox.setContentsMargins(40, 16, 40, 32)
        outer_vbox.setSpacing(16)
        outer_vbox.addWidget(self.card, stretch=1)
        outer_vbox.addLayout(Buttons(self.back_button, self.next_button))

        self.setTabOrder(self.back_button, self.next_button)

        self.icon_spec = (None, None)
        self.default_icon = 'electrum.png'
        self.set_icon(self.default_icon)

        self.start_viewstate = start_viewstate

        self._apply_stylesheet()
        self.show()
        self.raise_()

        QMetaObject.invokeMethod(self, 'strt', Qt.ConnectionType.QueuedConnection)

    def sizeHint(self) -> QSize:
        return QSize(600, 400)

    @pyqtSlot()
    def strt(self):
        viewstate = self.start_wizard(start_viewstate=self.start_viewstate)
        self.load_next_component(viewstate.view, viewstate.wizard_data, viewstate.params)
        self.set_default_focus()


        self.refresh_gui()

    def refresh_gui(self):

        self.app.processEvents()
        self.app.processEvents()

    def load_next_component(self, view, wdata=None, params=None):
        if wdata is None:
            wdata = {}
        if params is None:
            params = {}

        comp = self.view_to_component(view)
        try:
            self._logger.debug(f'load_next_component: {comp!r}')
            page = comp(self.main_widget, self)
        except Exception as e:
            self._logger.error(f'not a class: {comp!r}')
            raise e
        page.wizard_data = copy.deepcopy(wdata)
        page.params = params
        page.on_ready()

        page.updated.connect(self.on_page_updated)


        page.apply()
        self.main_widget.setCurrentIndex(self.main_widget.addWidget(page))
        self.update()

    @pyqtSlot(object)
    def on_page_updated(self, page):
        page.apply()
        if page == self.main_widget.currentWidget():
            self.update()

    def set_icon(self, filename, target_width=None):
        prior_spec = getattr(self, 'icon_spec', (None, None))
        self.icon_spec = (filename, target_width)
        if not filename:
            self.logo.clear()
            self.logo.setMinimumHeight(0)
            self.logo.setVisible(False)
            return prior_spec

        path = filename if os.path.isabs(filename) else icon_path(filename)
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.logo.clear()
            self.logo.setMinimumHeight(0)
            self.logo.setVisible(False)
            return prior_spec

        if target_width is None:
            target_width = int(self.width() * 0.35)
            if target_width <= 0:
                target_width = 260
            target_width = max(200, min(420, target_width))
        scaled = pixmap.scaled(
            target_width,
            target_width,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.logo.setPixmap(scaled)
        self.logo.setMinimumHeight(scaled.height())
        self.logo.setVisible(True)
        return prior_spec

    def set_default_focus(self):
        page = self.main_widget.currentWidget()
        control = page.initialFocus()
        if control and control.isVisible() and control.isEnabled():
            control.setFocus()
        else:
            self.next_button.setFocus()

    def can_go_back(self) -> bool:
        return len(self._stack) > 0

    def update(self):
        page = self.main_widget.currentWidget()
        self.setWindowTitle(page.wizard_title if page.wizard_title else self.window_title)
        self.title.setText(f'<b>{page.title}</b>' if page.title else '')
        self.back_button.setText(_('Back') if self.can_go_back() else _('Cancel'))
        self.back_button.setEnabled(not page.busy)
        self.next_button.setText(_('Next') if not self.is_last(page.wizard_data) else self.finish_label)
        self.next_button.setEnabled(not page.busy and page.valid)
        self.main_widget.setVisible(not page.busy and not bool(page.error))
        self.please_wait.setVisible(page.busy)
        self.please_wait_l.setText(page.busy_msg if page.busy_msg else _("Please wait..."))
        self.error_msg.setText(str(page.error))
        self.error.setVisible(not page.busy and bool(page.error))
        icon = page.params.get('icon', self.default_icon)
        icon_width = page.params.get('icon_width') if getattr(page, 'params', None) else None
        if (icon, icon_width) != self.icon_spec:
            self.set_icon(icon, icon_width)
        else:
            self.logo.setVisible(bool(icon))

    def on_back_button_clicked(self):
        if self.can_go_back():
            self.prev()
            widget = self.main_widget.currentWidget()
            self.main_widget.removeWidget(widget)
            widget.deleteLater()
            self.update()
        else:
            self.close()

    def on_next_button_clicked(self):
        page = self.main_widget.currentWidget()
        page.apply()
        wd = page.wizard_data.copy()
        if self.is_last(wd):
            self.submit(wd)
            if self.is_finalized(wd):
                self.accept()
            else:
                self.prev()
        else:
            view = self.submit(wd)
            try:
                self.load_next_component(view.view, view.wizard_data, view.params)
                self.set_default_focus()
            except Exception as e:
                self.prev()
                raise e

    def start_wizard(self, *, start_viewstate: Optional['WizardViewState'] = None) -> 'WizardViewState':
        self.start(start_viewstate=start_viewstate)
        return self._current

    def view_to_component(self, view) -> QWidget:
        return self.navmap[view]['gui']

    def submit(self, wizard_data) -> 'WizardViewState':
        wdata = wizard_data.copy()
        view = self.resolve_next(self._current.view, wdata)
        return view

    def prev(self) -> dict:
        viewstate = self.resolve_prev()
        return viewstate.wizard_data

    def is_last(self, wizard_data: dict) -> bool:
        wdata = wizard_data.copy()
        return self.is_last_view(self._current.view, wdata)

    def is_finalized(self, wizard_data: dict) -> bool:

        return True

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            #WizardWindow {
                background-color: #0b1024;
            }
            QFrame#WizardCard {
                background-color: #141b3b;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 20px;
            }
            QLabel#WizardTitle {
                color: rgba(244,246,255,0.95);
                font-size: 22px;
                font-weight: 600;
                margin-bottom: 6px;
            }
            QLabel#WizardHeroTitle {
                font-size: 26px;
                font-weight: 700;
                color: rgba(244,246,255,0.95);
            }
            QLabel#WizardHeroSubtitle {
                color: rgba(159,176,255,0.95);
                font-size: 14px;
            }
            QLabel#WizardUnlockTitle {
                font-size: 18px;
                font-weight: 600;
                color: rgba(244,246,255,0.95);
            }
            QLabel#WizardWalletLabel {
                color: rgba(189,201,255,0.94);
                font-size: 14px;
            }
            QLabel#WizardPathHint {
                color: rgba(143,154,200,0.9);
                font-size: 13px;
            }
            QScrollArea {
                background: transparent;
            }
            QWidget#WizardScrollContent {
                background-color: transparent;
            }
            QPushButton {
                border-radius: 14px;
                padding: 12px 22px;
                font-weight: 600;
                color: rgba(244,246,255,0.95);
            }
            QPushButton[class="WizardPrimaryButton"] {
                background-color: #2f6bff;
                border: none;
            }
            QPushButton[class="WizardPrimaryButton"]:disabled {
                background-color: rgba(47, 107, 255, 0.3);
                color: rgba(255,255,255,0.4);
            }
            QPushButton[class="WizardGhostButton"] {
                background-color: transparent;
                color: rgba(244,246,255,0.75);
                border: 1px solid rgba(255,255,255,0.2);
            }
            QPushButton[class="WizardGhostButton"]:hover {
                border-color: rgba(255,255,255,0.35);
            }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: rgba(0,0,0,0.35);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px;
                padding: 10px 14px;
                color: #f4f6ff;
            }
            QCheckBox {
                color: rgba(244,246,255,0.95);
            }
            QLabel {
                color: rgba(244,246,255,0.95);
            }
        """)


class WizardComponent(AbstractQWidget):
    updated = pyqtSignal(object)

    def __init__(self, parent: QWidget, wizard: QEAbstractWizard, *, title: str = None, layout: QLayout = None):
        super().__init__(parent)
        self.setLayout(layout if layout else QVBoxLayout(self))
        self.wizard_data = {}
        self.title = title if title is not None else 'No title'
        self.wizard_title = None
        self.busy_msg = ''
        self.wizard = wizard
        self._error = ''
        self._valid = False
        self._busy = False

    @property
    def valid(self):
        return self._valid

    @valid.setter
    def valid(self, is_valid):
        if self._valid != is_valid:
            self._valid = is_valid
            self.on_updated()

    @property
    def busy(self):
        return self._busy

    @busy.setter
    def busy(self, is_busy):
        if self._busy != is_busy:
            self._busy = is_busy
            self.on_updated()

    @property
    def error(self):
        return self._error

    @error.setter
    def error(self, error):
        if self._error != error:
            self._error = error
            self.on_updated()

    @abstractmethod
    def apply(self):

        pass

    def on_ready(self):

        pass

    @pyqtSlot()
    def on_updated(self, *args):
        try:
            self.updated.emit(self)
        except RuntimeError:
            pass

    def initialFocus(self) -> Optional[QWidget]:

        return None
