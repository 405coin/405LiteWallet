from typing import List, Tuple

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFontMetrics, QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
)

from .util import read_QIcon
from electrum.i18n import _


NAV_ITEMS = [
    ("Activity", 'history', "tab_history.svg"),
    ("Send", 'send', "tab_send.svg"),
    ("Receive", 'receive', "tab_receive.svg"),
]


class DashboardContainer(QWidget):


    def __init__(self, window, tabs: QWidget, coincontrol_widget: QWidget):
        super().__init__(window)
        self.window = window
        self.tabs = tabs
        self.coincontrol_widget = coincontrol_widget

        self.sidebar = DashboardSidebar(window, NAV_ITEMS)
        self.main = DashboardMain(window, tabs, coincontrol_widget)

        self.setObjectName("DashboardRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.main.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        layout.addWidget(self.sidebar, 0)
        layout.addWidget(self.main, 1)

        self.setStyleSheet("""
            #DashboardRoot {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 #040b22, stop:1 #0e1d4a);
            }
            QFrame#DashboardSidebar {
                background-color: transparent;
                border: none;
            }
            QFrame#DashboardMainRoot {
                background-color: transparent;
                border: none;
            }
            QFrame#DashboardBalanceCard {
                background-color: rgba(13,22,58,0.9);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 20px;
            }
            QLabel#DashboardTitle {
                color: #f9fbff;
                font-size: 18px;
                font-weight: 600;
            }
            QLabel#DashboardBalanceValue {
                color: #ffffff;
                font-size: 34px;
                font-weight: 600;
            }
            QLabel#DashboardBalanceUnit {
                color: rgba(216,224,255,0.85);
                font-size: 18px;
                font-weight: 600;
            }
            QLabel#DashboardBalanceFiat {
                color: rgba(198,206,251,0.8);
                font-size: 13px;
            }
            QLabel#DashboardSectionTitle {
                color: rgba(211,219,255,0.75);
                font-size: 13px;
                font-weight: 600;
                letter-spacing: 0.08em;
            }
            QPushButton.SideList {
                background-color: rgba(32,50,118,0.82);
                color: rgba(236,239,255,0.9);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 16px;
                padding: 14px 20px;
                text-align: left;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton.SideList:hover {
                background-color: rgba(53,76,149,0.95);
            }
            QPushButton.SideList[active="true"] {
                background-color: rgba(103,132,234,0.98);
                border-color: rgba(255,255,255,0.4);
                color: #ffffff;
            }
        """)

    def refresh(self):
        self.sidebar.refresh()
        self.sidebar.mark_tab_active(self.tabs.currentWidget())

    def mark_tab_active(self, current_widget: QWidget):
        self.sidebar.mark_tab_active(current_widget)


class DashboardSidebar(QFrame):
    def __init__(self, window, nav_items):
        super().__init__(window)
        self.window = window
        self.nav_items = nav_items
        self.setObjectName("DashboardSidebar")
        self.setFixedWidth(220)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.nav_buttons: List[Tuple[QPushButton, str]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        self.title_label = QLabel("405 Lite Wallet")
        self.title_label.setObjectName("DashboardTitle")
        root.addWidget(self.title_label)
        root.addSpacing(10)

        self.balance_card = QFrame()
        self.balance_card.setObjectName("DashboardBalanceCard")
        bal_layout = QVBoxLayout(self.balance_card)
        bal_layout.setContentsMargins(16, 14, 16, 14)
        bal_layout.setSpacing(4)

        amount_row = QHBoxLayout()
        amount_row.setContentsMargins(0, 0, 0, 0)
        amount_row.setSpacing(6)
        self.amount_row = amount_row
        self.balance_value = QLabel("0")
        self.balance_value.setObjectName("DashboardBalanceValue")
        self._balance_base_font_size = self.balance_value.font().pointSizeF() or self.balance_value.font().pointSize()
        self.balance_unit = QLabel("405")
        self.balance_unit.setObjectName("DashboardBalanceUnit")
        amount_row.addWidget(self.balance_value)
        amount_row.addWidget(self.balance_unit)
        amount_row.addStretch(1)
        bal_layout.addLayout(amount_row)

        self.balance_fiat = QLabel("")
        self.balance_fiat.setObjectName("DashboardBalanceFiat")
        bal_layout.addWidget(self.balance_fiat)

        root.addWidget(self.balance_card)
        root.addSpacing(6)

        nav_header = QLabel(_("Navigation"))
        nav_header.setObjectName("DashboardSectionTitle")
        root.addWidget(nav_header)

        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(24)
        root.addLayout(nav_layout)

        for label, key, icon_name in self.nav_items:
            btn = QPushButton(label, self)
            btn.setProperty("class", "SideList")
            btn.setProperty("active", "false")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(read_QIcon(icon_name))
            btn.setIconSize(QSize(18, 18))
            btn.setFlat(True)
            btn.setMinimumHeight(54)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda checked=False, k=key: window.switch_to_tab(k))
            nav_layout.addWidget(btn)
            self.nav_buttons.append((btn, key))
        nav_layout.addStretch(1)

        root.addStretch(1)

    def refresh(self):
        wallet = self.window.wallet
        c, u, x = wallet.get_balance()
        sat = c + u + x
        amount_text = self.window.format_amount(sat)
        amount_text = amount_text.rstrip('.') if amount_text else "0"
        self.balance_value.setText(amount_text)
        self.balance_unit.setText(self.window.base_unit())
        fiat = self._format_fiat(sat)
        self.balance_fiat.setText(f"≈ {fiat}" if fiat else "")
        self._adjust_balance_font()
        self.mark_tab_active(self.window.tabs.currentWidget())

    def _format_fiat(self, sat: int) -> str:
        fx = getattr(self.window, 'fx', None)
        if fx and fx.is_enabled():
            return fx.format_amount(sat, True) or ""
        return ""

    def mark_tab_active(self, current_widget: QWidget):
        mapping = {
            'history': getattr(self.window, 'history_tab', None),
            'send': self.window.send_tab,
            'receive': self.window.receive_tab,
        }
        for btn, key in self.nav_buttons:
            target = mapping.get(key)
            is_active = target is current_widget
            btn.setProperty('active', "true" if is_active else "false")
            btn.setChecked(is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def update_lock_icon(self):
        return

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adjust_balance_font()

    def _adjust_balance_font(self):
        if not self.balance_value or not self.balance_card.width():
            return
        rect_width = self.balance_card.contentsRect().width()
        if rect_width <= 0:
            return
        available = rect_width
        layout = self.balance_card.layout()
        if layout:
            margins = layout.contentsMargins()
            available -= margins.left() + margins.right()
        spacing = self.amount_row.spacing() if hasattr(self, "amount_row") else 6
        unit_width = self.balance_unit.sizeHint().width()
        available -= unit_width + spacing + 8
        if available <= 0:
            return
        base_size = self._balance_base_font_size or 34
        font = QFont(self.balance_value.font())
        font.setPointSizeF(base_size)
        metrics = QFontMetrics(font)
        text = self.balance_value.text() or ""
        size = base_size
        while metrics.horizontalAdvance(text) > available and size > 10:
            size -= 1
            font.setPointSizeF(size)
            metrics = QFontMetrics(font)
        self.balance_value.setFont(font)
        self.balance_value.setStyleSheet(
            f"color: #ffffff; font-weight: 600; font-size: {size}px;"
        )


class DashboardMain(QFrame):


    def __init__(self, window, tabs: QWidget, coincontrol_widget: QWidget):
        super().__init__(window)
        self.window = window
        self.tabs = tabs
        self.coincontrol_widget = coincontrol_widget
        self.setObjectName("DashboardMainRoot")
        self.setMinimumWidth(440)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: transparent;
            }
            QTabWidget QWidget {
                background-color: transparent;
                color: #f0f5ff;
            }
            QTabWidget QScrollArea {
                background-color: transparent;
            }
            QTableView, QTreeView, QListView, QTextEdit {
                background-color: transparent;
                border: none;
            }
            QHeaderView::section {
                background-color: transparent;
                color: rgba(255,255,255,0.8);
                border: none;
                padding: 6px;
            }
        """)
        self.tabs.tabBar().hide()
        layout.addWidget(self.tabs, 1)
        self.coincontrol_widget.setVisible(False)
