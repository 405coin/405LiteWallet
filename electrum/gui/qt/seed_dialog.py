
























from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QVBoxLayout, QCheckBox, QHBoxLayout, QLineEdit,
                             QLabel, QCompleter, QStyledItemDelegate,
                             QWidget, QPushButton, QFrame)

from electrum.i18n import _
from electrum.mnemonic import Mnemonic, calc_seed_type, is_any_2fa_seed_type
from electrum import old_mnemonic
from electrum import slip39
from electrum.util import ChoiceItem

from .util import (
    Buttons, OkButton, WWLabel, ButtonsTextEdit,
    CloseButton, WindowModalDialog, ColorScheme, font_height, ChoiceWidget,
    read_QIcon, apply_dashboard_dialog_style,
)
from .qrtextedit import ShowQRTextEdit, ScanQRTextEdit
from .completion_text_edit import CompletionTextEdit

if TYPE_CHECKING:
    from electrum.simple_config import SimpleConfig


MSG_PASSPHRASE_WARN_ISSUE4566 = _("Warning") + ": "\
                              + _("You have multiple consecutive whitespaces or leading/trailing "
                                  "whitespaces in your passphrase.") + " "\
                              + _("This is discouraged.") + " "\
                              + _("Due to a bug, old versions of 405LiteWallet will NOT be creating the "
                                  "same wallet as newer versions or other software.")


def seed_warning_msg(seed):
    return ''.join([
        "<p>",
        _("Please save these {0} words on paper (order is important). "),
        _("This seed will allow you to recover your wallet in case "
          "of computer failure."),
        "</p>",
        "<b>" + _("WARNING") + ":</b>",
        "<ul>",
        "<li>" + _("Never disclose your seed.") + "</li>",
        "<li>" + _("Never type it on a website.") + "</li>",
        "<li>" + _("Do not store it electronically.") + "</li>",
        "</ul>"
    ]).format(len(seed.split()))


class SeedWidget(QWidget):

    updated = pyqtSignal()
    validChanged = pyqtSignal([bool], arguments=['valid'])

    def __init__(
            self,
            seed=None,
            title=None,
            icon=True,
            msg=None,
            options=None,
            is_seed=None,
            passphrase=None,
            parent=None,
            for_seed_words=True,
            *,
            config: 'SimpleConfig',
            show_seed_controls=True,
    ):
        QWidget.__init__(self, parent)
        apply_dashboard_dialog_style(self, "SeedEntryWidget")
        vbox = QVBoxLayout()
        vbox.setContentsMargins(24, 24, 24, 24)
        vbox.setSpacing(18)
        self.setLayout(vbox)

        from electrum import constants
        if options:
            options = list(options)
            if getattr(constants.net, 'DISABLE_BIP39', False):
                options = [opt for opt in options if opt != 'bip39']
        self.options = options
        self.config = config
        self.msg = msg

        if options:
            self.seed_types = [
                ChoiceItem(key=stype, label=label) for stype, label in (
                    ('electrum', _('405LiteWallet')),
                    ('bip39', _('BIP39 seed')),
                    ('slip39', _('SLIP39 seed')),
                )
                if stype in self.options
            ]
            assert len(self.seed_types)
            self.seed_type = self.seed_types[0].key
        else:
            self.seed_type = 'electrum'

        self.is_seed = is_seed
        self.show_seed_controls = show_seed_controls

        if title:
            vbox.addWidget(WWLabel(title))
        if seed:
            if for_seed_words:
                self.seed_e = ButtonsTextEdit()
            else:
                self.seed_e = ShowQRTextEdit(config=self.config)
                self.seed_e.addCopyButton()
            self.seed_e.setReadOnly(True)
            self.seed_e.setText(seed)
        else:
            assert for_seed_words
            self.seed_e = CompletionTextEdit()
            self.seed_e.setTabChangesFocus(False)
            self.seed_e.textChanged.connect(self.on_edit)
            self.initialize_completer()

        self.seed_e.setMaximumHeight(max(75, 5 * font_height()))
        hbox = QHBoxLayout()
        if icon:
            logo = QLabel()
            logo.setPixmap(read_QIcon("seed.svg").pixmap(64, 64))
            logo.setMaximumWidth(60)
            hbox.addWidget(logo)
        hbox.addWidget(self.seed_e)
        vbox.addLayout(hbox)
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        self.seed_type_label = QLabel('')
        hbox.addWidget(self.seed_type_label)
        vbox.addLayout(hbox)

        self.is_ext = False
        self.seed_type_choice = None
        self.ext_checkbox = None
        if options and show_seed_controls:
            self._build_options_panel(vbox)
        if passphrase:
            hbox = QHBoxLayout()
            passphrase_e = QLineEdit()
            passphrase_e.setText(passphrase)
            passphrase_e.setReadOnly(True)
            hbox.addWidget(QLabel(_("Your seed extension is") + ':'))
            hbox.addWidget(passphrase_e)
            vbox.addLayout(hbox)


        self.slip39_mnemonic_index = 0
        self.slip39_mnemonics = [""]
        self.slip39_seed = None
        self.slip39_current_mnemonic_invalid = None
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        self.prev_share_btn = QPushButton(_("Previous share"))
        self.prev_share_btn.clicked.connect(self.on_prev_share)
        hbox.addWidget(self.prev_share_btn)
        self.next_share_btn = QPushButton(_("Next share"))
        self.next_share_btn.clicked.connect(self.on_next_share)
        hbox.addWidget(self.next_share_btn)
        self.update_share_buttons()
        vbox.addLayout(hbox)

        vbox.addStretch(1)
        self.seed_status = WWLabel('')
        vbox.addWidget(self.seed_status)
        self.seed_warning = WWLabel('')
        if msg:
            self.seed_warning.setText(seed_warning_msg(seed))
        else:
            self.update_seed_warning()

        vbox.addWidget(self.seed_warning)

    def _build_options_panel(self, parent_layout: QVBoxLayout) -> None:
        panel = QFrame()
        panel.setObjectName("SeedOptionsCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        if len(self.seed_types) > 1:
            self.seed_type_choice = ChoiceWidget(
                message=_('Seed format'),
                choices=self.seed_types,
                default_key=self.seed_type,
            )
            self.seed_type_choice.itemSelected.connect(self._on_seed_type_selected)
            layout.addWidget(self.seed_type_choice)
        if self.options and 'ext' in self.options:
            self.ext_checkbox = QCheckBox(_('Extend this seed with custom words'))
            self.ext_checkbox.setChecked(self.is_ext)
            self.ext_checkbox.stateChanged.connect(self._on_ext_toggled)
            layout.addWidget(self.ext_checkbox)
        layout.addStretch(1)
        parent_layout.addWidget(panel)

    def _on_seed_type_selected(self, idx: int) -> None:
        if not self.seed_type_choice:
            return
        self.seed_type = self.seed_type_choice.selected_key
        self.slip39_current_mnemonic_invalid = None
        self.seed_status.setText('')
        self.update_seed_warning()
        self.on_edit()
        self.update_share_buttons()
        self.initialize_completer()

    def _on_ext_toggled(self, state: int) -> None:
        self.is_ext = bool(state)
        self.update_seed_warning()
        self.updated.emit()

    def update_seed_warning(self):
        if self.msg:
            return

        if self.seed_type == 'bip39':
            message = ' '.join([
                '<b>' + _('Warning') + ':</b>  ',
                _('BIP39 seeds can be imported in 405LiteWallet, so that users can access funds locked in other wallets.'),
                _('However, we do not generate BIP39 seeds, because they do not meet our safety standard.'),
                _('BIP39 seeds do not include a version number, which compromises compatibility with future software.'),
                _('We do not guarantee that BIP39 imports will always be supported in 405LiteWallet.'),
            ])
        elif self.seed_type == 'slip39':
            message = ' '.join([
                '<b>' + _('Warning') + ':</b>  ',
                _('SLIP39 seeds can be imported in 405LiteWallet, so that users can access funds locked in other wallets.'),
                _('However, we do not generate SLIP39 seeds.'),
            ])
        else:
            message = ''

        self.seed_warning.setText(message)

    def initialize_completer(self):
        if self.seed_type != 'slip39':
            bip39_english_list = Mnemonic('en').wordlist
            old_list = old_mnemonic.wordlist
            only_old_list = set(old_list) - set(bip39_english_list)
            self.wordlist = list(bip39_english_list) + list(only_old_list)
            self.wordlist.sort()

            class CompleterDelegate(QStyledItemDelegate):
                def initStyleOption(self, option, index):
                    super().initStyleOption(option, index)




                    if option.text in only_old_list:

                        option.backgroundBrush = ColorScheme.YELLOW.as_color(background=True)

            delegate = CompleterDelegate(self.seed_e)
        else:
            self.wordlist = list(slip39.get_wordlist())
            delegate = None

        self.completer = QCompleter(self.wordlist)
        if delegate:
            self.completer.popup().setItemDelegate(delegate)
        self.seed_e.set_completer(self.completer)

    def get_seed_words(self):
        return self.seed_e.text().split()

    def get_seed(self):
        if self.seed_type != 'slip39':
            return ' '.join(self.get_seed_words())
        else:
            return self.slip39_seed

    def on_edit(self):
        s = ' '.join(self.get_seed_words())
        if self.seed_type == 'bip39':
            from electrum.keystore import bip39_is_checksum_valid
            is_checksum, is_wordlist = bip39_is_checksum_valid(s)
            label = ''
            valid = bool(s)
            if valid:
                label = ('' if is_checksum else _('BIP39 checksum failed')) if is_wordlist else _('Unknown BIP39 wordlist')
        elif self.seed_type == 'slip39':
            self.slip39_mnemonics[self.slip39_mnemonic_index] = s
            try:
                slip39.decode_mnemonic(s)
            except slip39.Slip39Error as e:
                share_status = str(e)
                current_mnemonic_invalid = True
            else:
                share_status = _('Valid.')
                current_mnemonic_invalid = False

            label = _('SLIP39 share') + ' #%d: %s' % (self.slip39_mnemonic_index + 1, share_status)


            if not (self.slip39_current_mnemonic_invalid and current_mnemonic_invalid):
                self.slip39_seed, seed_status = slip39.process_mnemonics(self.slip39_mnemonics)
                self.seed_status.setText(seed_status)
            self.slip39_current_mnemonic_invalid = current_mnemonic_invalid

            valid = self.slip39_seed is not None
            self.update_share_buttons()
        else:
            valid = self.is_seed(s)
            t = calc_seed_type(s)
            label = _('Seed Type') + ': ' + t if t else ''
            if t and not valid:
                wiztype_fullname = _('Wallet with two-factor authentication') if is_any_2fa_seed_type(t) else _("Standard wallet")
                msg = ' '.join([
                    '<b>' + _('Warning') + ':</b>  ',
                    _("Looks like you have entered a valid seed of type '{}' but this dialog does not support such seeds.").format(t),
                    _("If unsure, try restoring as '{}'.").format(wiztype_fullname),
                ])
                self.seed_warning.setText(msg)
            else:
                self.seed_warning.setText("")

        self.seed_type_label.setText(label)
        self.validChanged.emit(valid)


        for word in self.get_seed_words()[:-1]:
            if word not in self.wordlist:
                self.seed_e.disable_suggestions()
                return
        self.seed_e.enable_suggestions()

    def update_share_buttons(self):
        if self.seed_type != 'slip39':
            self.prev_share_btn.hide()
            self.next_share_btn.hide()
            return

        finished = self.slip39_seed is not None
        self.prev_share_btn.show()
        self.next_share_btn.show()
        self.prev_share_btn.setEnabled(self.slip39_mnemonic_index != 0)
        self.next_share_btn.setEnabled(

            self.slip39_mnemonic_index < len(self.slip39_mnemonics) - 1

            or (bool(self.seed_e.text().strip()) and not self.slip39_current_mnemonic_invalid and not finished)
        )

    def on_prev_share(self):
        if not self.slip39_mnemonics[self.slip39_mnemonic_index]:
            del self.slip39_mnemonics[self.slip39_mnemonic_index]

        self.slip39_mnemonic_index -= 1
        self.seed_e.setText(self.slip39_mnemonics[self.slip39_mnemonic_index])
        self.slip39_current_mnemonic_invalid = None

    def on_next_share(self):
        if not self.slip39_mnemonics[self.slip39_mnemonic_index]:
            del self.slip39_mnemonics[self.slip39_mnemonic_index]
        else:
            self.slip39_mnemonic_index += 1

        if len(self.slip39_mnemonics) <= self.slip39_mnemonic_index:
            self.slip39_mnemonics.append("")
            self.seed_e.setFocus()
        self.seed_e.setText(self.slip39_mnemonics[self.slip39_mnemonic_index])
        self.slip39_current_mnemonic_invalid = None


class KeysWidget(QWidget):

    validChanged = pyqtSignal([bool], arguments=['valid'])

    def __init__(
            self,
            parent=None,
            header_layout=None,
            is_valid=None,
            allow_multi=False,
            *,
            config: 'SimpleConfig',
    ):
        QWidget.__init__(self, parent)
        vbox = QVBoxLayout()
        self.setLayout(vbox)

        self.is_valid = is_valid
        self.text_e = ScanQRTextEdit(allow_multi=allow_multi, config=config)
        self.text_e.textChanged.connect(self.on_edit)
        if isinstance(header_layout, str):
            vbox.addWidget(WWLabel(header_layout))
        else:
            vbox.addLayout(header_layout)
        vbox.addWidget(self.text_e)

    def get_text(self):
        return self.text_e.text()

    def on_edit(self):
        try:
            valid = self.is_valid(self.get_text())
        except Exception as e:
            valid = False
        self.validChanged.emit(valid)


class SeedDialog(WindowModalDialog):

    def __init__(self, parent, seed, passphrase, *, config: 'SimpleConfig'):
        WindowModalDialog.__init__(self, parent, ('405LiteWallet - ' + _('Seed')))
        apply_dashboard_dialog_style(self, "SeedDialog")
        self.setMinimumWidth(400)
        vbox = QVBoxLayout(self)
        title = _("Your wallet generation seed is:")
        seed_widget = SeedWidget(title=title, seed=seed, msg=True, passphrase=passphrase, config=config)
        vbox.addWidget(seed_widget)
        vbox.addLayout(Buttons(CloseButton(self)))
