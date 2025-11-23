



from typing import Optional, TYPE_CHECKING

from PyQt6.QtGui import QFont, QMouseEvent
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (QLabel, QVBoxLayout, QGridLayout, QTextEdit,
                             QHBoxLayout, QPushButton, QWidget, QSizePolicy, QFrame, QStackedLayout, QStyle)

from electrum.i18n import _
from electrum.util import InvoiceError
from electrum.logging import Logger

from .util import read_QIcon, WWLabel, MessageBoxMixin, MONOSPACE_FONT

if TYPE_CHECKING:
    from .main_window import ElectrumWindow


class ReceiveTab(QWidget, MessageBoxMixin, Logger):


    addr = ''
    lnaddr = ''
    URI = ''
    address_help = ''
    URI_help = ''
    ln_help = ''

    def __init__(self, window: 'ElectrumWindow'):
        QWidget.__init__(self, window)
        Logger.__init__(self)

        self.window = window
        self.wallet = window.wallet
        self.fx = window.fx
        self.config = window.config



        self.receive_grid = grid = QGridLayout()
        grid.setVerticalSpacing(14)
        grid.setHorizontalSpacing(12)
        grid.setColumnStretch(1, 1)

        text = _('Request') if not self.wallet.has_lightning() else _('Onchain')
        self.create_onchain_invoice_button = QPushButton(text)
        self.create_onchain_invoice_button.setIcon(read_QIcon("bitcoin.png"))
        self._scale_request_button_icon(self.create_onchain_invoice_button, factor=2)
        self.create_onchain_invoice_button.clicked.connect(lambda: self.create_invoice(False))
        self.create_lightning_invoice_button = QPushButton(_('Lightning'))
        self.create_lightning_invoice_button.setIcon(read_QIcon("lightning.png"))
        self.create_lightning_invoice_button.clicked.connect(lambda: self.create_invoice(True))
        self.create_lightning_invoice_button.setVisible(self.wallet.has_lightning())

        self.receive_e = QTextEdit()
        self.receive_e.setFont(QFont(MONOSPACE_FONT))
        self.receive_e.setReadOnly(True)
        self.receive_e.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.receive_e.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.receive_e.setPlaceholderText(_('Generate a payment request to display the address here.'))
        self.receive_e.setObjectName("DashboardReceiveOutput")
        self.receive_e.setFixedHeight(72)
        self.receive_e.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.receive_e.textChanged.connect(self.update_receive_widgets)

        self.receive_qr = None

        self.receive_help_text = WWLabel('')
        self.receive_help_text.setLayout(QHBoxLayout())
        self.receive_rebalance_button = QPushButton('Rebalance')
        self.receive_rebalance_button.suggestion = None
        self.receive_zeroconf_button = QPushButton(_('Accept'))
        self.receive_zeroconf_button.clicked.connect(self.on_accept_zeroconf)

        def on_receive_rebalance():
            if self.receive_rebalance_button.suggestion:
                chan1, chan2, delta = self.receive_rebalance_button.suggestion
                self.window.rebalance_dialog(chan1, chan2, amount_sat=delta)
        self.receive_rebalance_button.clicked.connect(on_receive_rebalance)
        self.receive_swap_button = QPushButton('Swap')
        self.receive_swap_button.suggestion = None

        def on_receive_swap():
            if self.receive_swap_button.suggestion:
                chan, swap_recv_amount_sat = self.receive_swap_button.suggestion
                self.window.run_swap_dialog(is_reverse=True, recv_amount_sat_or_max=swap_recv_amount_sat, channels=[chan])
        self.receive_swap_button.clicked.connect(on_receive_swap)
        buttons = QHBoxLayout()
        buttons.addWidget(self.receive_rebalance_button)
        buttons.addWidget(self.receive_swap_button)
        buttons.addWidget(self.receive_zeroconf_button)
        vbox = QVBoxLayout()
        vbox.addWidget(self.receive_help_text)
        vbox.addLayout(buttons)
        self.receive_help_widget = FramedWidget()
        self.receive_help_widget.setObjectName("DashboardReceiveHint")
        self.receive_help_widget.setVisible(False)
        self.receive_help_widget.setLayout(vbox)
        self.receive_help_widget.setFixedHeight(72)
        self.receive_help_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.receive_widget = ReceiveWidget(self, self.receive_e, None, self.receive_help_widget)
        self.receive_widget.setVisible(False)

        self.receive_requests_label = QLabel(_('Requests'))
        from .request_list import RequestList
        self.request_list = RequestList(self)
        self.request_list.setObjectName("DashboardRequestList")

        self.toolbar, menu = self.request_list.create_toolbar_with_menu('')

        self.toggle_qr_button = QPushButton(_('Copy'))
        req_height = max(
            self.create_onchain_invoice_button.sizeHint().height(),
            self.create_onchain_invoice_button.iconSize().height() + 14,
        )
        req_height += 2
        self.toggle_qr_button.setFixedHeight(req_height)
        self.toggle_qr_button.clicked.connect(self.copy_current)


        menu.addAction(_("Import requests"), self.window.import_requests)
        menu.addAction(_("Export requests"), self.window.export_requests)
        menu.addAction(_("Delete expired requests"), self.request_list.delete_expired_requests)
        self.toolbar_menu = menu

        form_card = QFrame()
        form_card.setObjectName("DashboardReceivePanel")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(28, 28, 28, 28)
        form_layout.setSpacing(18)
        form_layout.addLayout(self.toolbar)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(12)
        actions_row.addStretch(1)
        actions_row.addWidget(self.toggle_qr_button)
        actions_row.addWidget(self.create_onchain_invoice_button)
        actions_row.addWidget(self.create_lightning_invoice_button)
        form_layout.addLayout(actions_row)

        form_wrapper = QWidget()
        form_wrapper.setObjectName("DashboardReceiveForm")
        form_wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        form_wrapper.setMinimumWidth(560)
        inner_layout = QVBoxLayout(form_wrapper)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(18)
        inner_layout.addLayout(grid)

        receive_display = QFrame()
        receive_display.setObjectName("DashboardReceiveDisplay")
        receive_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        receive_display.setMinimumHeight(140)
        receive_display_layout = QVBoxLayout(receive_display)
        receive_display_layout.setContentsMargins(18, 18, 18, 18)
        receive_display_layout.addWidget(self.receive_widget)
        self.receive_widget.setVisible(True)
        inner_layout.addWidget(receive_display)
        form_layout.addWidget(form_wrapper)

        form_layout.addWidget(self.receive_requests_label)
        self.request_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.request_list.setMinimumHeight(260)
        self.request_list_card = QFrame()
        self.request_list_card.setObjectName("DashboardRequestListCard")
        self.request_list_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_layout = QVBoxLayout(self.request_list_card)
        card_layout.setContentsMargins(18, 12, 18, 12)
        card_layout.addWidget(self.request_list)
        form_layout.addWidget(self.request_list_card)
        form_layout.setStretchFactor(self.receive_widget, 1)
        form_layout.setStretchFactor(self.request_list_card, 1000)

        self.searchable_list = self.request_list
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(12)
        vbox.addWidget(form_card)
        self.request_list.update()
        self._apply_dashboard_style()

    @staticmethod
    def _scale_request_button_icon(button: QPushButton, factor: int = 2):

        if factor <= 1:
            return
        icon_size = button.iconSize()
        if icon_size.isEmpty():
            metric = button.style().pixelMetric(QStyle.PixelMetric.PM_ButtonIconSize, None, button)
            icon_size = QSize(metric, metric)
        button.setIconSize(QSize(icon_size.width() * factor, icon_size.height() * factor))

    def copy_current(self):
        text, data, help_text, title = self.get_tab_data()
        if text:
            self.window.do_copy(text, title=title)

    def _apply_dashboard_style(self):
        self.setObjectName("DashboardReceiveTab")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
        QWidget#DashboardReceiveTab {
            background-color: transparent;
        }
        QFrame#DashboardReceivePanel {
            background-color: #141b3b;
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 20px;
        }
        QWidget#DashboardReceiveForm {
            background-color: transparent;
        }
        QFrame#DashboardReceiveDisplay {
            background-color: rgba(255,255,255,0.04);
            border-radius: 18px;
        }
        QFrame#DashboardRequestListCard {
            background-color: rgba(255,255,255,0.04);
            border-radius: 18px;
            border: 1px solid rgba(255,255,255,0.08);
        }
        QTextEdit#DashboardReceiveOutput {
            background-color: rgba(0,0,0,0.35);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            color: #f4f6ff;
        }
        QWidget#DashboardReceiveHint {
            border: none;
            color: rgba(244,246,255,0.85);
        }
        QWidget#DashboardReceiveTab QLabel:!flat {
            color: rgba(244,246,255,0.95);
            padding: 3px 0;
            border: none;
        }
        QWidget#DashboardReceiveTab QLineEdit,
        QWidget#DashboardReceiveTab QTextEdit,
        QWidget#DashboardReceiveTab QPlainTextEdit {
            background-color: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 10px;
            padding: 6px 10px;
            min-height: 21px;
            color: #f7f9ff;
            selection-color: #04081a;
            selection-background-color: rgba(146,169,255,0.65);
        }
        QWidget#DashboardReceiveTab QTextEdit,
        QWidget#DashboardReceiveTab QPlainTextEdit {
            min-height: 36px;
        }
        QWidget#DashboardReceiveTab QLineEdit:focus,
        QWidget#DashboardReceiveTab QTextEdit:focus,
        QWidget#DashboardReceiveTab QPlainTextEdit:focus {
            border-color: rgba(255,255,255,0.85);
            background-color: rgba(44,58,130,0.98);
        }
        QWidget#DashboardReceiveTab QPushButton {
            background-color: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            color: #eff1ff;
            padding: 8px 16px;
            font-weight: 500;
        }
        QWidget#DashboardReceiveTab QPushButton:hover {
            background-color: rgba(255,255,255,0.16);
            border-color: rgba(255,255,255,0.18);
        }
        QWidget#DashboardReceiveTab QPushButton:disabled {
            color: rgba(239,241,255,0.35);
            background-color: rgba(255,255,255,0.04);
            border-color: rgba(255,255,255,0.04);
        }
        QTreeView#DashboardRequestList {
            background-color: transparent;
            border: none;
            color: #f4f6ff;
        }
        QTreeView#DashboardRequestList::item:selected {
            background-color: rgba(255,255,255,0.18);
        }
        QTreeView#DashboardRequestList::item {
            padding: 4px 6px;
        }
        QTreeView#DashboardRequestList QHeaderView::section {
            background-color: transparent;
            color: rgba(255,255,255,0.85);
            border: none;
            padding: 6px 10px;
        }
        """)

    def on_tab_changed(self):
        self.get_tab_data()

    def do_copy(self, e: 'QMouseEvent'):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        text, data, help_text, title = self.get_tab_data()
        self.window.do_copy(text, title=title)

    def update_receive_widgets(self):
        self.receive_widget.update_visibility(False)

    def update_current_request(self):
        if len(self.request_list.selectionModel().selectedRows(0)) > 1:
            key = None
        else:
            key = self.request_list.get_current_key()
        req = self.wallet.get_request(key) if key else None
        if req is None:
            self.receive_e.setText('')
            self.addr = self.URI = self.lnaddr = ''
            self.address_help = self.URI_help = self.ln_help = ''
            self.receive_widget.setVisible(True)
            self.receive_widget.update_visibility(False)
            self.receive_help_text.setText('')
            self.toggle_qr_button.setEnabled(False)
            return
        help_texts = self.wallet.get_help_texts_for_receive_request(req)
        self.addr = (req.get_address() or '') if not help_texts.address_is_error else ''
        uri = (self.wallet.get_request_URI(req) or '') if not help_texts.URI_is_error else ''
        if uri.startswith('bitcoin:'):
            uri = uri.replace('bitcoin:', '405:', 1)
        self.URI = uri
        self.lnaddr = self.wallet.get_bolt11_invoice(req) if not help_texts.ln_is_error else ''
        self.address_help = help_texts.address_help
        self.URI_help = help_texts.URI_help
        self.ln_help = help_texts.ln_help
        can_rebalance = help_texts.can_rebalance()
        can_swap = help_texts.can_swap()
        can_zeroconf = help_texts.can_zeroconf()
        self.receive_rebalance_button.suggestion = help_texts.ln_rebalance_suggestion
        self.receive_swap_button.suggestion = help_texts.ln_swap_suggestion
        self.receive_rebalance_button.setVisible(can_rebalance)
        self.receive_swap_button.setVisible(can_swap)
        self.receive_rebalance_button.setEnabled(can_rebalance and self.window.num_tasks() == 0)
        self.receive_swap_button.setEnabled(can_swap and self.window.num_tasks() == 0)
        self.receive_zeroconf_button.setVisible(can_zeroconf)
        self.receive_zeroconf_button.setEnabled(can_zeroconf)
        text, data, help_text, title = self.get_tab_data()
        self.receive_e.setText(text)
        self.receive_help_text.setText(help_text)
        self.receive_help_widget.setVisible(bool(help_text))
        for w in [self.receive_e]:
            w.setEnabled(bool(text) and (not help_text or can_zeroconf))
            w.setToolTip(help_text)

        self.receive_e.repaint()

        if can_zeroconf:


            self.receive_widget.show_help()
        self.receive_widget.setVisible(True)
        self.toggle_qr_button.setEnabled(True)

    def on_accept_zeroconf(self):
        self.receive_zeroconf_button.setVisible(False)
        self.update_receive_widgets()

    def get_tab_data(self):
        if self.URI:
            out = self.URI, self.URI, self.URI_help, _('Bitcoin URI')
        elif self.addr:
            out = self.addr, self.addr, self.address_help, _('Address')
        else:


            out = self.lnaddr, self.lnaddr.upper(), self.ln_help, _('Lightning Request')
        return out

    def create_invoice(self, is_lightning: bool):
        amount_sat = None
        message = ''
        expiry = self.config.WALLET_PAYREQ_EXPIRY_SECONDS
        if is_lightning:
            address = None
        else:
            address = self.get_bitcoin_address_for_request(None)
            if not address:
                return
            self.window.address_list.update()

        try:
            key = self.wallet.create_request(amount_sat, message, expiry, address)
        except InvoiceError as e:
            self.show_error(_('Error creating payment request') + ':\n' + str(e))
            return
        except Exception as e:
            self.logger.exception('Error adding payment request')
            self.show_error(_('Error adding payment request') + ':\n' + repr(e))
            return
        assert key is not None
        self.window.address_list.refresh_all()
        self.request_list.update()
        self.request_list.set_current_key(key)
        self.on_tab_changed()

    def get_bitcoin_address_for_request(self, amount) -> Optional[str]:
        addr = self.wallet.get_unused_address()
        if addr is None:
            if not self.wallet.is_deterministic():
                msg = [
                    _('No more addresses in your wallet.'), ' ',
                    _('You are using a non-deterministic wallet, which cannot create new addresses.'), ' ',
                    _('If you want to create new addresses, use a deterministic wallet instead.'), '\n\n',
                    _('Creating a new payment request will reuse one of your addresses and overwrite an existing request. Continue anyway?'),
                   ]
                if not self.question(''.join(msg)):
                    return
                addr = self.wallet.get_receiving_address()
            else:
                self._show_receive_warning(_('The maximum number of receiving addresses has been used for this seed phrase.'))
                return
        return addr

    def _show_receive_warning(self, message: str):

        self.receive_help_text.setText(message)
        self.receive_help_widget.setVisible(True)
        self.receive_widget.show_help()
        self.receive_rebalance_button.setVisible(False)
        self.receive_swap_button.setVisible(False)
        self.receive_zeroconf_button.setVisible(False)

    def do_clear(self):
        self.receive_e.setText('')
        self.addr = self.URI = self.lnaddr = ''
        self.address_help = self.URI_help = self.ln_help = ''
        self.toggle_qr_button.setEnabled(False)
        self.request_list.clearSelection()


class ReceiveWidget(QWidget):
    HELP_VIEW = 0
    TEXT_VIEW = 1
    QR_VIEW = 2

    def __init__(self, receive_tab: 'ReceiveTab', textedit: QWidget, qr: QWidget, help_widget: QWidget):
        QWidget.__init__(self)
        self.textedit = textedit
        self.qr = qr
        self.help_widget = help_widget

        textedit.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.stack = QStackedLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(help_widget)
        self.stack.addWidget(textedit)
        if qr:
            self.stack.addWidget(qr)
        self.stack.setCurrentIndex(self.TEXT_VIEW)
        self.setFixedHeight(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def update_visibility(self, is_qr):
        has_text = bool(self.textedit.toPlainText())
        if self.qr and is_qr and has_text:
            self.stack.setCurrentIndex(self.QR_VIEW)
        elif self.stack.currentIndex() == self.HELP_VIEW and not has_text:

            return
        else:
            self.stack.setCurrentIndex(self.TEXT_VIEW)

    def show_help(self):
        self.stack.setCurrentIndex(self.HELP_VIEW)


class FramedWidget(QFrame):
    def __init__(self):
        QFrame.__init__(self)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("FramedWidget {border:1px solid gray; border-radius:2px; }")
