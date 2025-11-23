from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel

from electrum.i18n import _
from electrum.wizard import TermsOfUseWizard
from electrum.gui.qt.util import WWLabel, icon_path
from electrum.gui import messages
from .wizard import QEAbstractWizard, WizardComponent

if TYPE_CHECKING:
    from electrum.simple_config import SimpleConfig
    from electrum.gui.qt import QElectrumApplication


class QETermsOfUseWizard(TermsOfUseWizard, QEAbstractWizard):
    def __init__(self, config: 'SimpleConfig', app: 'QElectrumApplication'):
        TermsOfUseWizard.__init__(self, config)
        QEAbstractWizard.__init__(self, config, app)
        self.window_title = _('Terms of Use')
        self.finish_label = _('I Accept')
        self.title.setVisible(False)

        self.next_button.setToolTip("You accept the Terms of Use by clicking this button.")


        self.navmap_merge({
            'terms_of_use': {'gui': WCTermsOfUseScreen, 'params': {'icon': None}},
        })

class WCTermsOfUseScreen(WizardComponent):
    def __init__(self, parent, wizard):
        WizardComponent.__init__(self, parent, wizard, title='')
        self.wizard_title = _('405LiteWallet Terms of Use')
        hero = QLabel()
        pixmap = QPixmap(icon_path('electrum_presplash.png'))
        if not pixmap.isNull():
            hero.setPixmap(pixmap.scaledToWidth(360, mode=Qt.TransformationMode.SmoothTransformation))
            hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout().addWidget(hero)
        self.layout().addSpacing(15)

        self.tos_label = WWLabel()
        self.tos_label.setText(messages.MSG_TERMS_OF_USE)
        self.layout().addWidget(self.tos_label)
        self._valid = True

    def apply(self):
        pass
