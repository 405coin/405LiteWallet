
























from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from .qrcodewidget import QRCodeWidget

from electrum.i18n import _


class QR_Window(QWidget):

    def __init__(self, win):
        QWidget.__init__(self)
        self.main_window = win
        self.setWindowTitle('405LiteWallet - '+_('Payment Request'))
        self.setMinimumSize(800, 800)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        main_box = QHBoxLayout()
        self.qrw = QRCodeWidget()
        main_box.addWidget(self.qrw, 1)
        self.setLayout(main_box)

    def closeEvent(self, event):
        self.main_window.receive_tab.qr_menu_action.setChecked(False)
