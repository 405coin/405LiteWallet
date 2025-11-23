from abc import ABC
import os
import sys
import threading

from typing import TYPE_CHECKING, Optional, List, Tuple

from PyQt6.QtCore import Qt, QTimer, QRect, pyqtSignal
from PyQt6.QtGui import QPen, QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget,
                             QFileDialog, QSlider, QGridLayout, QDialog, QApplication,
                             QCheckBox, QStackedLayout, QFrame, QSizePolicy)

from electrum.bip32 import is_bip32_derivation, BIP32Node, normalize_bip32_derivation, xpub_type
from electrum.daemon import Daemon
from electrum.i18n import _
from electrum.keystore import bip44_derivation, bip39_to_seed, purpose48_derivation, ScriptTypeNotSupported
from electrum.plugin import run_hook, HardwarePluginLibraryUnavailable
from electrum.storage import StorageReadWriteError
from electrum.util import WalletFileException, get_new_wallet_name, UserFacingException, InvalidPassword
from electrum.util import is_subpath, ChoiceItem, multisig_type, UserCancelled
from electrum.wallet import wallet_types
from .wizard import QEAbstractWizard, WizardComponent
from electrum.logging import get_logger, Logger
from electrum import WalletStorage, mnemonic, keystore, constants
from electrum.wallet_db import WalletDB
from electrum.wizard import NewWalletWizard, KeystoreWizard, WizardViewState

from electrum.gui.qt.bip39_recovery_dialog import Bip39RecoveryDialog
from electrum.gui.qt.password_dialog import PasswordLayout, PW_NEW, MSG_ENTER_PASSWORD, PasswordLayoutForHW
from electrum.gui.qt.seed_dialog import SeedWidget, MSG_PASSPHRASE_WARN_ISSUE4566, KeysWidget
from electrum.gui.qt.util import (PasswordLineEdit, char_width_in_lineedit, WWLabel, InfoButton, font_height,
                                  ChoiceWidget, MessageBoxMixin, icon_path, IconLabel, read_QIcon)
from electrum.gui.qt.plugins_dialog import PluginsDialog

if TYPE_CHECKING:
    from electrum.simple_config import SimpleConfig
    from electrum.plugin import Plugins, DeviceInfo
    from electrum.gui.qt import QElectrumApplication

WIF_HELP_TEXT = (_('WIF keys are typed in 405LiteWallet, based on script type.') + '\n\n' +
                 _('A few examples') + ':\n' +
                 'p2pkh:KxZcY47uGp9a...       \t-> 1DckmggQM...\n' +
                 'p2wpkh-p2sh:KxZcY47uGp9a... \t-> 3NhNeZQXF...\n' +
                 'p2wpkh:KxZcY47uGp9a...      \t-> bc1q3fjfk...')

MSG_HW_STORAGE_ENCRYPTION = _("Set wallet file encryption.") + '\n'\
                          + _("Your wallet file does not contain secrets, mostly just metadata. ")\
                          + _("It also contains your master public key that allows watching your addresses.")

APP_NAME = getattr(constants.net, "APP_NAME", "405LiteWallet")


class QEKeystoreWizard(KeystoreWizard, QEAbstractWizard, MessageBoxMixin):
    _logger = get_logger(__name__)

    def __init__(
            self,
            *,
            config: 'SimpleConfig',
            app: 'QElectrumApplication',
            plugins: 'Plugins',
            start_viewstate: WizardViewState = None,
    ):
        assert 'wallet_type' in start_viewstate.wizard_data, 'wallet_type required'

        QEAbstractWizard.__init__(self, config, app, start_viewstate=start_viewstate)
        KeystoreWizard.__init__(self, plugins)
        self.window_title = _('Extend wallet keystore')

        self.navmap_merge({
            'keystore_type': {'gui': WCExtendKeystore},
            'enter_seed': {'gui': WCHaveSeed},
            'enter_ext': {'gui': WCEnterExt},
            'choose_hardware_device': {'gui': WCChooseHWDevice},
            'script_and_derivation': {'gui': WCScriptAndDerivation},
            'wallet_password': {'gui': WCWalletPassword},
            'wallet_password_hardware': {'gui': WCWalletPasswordHardware},
        })

    def is_single_password(self):
        return True

    def run(self):
        if self.exec() == QDialog.DialogCode.Rejected:
            return
        return self._result


class QENewWalletWizard(NewWalletWizard, QEAbstractWizard, MessageBoxMixin):
    _logger = get_logger(__name__)

    def __init__(self, config: 'SimpleConfig', app: 'QElectrumApplication', plugins: 'Plugins', daemon: Daemon, path, *, start_viewstate=None):
        NewWalletWizard.__init__(self, daemon, plugins)
        QEAbstractWizard.__init__(self, config, app, start_viewstate=start_viewstate)
        self.window_title = _('Create/Restore wallet')

        self._path = path
        self._password = None


        self.navmap_merge({
            'wallet_name': {'gui': WCWalletName, 'params': {'icon': None}},
            'hw_unlock': {'gui': WCChooseHWDevice},
            'wallet_type': {'gui': WCWalletType},
            'keystore_type': {'gui': WCKeystoreType},
            'create_seed': {'gui': WCCreateSeed, 'params': {'icon': 'electrum.png', 'icon_width': 180}},
            'create_ext': {'gui': WCEnterExt},
            'confirm_seed': {'gui': WCConfirmSeed},
            'confirm_ext': {'gui': WCConfirmExt},
            'have_seed': {'gui': WCHaveSeed, 'params': {'icon': 'electrum.png', 'icon_width': 180}},
            'have_ext': {'gui': WCEnterExt},
            'choose_hardware_device': {'gui': WCChooseHWDevice},
            'script_and_derivation': {'gui': WCScriptAndDerivation},
            'have_master_key': {'gui': WCHaveMasterKey},
            'multisig': {'gui': WCMultisig},
            'multisig_cosigner_keystore': {'gui': WCCosignerKeystore},
            'multisig_cosigner_key': {'gui': WCHaveMasterKey},
            'multisig_cosigner_seed': {'gui': WCHaveSeed},
            'multisig_cosigner_have_ext': {'gui': WCEnterExt},
            'multisig_cosigner_hardware': {'gui': WCChooseHWDevice},
            'multisig_cosigner_script_and_derivation': {'gui': WCScriptAndDerivation},
            'imported': {'gui': WCImport},
            'wallet_password': {'gui': WCWalletPassword, 'params': {'icon': 'electrum.png', 'icon_width': 180}},
            'wallet_password_hardware': {'gui': WCWalletPasswordHardware}
        })


        def _wallet_name_next(data):
            if data['wallet_needs_hw_unlock']:
                return 'hw_unlock'
            override = data.pop('next_view_override', None)
            if override:
                return override
            return 'wallet_type'

        self.navmap_merge({
            'wallet_name': {
                'next': _wallet_name_next,
                'last': lambda d: d['wallet_exists'] and not d['wallet_needs_hw_unlock']
            },
        })

        run_hook('init_wallet_wizard', self)

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, path):
        self._path = path

    def is_single_password(self):

        return False

    def on_wallet_type(self, wizard_data: dict) -> str:
        next_view = super().on_wallet_type(wizard_data)
        skip = wizard_data.pop('skip_keystore_prompt', None)
        if skip and next_view == 'keystore_type' and wizard_data.get('keystore_type'):
            return self.on_keystore_type(wizard_data)
        return next_view

    def create_storage(self, single_password: str = None):
        self._logger.info('Creating wallet from wizard data')
        data = self.get_wizard_data()

        path = os.path.join(os.path.dirname(self._daemon.config.get_wallet_path()), data['wallet_name'])

        super().create_storage(path, data)


        self._password = data['password']
        self.path = path

    def run_split(self, wallet_path, split_data) -> None:
        msg = _(
            "The wallet '{}' contains multiple accounts, which are no longer supported since 405LiteWallet 2.7.\n\n"
            "Do you want to split your wallet into multiple files?").format(wallet_path)
        if self.question(msg):
            file_list = WalletDB.split_accounts(wallet_path, split_data)
            msg = _('Your accounts have been moved to') + ':\n' + '\n'.join(file_list) + '\n\n' + _(
                'Do you want to delete the old file') + ':\n' + wallet_path
            if self.question(msg):
                os.remove(wallet_path)
                self.show_warning(_('The file was removed'))

    def is_finalized(self, wizard_data: dict) -> bool:


        if not wizard_data['wallet_exists'] or wizard_data['wallet_is_open']:
            return True

        wallet_file = wizard_data['wallet_name']

        storage = WalletStorage(wallet_file)
        assert storage.file_exists(), f"file {wallet_file!r} does not exist"
        if not storage.is_encrypted_with_user_pw() and not storage.is_encrypted_with_hw_device():
            return True

        try:
            storage.decrypt(wizard_data['password'])
        except InvalidPassword:
            if storage.is_encrypted_with_hw_device():
                self.show_message('This hardware device could not decrypt this wallet. Is it the correct one?')
            else:
                self.show_message('Invalid password')
            return False

        return True

    def waiting_dialog(self, task, msg, on_finished=None):
        dialog = QDialog()
        label = WWLabel(msg)
        vbox = QVBoxLayout()
        vbox.addSpacing(100)
        label.setMinimumWidth(300)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(label)
        vbox.addSpacing(100)
        dialog.setLayout(vbox)
        dialog.setModal(True)

        exc = None

        def task_wrap(_task):
            nonlocal exc
            try:
                _task()
            except Exception as e:
                exc = e

        t = threading.Thread(target=task_wrap, args=(task,))
        t.start()

        dialog.show()

        while True:
            QApplication.processEvents()
            t.join(1.0/60)
            if not t.is_alive():
                break

        dialog.close()

        if exc:
            raise exc

        if on_finished:
            on_finished()


class WalletWizardComponent(WizardComponent, ABC):

    wizard: QENewWalletWizard

    def __init__(self, parent: QWidget, wizard: QENewWalletWizard, **kwargs):
        WizardComponent.__init__(self, parent, wizard, **kwargs)


class WCWalletName(WalletWizardComponent, Logger):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title='')
        Logger.__init__(self)

        path = wizard._path

        if os.path.isdir(path):
            raise Exception("wallet path cannot point to a directory")

        self.wallet_exists = False
        self.wallet_is_open = False
        self.wallet_needs_hw_unlock = False
        self.password_required = False
        self.mode = 'create'
        self.remember_duration = 5
        self.storage_ready = False
        self._current_wallet_path = None
        self._next_view_override = 'create_seed'
        self._flow_override_data = {}

        root = self.layout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QFrame()
        card.setObjectName("WizardWelcomeCard")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(20)
        card_layout.setContentsMargins(40, 24, 40, 32)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(card)

        self.wizard_title = ''
        hero_pixmap = QPixmap(icon_path('electrum_presplash.png'))
        if not hero_pixmap.isNull():
            hero_label = QLabel()
            hero_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hero_label.setPixmap(hero_pixmap.scaledToWidth(180, mode=Qt.TransformationMode.SmoothTransformation))
            card_layout.addWidget(hero_label)
        header_label = QLabel(_('Welcome'))
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_label.setObjectName("WizardHeroTitle")
        card_layout.addWidget(header_label)

        self.stack = QStackedLayout()
        self.stack.setContentsMargins(0, 20, 0, 0)
        card_layout.addLayout(self.stack)


        self.create_view = QWidget()
        self.create_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        create_layout = QVBoxLayout(self.create_view)
        create_layout.setSpacing(12)
        create_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        create_layout.setContentsMargins(0, 0, 0, 0)

        self.name_e = QLineEdit()
        self.name_e.setPlaceholderText(_('Wallet name'))
        self.name_e.setMinimumWidth(520)
        self.name_e.setMaximumWidth(680)
        self.name_e.setAlignment(Qt.AlignmentFlag.AlignCenter)
        create_layout.addWidget(self.name_e, alignment=Qt.AlignmentFlag.AlignCenter)

        self.path_hint = QLabel('')
        self.path_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.path_hint.setObjectName("WizardPathHint")
        create_layout.addWidget(self.path_hint, alignment=Qt.AlignmentFlag.AlignCenter)

        self.terms_cb = QCheckBox(_('I agree to use the wallet responsibly'))
        create_layout.addWidget(self.terms_cb, alignment=Qt.AlignmentFlag.AlignCenter)

        self.create_btn = QPushButton(_('Create New Wallet'))
        self.create_btn.setProperty("class", "WizardPrimaryButton")
        self.create_btn.setMinimumWidth(320)
        self.create_btn.setMinimumHeight(48)
        self.create_btn.clicked.connect(self._handle_create_clicked)
        create_layout.addWidget(self.create_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.restore_btn = QPushButton(_('Restore From Seed'))
        self.restore_btn.setProperty("class", "WizardGhostButton")
        self.restore_btn.setMinimumWidth(320)
        self.restore_btn.setMinimumHeight(48)
        self.restore_btn.clicked.connect(self._handle_restore_clicked)
        create_layout.addWidget(self.restore_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.open_file_btn = QPushButton(_('Open wallet file'))
        self.open_file_btn.setProperty("class", "WizardGhostButton")
        self.open_file_btn.setMinimumWidth(320)
        self.open_file_btn.setMinimumHeight(40)
        create_layout.addWidget(self.open_file_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.create_message = WWLabel('')
        self.create_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        create_layout.addWidget(self.create_message, alignment=Qt.AlignmentFlag.AlignCenter)
        create_layout.addStretch(1)

        self.stack.addWidget(self.create_view)


        self.unlock_view = QWidget()
        self.unlock_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        unlock_layout = QVBoxLayout(self.unlock_view)
        unlock_layout.setSpacing(12)
        unlock_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        unlock_layout.setContentsMargins(0, 0, 0, 0)

        self.unlock_title = QLabel(_('Enter your password'))
        self.unlock_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unlock_title.setObjectName("WizardUnlockTitle")
        unlock_layout.addWidget(self.unlock_title)

        self.wallet_name_label = QLabel('')
        self.wallet_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wallet_name_label.setObjectName("WizardWalletLabel")
        unlock_layout.addWidget(self.wallet_name_label)

        self.pw_e = PasswordLineEdit('', self)
        self.pw_e.setPlaceholderText(_('Enter your password'))
        self.pw_e.setMinimumWidth(520)
        self.pw_e.setMaximumWidth(680)
        self.pw_e.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unlock_layout.addWidget(self.pw_e, alignment=Qt.AlignmentFlag.AlignCenter)

        self.remember_cb = QCheckBox(_('Remember for 5 minutes'))
        unlock_layout.addWidget(self.remember_cb, alignment=Qt.AlignmentFlag.AlignCenter)

        self.unlock_button = QPushButton(_('Unlock'))
        self.unlock_button.setProperty("class", "WizardPrimaryButton")
        self.unlock_button.setMinimumWidth(320)
        self.unlock_button.setMinimumHeight(48)
        self.unlock_button.clicked.connect(self._proceed_with_unlock)
        unlock_layout.addWidget(self.unlock_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.change_wallet_button = QPushButton(_('Choose another wallet'))
        self.change_wallet_button.setProperty("class", "WizardGhostButton")
        self.change_wallet_button.setMinimumWidth(320)
        self.change_wallet_button.setMinimumHeight(48)
        unlock_layout.addWidget(self.change_wallet_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.unlock_message = WWLabel('')
        self.unlock_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unlock_layout.addWidget(self.unlock_message)
        unlock_layout.addStretch(1)

        self.stack.addWidget(self.unlock_view)

        temp_storage = None
        datadir_wallet_folder = self.wizard.config.get_datadir_wallet_path()

        def relative_path(path):
            new_path = path
            try:
                if path and is_subpath(path, datadir_wallet_folder):
                    commonpath = os.path.commonpath([path, datadir_wallet_folder])
                    new_path = os.path.relpath(path, commonpath)
            except ValueError:
                pass
            return new_path

        def _ensure_wallet_extension(name: str) -> str:
            if not name:
                return name
            lowered = name.lower()
            if lowered.endswith(".405") or '.' in os.path.basename(name):
                return name
            return f"{name}.405"

        def on_choose():
            _path, __ = QFileDialog.getOpenFileName(self, _("Select your wallet file"), datadir_wallet_folder)
            if _path:
                self.name_e.setText(relative_path(_path))

        def on_filename(filename):
            nonlocal temp_storage
            temp_storage = None
            msg = ""
            self.wallet_exists = False
            self.wallet_is_open = False
            self.wallet_needs_hw_unlock = False
            self.password_required = False
            wallet_from_memory = None
            if filename:
                filename_with_ext = _ensure_wallet_extension(filename)
                if filename_with_ext != filename:
                    self.name_e.blockSignals(True)
                    self.name_e.setText(filename_with_ext)
                    self.name_e.blockSignals(False)
                    filename = filename_with_ext
                _path = filename if os.path.isabs(filename) else os.path.join(datadir_wallet_folder, filename)
                wallet_from_memory = self.wizard._daemon.get_wallet(_path)
                try:
                    if wallet_from_memory:
                        temp_storage = wallet_from_memory.storage
                        self.wallet_is_open = True
                    else:
                        temp_storage = WalletStorage(_path)
                    self.wallet_exists = temp_storage.file_exists()
                    self._current_wallet_path = os.path.abspath(_path)
                except (StorageReadWriteError, WalletFileException) as e:
                    msg = _('Cannot read file') + f'\n{repr(e)}'
                except Exception as e:
                    self.logger.exception('')
                    msg = _('Cannot read file') + f'\n{repr(e)}'
            else:
                self._current_wallet_path = None

            self.storage_ready = temp_storage is not None
            user_needs_to_enter_password = False
            if temp_storage:
                if not temp_storage.file_exists():
                    msg = _("This file does not exist.") + '\n'\
                          + _("Press 'Next' to create this wallet, or choose another file.")
                elif not wallet_from_memory:
                    if temp_storage.is_encrypted_with_user_pw():
                        msg = _("This file is encrypted with a password.")
                        user_needs_to_enter_password = True
                    elif temp_storage.is_encrypted_with_hw_device():
                        msg = _("This file is encrypted using a hardware device.") + '\n'\
                              + _("Press 'Next' to choose device to decrypt.")
                        self.wallet_needs_hw_unlock = True
                    else:
                        msg = _("Press 'Finish' to open this wallet.")
                else:
                    msg = _("This file is already open in memory.") + "\n"\
                          + _("Press 'Finish' to create/focus window.")
            elif not msg:
                msg = ""

            rel = relative_path(self._current_wallet_path)
            if filename and rel and os.path.isabs(rel):
                outside_text = _('Note: this wallet file is outside the default wallets folder.')
            else:
                outside_text = ''

            self._update_path_hint(self._current_wallet_path)
            self.password_required = user_needs_to_enter_password
            self._update_mode()
            self._update_message(msg, outside_text)

            if user_needs_to_enter_password and not self.name_e.hasFocus():
                self.pw_e.setFocus()

        self.open_file_btn.clicked.connect(on_choose)
        self.change_wallet_button.clicked.connect(on_choose)
        self.name_e.textChanged.connect(on_filename)
        self.terms_cb.stateChanged.connect(lambda _: self._sync_valid_state())
        self.pw_e.textChanged.connect(lambda _: self._sync_valid_state())
        try:
            default_name = relative_path(path) if path else get_new_wallet_name(datadir_wallet_folder)
        except Exception:
            default_name = "wallet.405"
        default_name = _ensure_wallet_extension(default_name)
        self.name_e.setText(default_name)
        self._select_flow('create_seed')

    def initialFocus(self) -> Optional[QWidget]:
        if self.mode == 'unlock':
            return self.pw_e if self.password_required else self.unlock_button
        return self.name_e

    def apply(self):
        wallet_folder = self.wizard.config.get_datadir_wallet_path()
        wallet_name_field = self.name_e.text()
        if wallet_name_field and '.' not in os.path.basename(wallet_name_field):
            if not wallet_name_field.lower().endswith(".405"):
                wallet_name_field = f"{wallet_name_field}.405"
        if self.wallet_exists and wallet_name_field and not os.path.isabs(wallet_name_field):
            self.wizard_data['wallet_name'] = os.path.join(wallet_folder, wallet_name_field)
        else:
            self.wizard_data['wallet_name'] = wallet_name_field
        self.wizard_data['wallet_exists'] = self.wallet_exists
        self.wizard_data['wallet_is_open'] = self.wallet_is_open
        self.wizard_data['password'] = self.pw_e.text()
        self.wizard_data['wallet_needs_hw_unlock'] = self.wallet_needs_hw_unlock
        remember = self.remember_duration if (self.mode == 'unlock' and self.password_required and self.remember_cb.isChecked()) else 0
        self.wizard_data['remember_password_minutes'] = remember
        if self._flow_override_data:
            self.wizard_data.update(self._flow_override_data)
        if self._next_view_override:
            self.wizard_data['next_view_override'] = self._next_view_override

    def _update_path_hint(self, full_path: Optional[str]):
        if not full_path:
            self.path_hint.setText('')
            return
        normalized = os.path.abspath(full_path)
        self.path_hint.setText(_('Location: {path}').format(path=normalized))

    def _update_mode(self):
        unlock_mode = self.wallet_exists or self.wallet_is_open or self.wallet_needs_hw_unlock
        if unlock_mode:
            self.mode = 'unlock'
            self.stack.setCurrentWidget(self.unlock_view)
            wallet_label = os.path.basename(self._current_wallet_path or self.name_e.text()) or _('Wallet')
            self.wallet_name_label.setText(wallet_label)
            show_password = self.password_required and not self.wallet_needs_hw_unlock
            self.pw_e.setVisible(show_password)
            if not show_password:
                self.pw_e.clear()
            self.remember_cb.setVisible(show_password)
            if not show_password:
                self.remember_cb.setChecked(False)
            self.unlock_button.setText(_('Unlock') if show_password else _('Continue'))
            self.change_wallet_button.setVisible(True)
            self._next_view_override = None
            self._flow_override_data = {}
        else:
            self.mode = 'create'
            self.stack.setCurrentWidget(self.create_view)
            self.change_wallet_button.setVisible(False)
        self._sync_valid_state()

    def _sync_valid_state(self):
        if not self.storage_ready:
            self.create_btn.setEnabled(False)
            self.unlock_button.setEnabled(False)
            self.valid = False
            return
        if self.mode == 'unlock':
            if self.wallet_needs_hw_unlock:
                can_proceed = True
            else:
                can_proceed = (not self.password_required) or bool(self.pw_e.text())
            self.unlock_button.setEnabled(can_proceed)
            self.valid = can_proceed
        else:
            name_valid = bool(self.name_e.text().strip())
            can_proceed = name_valid and self.terms_cb.isChecked()
            self.create_btn.setEnabled(can_proceed)
            self.valid = can_proceed

    def _update_message(self, message: str, outside_text: str):
        notes = [txt for txt in (outside_text, message) if txt]
        text = '\n'.join(notes)
        if self.mode == 'unlock':
            self.unlock_message.setText(text)
            self.create_message.setText('')
        else:
            self.create_message.setText(text)
            self.unlock_message.setText('')

    def _handle_create_clicked(self):
        self._select_flow('create_seed')
        self._proceed_with_create()

    def _handle_restore_clicked(self):
        self._select_flow('have_seed')
        self._proceed_with_create()

    def _select_flow(self, flow_key: str):
        self._next_view_override = flow_key
        if flow_key == 'create_seed':
            self._flow_override_data = {
                'wallet_type': 'standard',
                'keystore_type': 'createseed',
                'skip_keystore_prompt': True,
            }
        elif flow_key == 'have_seed':
            self._flow_override_data = {
                'wallet_type': 'standard',
                'keystore_type': 'haveseed',
                'skip_keystore_prompt': True,
            }
        else:
            self._flow_override_data = {}

    def _proceed_with_create(self):
        self._sync_valid_state()
        if not self.valid:
            return
        self.wizard.requestNext.emit()

    def _proceed_with_unlock(self):
        self._sync_valid_state()
        if not self.valid:
            return
        self.wizard.requestNext.emit()


class WCWalletType(WalletWizardComponent):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Create or restore a wallet'))
        message = _('Choose how you would like to set up your {app} wallet.').format(app=APP_NAME)
        wallet_kinds = [
            ChoiceItem(key='create_seed', label=_('Create new seed')),
            ChoiceItem(key='import_seed', label=_('Import seed')),
        ]

        self.choice_w = ChoiceWidget(message=message, choices=wallet_kinds, default_key='create_seed')
        self.layout().addWidget(self.choice_w)
        self.layout().addStretch(1)
        self._valid = True

    def apply(self):
        selection = self.choice_w.selected_key
        if selection == 'import_privkey':
            self.wizard_data['wallet_type'] = 'imported'
            self.wizard_data.pop('keystore_type', None)
            self.wizard_data.pop('skip_keystore_prompt', None)
        else:
            self.wizard_data['wallet_type'] = 'standard'
            self.wizard_data['keystore_type'] = 'createseed' if selection == 'create_seed' else 'haveseed'
            self.wizard_data['skip_keystore_prompt'] = True


class WCKeystoreType(WalletWizardComponent):

    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Keystore'))
        message = _('Do you want to create a new seed, or to restore a wallet using an existing seed?')
        choices = [
            ChoiceItem(key='createseed', label=_('Create a new seed')),
            ChoiceItem(key='haveseed', label=_('I already have a seed')),
        ]
        self.choice_w = ChoiceWidget(message=message, choices=choices)
        self.layout().addWidget(self.choice_w)
        self.layout().addStretch(1)
        self._valid = True

    def apply(self):
        self.wizard_data['keystore_type'] = self.choice_w.selected_key


class WCExtendKeystore(WalletWizardComponent):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Keystore'))
        message = _('What type of signing method do you want to add?')
        choices = [
            ChoiceItem(key='haveseed', label=_('Enter seed')),
        ]
        self.choice_w = ChoiceWidget(message=message, choices=choices)
        self.layout().addWidget(self.choice_w)
        self.layout().addStretch(1)
        self._valid = True

    def apply(self):
        self.wizard_data['keystore_type'] = self.choice_w.selected_key


class WCCreateSeed(WalletWizardComponent):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Wallet Seed'))
        self._busy = True
        default_seed_type = getattr(constants.net, 'DEFAULT_SEED_TYPE', 'segwit')
        if default_seed_type == 'segwit' and self.wizard.config.WIZARD_DONT_CREATE_SEGWIT:
            default_seed_type = 'standard'
        self.seed_type = default_seed_type
        self.seed_widget = None
        self.seed = None

    def on_ready(self):
        if self.wizard_data['wallet_type'] == '2fa':
            self.seed_type = '2fa_segwit'
        QTimer.singleShot(1, self.create_seed)

    def apply(self):
        if self.seed_widget:
            self.wizard_data['seed'] = self.seed
            self.wizard_data['seed_type'] = self.seed_type
            self.wizard_data['seed_extend'] = self.seed_widget.is_ext
            self.wizard_data['seed_variant'] = 'electrum'

    def create_seed(self):
        self.busy = True
        self.seed = mnemonic.Mnemonic('en').make_seed(seed_type=self.seed_type)

        self.seed_widget = SeedWidget(
            title=_('Your wallet generation seed is:'),
            seed=self.seed,
            options=['ext', 'electrum'],
            msg=True,
            parent=self,
            config=self.wizard.config,
            show_seed_controls=False,
        )
        self.layout().addWidget(self.seed_widget)
        self.layout().addStretch(1)
        self.busy = False
        self.valid = True


class WCConfirmSeed(WalletWizardComponent):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Confirm Seed'))
        message = ' '.join([
            _('Your seed is important!'),
            _('If you lose your seed, your money will be permanently lost.'),
            _('To make sure that you have properly saved your seed, please retype it here.')
        ])

        self.layout().addWidget(WWLabel(message))

        self.seed_widget = SeedWidget(
            is_seed=lambda x: x == self.wizard_data['seed'],
            config=self.wizard.config,
        )

        def seed_valid_changed(valid):
            self.valid = valid

        self.seed_widget.validChanged.connect(seed_valid_changed)
        self.layout().addWidget(self.seed_widget)

        wizard.app.clipboard().clear()

    def apply(self):
        pass


class WCEnterExt(WalletWizardComponent, Logger):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Seed Extension'))
        Logger.__init__(self)

        message = '\n'.join([
            _('You may extend your seed with custom words.'),
            _('Your seed extension must be saved together with your seed.'),
        ])
        warning = '\n'.join([
            _('Note that this is NOT your encryption password.'),
            _('If you do not know what this is, leave this field empty.'),
        ])

        self.ext_edit = SeedExtensionEdit(self, message=message, warning=warning)
        self.ext_edit.textEdited.connect(self.on_text_edited)
        self.layout().addWidget(self.ext_edit)
        self.layout().addStretch(1)
        self.warn_label = IconLabel(reverse=True, hide_if_empty=True)
        self.warn_label.setIcon(read_QIcon('warning.png'))
        self.layout().addWidget(self.warn_label)

    def on_ready(self):
        self.validate()

    def on_text_edited(self, text):

        self.ext_edit.warn_issue4566 = self.wizard_data['keystore_type'] == 'haveseed' and\
                                       self.wizard_data['seed_type'] == 'bip39'
        self.validate()

    def validate(self):
        self.apply()

        musig_valid, errortext = self.wizard.check_multisig_constraints(self.wizard_data)
        self.valid = musig_valid
        self.warn_label.setText(errortext)

    def apply(self):
        cosigner_data = self.wizard.current_cosigner(self.wizard_data)
        cosigner_data['seed_extra_words'] = self.ext_edit.text()


class WCConfirmExt(WalletWizardComponent):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Confirm Seed Extension'))
        message = '\n'.join([
            _('Your seed extension must be saved together with your seed.'),
            _('Please type it here.'),
        ])
        self.ext_edit = SeedExtensionEdit(self, message=message)
        self.ext_edit.textEdited.connect(self.on_text_edited)
        self.layout().addWidget(self.ext_edit)
        self.layout().addStretch(1)

    def on_ready(self):
        self.validate()

    def on_text_edited(self, *args):
        self.validate()

    def validate(self):
        self.valid = self.ext_edit.text() == self.wizard_data['seed_extra_words']

    def apply(self):
        pass


class WCHaveSeed(WalletWizardComponent, Logger):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Enter Seed'))
        Logger.__init__(self)

        self.layout().addWidget(WWLabel(_('Please enter your seed phrase in order to restore your wallet.')))
        self.warn_label = IconLabel(reverse=True, hide_if_empty=True)
        self.warn_label.setIcon(read_QIcon('warning.png'))

        self.seed_widget = None
        self.can_passphrase = True

    def on_ready(self):
        options = ['ext', 'electrum', 'bip39', 'slip39']
        if self.wizard_data['wallet_type'] == '2fa':
            options = ['ext', 'electrum']
        else:
            if self.params and 'seed_options' in self.params:
                options = self.params['seed_options']

        self.seed_widget = SeedWidget(
            is_seed=self.is_seed,
            options=options,
            config=self.wizard.config,
            show_seed_controls=False,
        )

        def seed_valid_changed(valid):
            if not valid:
                self.valid = valid
            else:
                self.validate()

        self.seed_widget.validChanged.connect(seed_valid_changed)
        self.seed_widget.updated.connect(self.validate)

        self.layout().addWidget(self.seed_widget)
        self.layout().addStretch(1)

        self.layout().addWidget(self.warn_label)

    def is_seed(self, x):

        t = mnemonic.calc_seed_type(x)
        if self.wizard_data['wallet_type'] == 'standard':
            return mnemonic.is_seed(x) and not mnemonic.is_any_2fa_seed_type(t)
        elif self.wizard_data['wallet_type'] == '2fa':
            return mnemonic.is_any_2fa_seed_type(t)
        else:

            return t in ['standard', 'segwit']

    def validate(self):

        seed = self.seed_widget.get_seed()
        seed_variant = self.seed_widget.seed_type
        wallet_type = self.wizard_data['wallet_type']
        seed_valid, seed_type, validation_message, self.can_passphrase = self.wizard.validate_seed(seed, seed_variant, wallet_type)

        is_cosigner = self.wizard_data['wallet_type'] == 'multisig' and 'multisig_current_cosigner' in self.wizard_data

        if not is_cosigner or not seed_valid:
            self.warn_label.setText(validation_message)
            self.valid = seed_valid
            return

        self.apply()
        musig_valid, errortext = self.wizard.check_multisig_constraints(self.wizard_data)
        if not musig_valid:
            seed_valid = False

        self.warn_label.setText(errortext)
        self.valid = seed_valid

    def apply(self):
        cosigner_data = self.wizard.current_cosigner(self.wizard_data)

        cosigner_data['seed'] = self.seed_widget.get_seed()
        cosigner_data['seed_variant'] = self.seed_widget.seed_type
        if self.seed_widget.seed_type == 'electrum':
            cosigner_data['seed_type'] = mnemonic.calc_seed_type(self.seed_widget.get_seed())
        else:
            cosigner_data['seed_type'] = self.seed_widget.seed_type
        cosigner_data['seed_extend'] = self.seed_widget.is_ext if self.can_passphrase else False


class WCScriptAndDerivation(WalletWizardComponent, Logger):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Script type and Derivation path'))
        Logger.__init__(self)

        self.choice_w = None
        self.derivation_path_edit = None

        self.warn_label = IconLabel(reverse=True, hide_if_empty=True)
        self.warn_label.setIcon(read_QIcon('warning.png'))

    def on_ready(self):
        message1 = _('Choose the type of addresses in your wallet.')
        message2 = ' '.join([
            _('You can override the suggested derivation path.'),
            _('If you are not sure what this is, leave this field unchanged.')
        ])
        hide_choices = False

        if self.wizard_data['wallet_type'] == 'multisig':
            choices = [

                ChoiceItem(key='standard', label='legacy multisig (p2sh)',
                           extra_data=normalize_bip32_derivation("m/45'/0")),
                ChoiceItem(key='p2wsh-p2sh', label='p2sh-segwit multisig (p2wsh-p2sh)',
                           extra_data=purpose48_derivation(0, xtype='p2wsh-p2sh')),
                ChoiceItem(key='p2wsh', label='native segwit multisig (p2wsh)',
                           extra_data=purpose48_derivation(0, xtype='p2wsh')),
            ]
            if 'multisig_current_cosigner' in self.wizard_data:

                ks = self.wizard.keystore_from_data(self.wizard_data['wallet_type'], self.wizard_data)
                default_choice = xpub_type(ks.get_master_public_key())
                hide_choices = True
            else:
                default_choice = 'p2wsh'
        else:
            default_choice = getattr(constants.net, 'DEFAULT_SCRIPT_TYPE', 'p2wpkh')
            choices = [

                ChoiceItem(key='standard', label='legacy (p2pkh)',
                           extra_data=bip44_derivation(0, bip43_purpose=44)),
                ChoiceItem(key='p2wpkh-p2sh', label='p2sh-segwit (p2wpkh-p2sh)',
                           extra_data=bip44_derivation(0, bip43_purpose=49)),
                ChoiceItem(key='p2wpkh', label='native segwit (p2wpkh)',
                           extra_data=bip44_derivation(0, bip43_purpose=84)),
            ]

        if self.wizard_data['wallet_type'] == 'standard' and not self.wizard_data['keystore_type'] == 'hardware':
            button = QPushButton(_("Detect Existing Accounts"))

            passphrase = self.wizard_data['seed_extra_words'] if self.wizard_data['seed_extend'] else ''
            if self.wizard_data['seed_variant'] == 'bip39':
                root_seed = bip39_to_seed(self.wizard_data['seed'], passphrase=passphrase)
            elif self.wizard_data['seed_variant'] == 'slip39':
                root_seed = self.wizard_data['seed'].decrypt(passphrase)

            def get_account_xpub(account_path):
                root_node = BIP32Node.from_rootseed(root_seed, xtype="standard")
                account_node = root_node.subkey_at_private_derivation(account_path)
                account_xpub = account_node.to_xpub()
                return account_xpub

            def on_account_select(account):
                script_type = account["script_type"]
                if script_type == "p2pkh":
                    script_type = "standard"
                self.choice_w.select(script_type)
                self.derivation_path_edit.setText(account["derivation_path"])

            button.clicked.connect(lambda: Bip39RecoveryDialog(self, get_account_xpub, on_account_select))
            self.layout().addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
            self.layout().addWidget(QLabel(_("Or")))

        def on_choice_click(index):
            self.derivation_path_edit.setText(self.choice_w.selected_item.extra_data)
        self.choice_w = ChoiceWidget(message=message1, choices=choices, default_key=default_choice)
        self.choice_w.itemSelected.connect(on_choice_click)

        if not hide_choices:
            self.layout().addWidget(self.choice_w)

        self.layout().addWidget(WWLabel(message2))

        self.derivation_path_edit = QLineEdit()
        self.derivation_path_edit.textChanged.connect(self.validate)
        self.layout().addWidget(self.derivation_path_edit)

        on_choice_click(self.choice_w.selected_index)

        self.layout().addStretch(1)
        self.layout().addWidget(self.warn_label)

    def validate(self):
        self.apply()

        cosigner_data = self.wizard.current_cosigner(self.wizard_data)
        valid = is_bip32_derivation(cosigner_data['derivation_path'])

        if valid:
            valid, errortext = self.wizard.check_multisig_constraints(self.wizard_data)
            if not valid:
                self.logger.error(errortext)
            self.warn_label.setText(errortext)
        else:
            self.warn_label.setText(_('Invalid derivation path'))

        self.valid = valid

    def apply(self):
        cosigner_data = self.wizard.current_cosigner(self.wizard_data)
        cosigner_data['script_type'] = self.choice_w.selected_key
        cosigner_data['derivation_path'] = str(self.derivation_path_edit.text())


class WCCosignerKeystore(WalletWizardComponent):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard)

        message = _('Add a cosigner to your multi-sig wallet')
        choices = [
            ChoiceItem(key='masterkey', label=_('Enter cosigner key')),
            ChoiceItem(key='haveseed', label=_('Enter cosigner seed')),
            ChoiceItem(key='hardware', label=_('Cosign with hardware device')),
        ]

        self.choice_w = ChoiceWidget(message=message, choices=choices)
        self.layout().addWidget(self.choice_w)

        self.cosigner = 0
        self.participants = 0

        self._valid = True

    def on_ready(self):
        self.participants = self.wizard_data['multisig_participants']


        self.cosigner = 2 + len(self.wizard_data['multisig_cosigner_data'])

        self.wizard_data['multisig_current_cosigner'] = self.cosigner
        self.title = _("Add Cosigner {}").format(self.wizard_data['multisig_current_cosigner'])


        self.layout().addSpacing(20)
        self.layout().addWidget(WWLabel(_('Below is your master public key. Please share it with your cosigners')))
        seed_widget = SeedWidget(
            self.wizard_data['multisig_master_pubkey'],
            icon=False,
            for_seed_words=False,
            config=self.wizard.config,
        )
        self.layout().addWidget(seed_widget)
        self.layout().addStretch(1)

    def apply(self):
        self.wizard_data['cosigner_keystore_type'] = self.choice_w.selected_key
        self.wizard_data['multisig_current_cosigner'] = self.cosigner
        self.wizard_data['multisig_cosigner_data'][str(self.cosigner)] = {
            'keystore_type': self.choice_w.selected_key
        }


class WCHaveMasterKey(WalletWizardComponent):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Create keystore from a master key'))

        self.keys_widget = None

        self.message_create = ' '.join([
            _("To create a watching-only wallet, please enter your master public key (xpub/ypub/zpub)."),
            _("To create a spending wallet, please enter a master private key (xprv/yprv/zprv).")
        ])
        self.message_multisig = ' '.join([
            _('Please enter your master private key (xprv).'),
            _('You can also enter a public key (xpub) here, but be aware you will then create a watch-only wallet if all cosigners are added using public keys'),
        ])
        self.message_cosign = ' '.join([
            _('Please enter the master public key (xpub) of your cosigner.'),
            _('Enter their master private key (xprv) if you want to be able to sign for them.')
        ])

        self.header_layout = QHBoxLayout()
        self.label = WWLabel()
        self.label.setMinimumWidth(400)
        self.header_layout.addWidget(self.label)

        self.warn_label = IconLabel(reverse=True, hide_if_empty=True)
        self.warn_label.setIcon(read_QIcon('warning.png'))

    def on_ready(self):
        if self.wizard_data['wallet_type'] == 'standard':
            self.label.setText(self.message_create)

            def is_valid(x) -> bool:
                self.apply()
                key_valid, message = self.wizard.validate_master_key(x, self.wizard_data['wallet_type'])
                self.warn_label.setText(message)
                return key_valid
        elif self.wizard_data['wallet_type'] == 'multisig':
            if 'multisig_current_cosigner' in self.wizard_data:
                self.title = _("Add Cosigner {}").format(self.wizard_data['multisig_current_cosigner'])
                self.label.setText(self.message_cosign)
            else:
                self.label.setText(self.message_multisig)

            def is_valid(x) -> bool:
                self.apply()
                key_valid, message = self.wizard.validate_master_key(x, self.wizard_data['wallet_type'])
                if not key_valid:
                    self.warn_label.setText(message)
                    return False
                musig_valid, errortext = self.wizard.check_multisig_constraints(self.wizard_data)
                self.warn_label.setText(errortext)
                if not musig_valid:
                    return False
                return True
        else:
            raise Exception(f"unexpected wallet type: {self.wizard_data['wallet_type']}")

        self.keys_widget = KeysWidget(parent=self, header_layout=self.header_layout, is_valid=is_valid,
                                      allow_multi=False, config=self.wizard.config)

        def key_valid_changed(valid):
            self.valid = valid

        self.keys_widget.validChanged.connect(key_valid_changed)

        self.layout().addWidget(self.keys_widget)
        self.layout().addStretch()
        self.layout().addWidget(self.warn_label)

    def apply(self):
        text = self.keys_widget.get_text()
        cosigner_data = self.wizard.current_cosigner(self.wizard_data)
        cosigner_data['master_key'] = text


class WCMultisig(WalletWizardComponent):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Multi-Signature Wallet'))

        def on_m(m):
            m_label.setText(_('Require {0} signatures').format(m))
            cw.set_m(m)
            backup_warning_label.setVisible(cw.m != cw.n)

        def on_n(n):
            n_label.setText(_('From {0} cosigners').format(n))
            cw.set_n(n)
            m_edit.setMaximum(n)
            backup_warning_label.setVisible(cw.m != cw.n)

        backup_warning_label = WWLabel(_('Warning: to be able to restore a multisig wallet, '
                                         'you should include the master public key for each cosigner '
                                         'in all of your backups.'))

        cw = CosignWidget(2, 2)
        m_label = QLabel()
        n_label = QLabel()

        m_edit = QSlider(Qt.Orientation.Horizontal, self)
        m_edit.setMinimum(1)
        m_edit.setMaximum(2)
        m_edit.setValue(2)
        m_edit.valueChanged.connect(on_m)
        on_m(m_edit.value())

        n_edit = QSlider(Qt.Orientation.Horizontal, self)
        n_edit.setMinimum(2)
        n_edit.setMaximum(15)
        n_edit.setValue(2)
        n_edit.valueChanged.connect(on_n)
        on_n(n_edit.value())

        grid = QGridLayout()
        grid.addWidget(n_label, 0, 0)
        grid.addWidget(n_edit, 0, 1)
        grid.addWidget(m_label, 1, 0)
        grid.addWidget(m_edit, 1, 1)

        self.layout().addWidget(cw)
        self.layout().addWidget(WWLabel(_('Choose the number of signatures needed to unlock funds in your wallet:')))
        self.layout().addLayout(grid)
        self.layout().addSpacing(2 * char_width_in_lineedit())
        self.layout().addWidget(backup_warning_label)
        self.layout().addStretch(1)

        self.n_edit = n_edit
        self.m_edit = m_edit

        self._valid = True

    def apply(self):
        self.wizard_data['multisig_participants'] = int(self.n_edit.value())
        self.wizard_data['multisig_signatures'] = int(self.m_edit.value())
        self.wizard_data['multisig_cosigner_data'] = {}


class WCImport(WalletWizardComponent):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Import Bitcoin Addresses or Private Keys'))
        message = _(
            'Enter a list of Bitcoin addresses (this will create a watching-only wallet), or a list of private keys.')
        header_layout = QHBoxLayout()
        label = WWLabel(message)
        label.setMinimumWidth(400)
        header_layout.addWidget(label)
        header_layout.addWidget(InfoButton(WIF_HELP_TEXT), alignment=Qt.AlignmentFlag.AlignRight)

        def is_valid(x) -> bool:
            return keystore.is_address_list(x) or keystore.is_private_key_list(x, raise_on_error=True)

        self.keys_widget = KeysWidget(header_layout=header_layout, is_valid=is_valid,
                                      allow_multi=True, config=self.wizard.config)

        def key_valid_changed(valid):
            self.valid = valid

        self.keys_widget.validChanged.connect(key_valid_changed)
        self.layout().addWidget(self.keys_widget)

    def apply(self):
        text = self.keys_widget.get_text()
        if keystore.is_address_list(text):
            self.wizard_data['address_list'] = text
        elif keystore.is_private_key_list(text):
            self.wizard_data['private_key_list'] = text


class WCWalletPassword(WalletWizardComponent):

    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Wallet Password'))


        class Hack:
            def setEnabled(self2, b):
                self.valid = b
        self.next_button = Hack()
        self.pw_layout = PasswordLayout(
            msg=MSG_ENTER_PASSWORD,
            kind=PW_NEW,
            OK_button=self.next_button,
        )
        self.layout().addLayout(self.pw_layout.layout())
        self.layout().addStretch(1)

    def initialFocus(self) -> Optional[QWidget]:
        return self.pw_layout.new_pw

    def apply(self):
        self.wizard_data['password'] = self.pw_layout.new_password()
        self.wizard_data['encrypt'] = True


class SeedExtensionEdit(QWidget):
    def __init__(self, parent, *, message: str = None, warning: str = None, warn_issue4566: bool = False):
        super().__init__(parent)

        self.warn_issue4566 = warn_issue4566

        layout = QVBoxLayout()
        self.setLayout(layout)

        if message:
            layout.addWidget(WWLabel(message))

        self.line = QLineEdit()
        layout.addWidget(self.line)

        def f(text):
            if self.warn_issue4566:
                text_whitespace_normalised = ' '.join(text.split())
                warn_issue4566_label.setVisible(text != text_whitespace_normalised)
        self.line.textEdited.connect(f)

        if warning:
            layout.addWidget(WWLabel(warning))

        warn_issue4566_label = WWLabel(MSG_PASSPHRASE_WARN_ISSUE4566)
        warn_issue4566_label.setVisible(False)
        layout.addWidget(warn_issue4566_label)


        self.textEdited = self.line.textEdited
        self.text = self.line.text


class CosignWidget(QWidget):
    def __init__(self, m, n):
        QWidget.__init__(self)
        self.size = max(120, 9 * font_height())
        self.R = QRect(0, 0, self.size, self.size)
        self.setGeometry(self.R)
        self.setMinimumHeight(self.size)
        self.setMaximumHeight(self.size)
        self.m = m
        self.n = n

    def set_n(self, n):
        self.n = n
        self.update()

    def set_m(self, m):
        self.m = m
        self.update()

    def paintEvent(self, event):
        bgcolor = self.palette().color(QPalette.ColorRole.Window)
        pen = QPen(bgcolor, 7, Qt.PenStyle.SolidLine)
        qp = QPainter()
        qp.begin(self)
        qp.setPen(pen)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        qp.setBrush(Qt.GlobalColor.gray)
        for i in range(self.n):
            alpha = int(16 * 360 * i/self.n)
            alpha2 = int(16 * 360 * 1/self.n)
            qp.setBrush(Qt.GlobalColor.green if i < self.m else Qt.GlobalColor.gray)
            qp.drawPie(self.R, alpha, alpha2)
        qp.end()


class WCChooseHWDevice(WalletWizardComponent, Logger):
    scanFailed = pyqtSignal([str, str], arguments=['code', 'message'])
    scanComplete = pyqtSignal()

    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Choose Hardware Device'))
        Logger.__init__(self)
        self.scanFailed.connect(self.on_scan_failed)
        self.scanComplete.connect(self.on_scan_complete)
        self.plugins = wizard.plugins
        self.config = wizard.config

        self.error_l = WWLabel()
        self.error_l.setVisible(False)

        self.device_list = QWidget()
        self.device_list_layout = QVBoxLayout()
        self.device_list.setLayout(self.device_list_layout)
        self.choice_w = None

        self.rescan_button = QPushButton(_('Rescan devices'))
        self.rescan_button.clicked.connect(self.on_rescan)

        self.add_plugin_button = QPushButton(_('Add plugin'))
        self.add_plugin_button.clicked.connect(self.on_add_plugin)

        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(self.rescan_button)
        hbox.addWidget(self.add_plugin_button)
        hbox.addStretch(1)

        self.layout().addWidget(self.error_l)
        self.layout().addWidget(self.device_list)
        self.layout().addStretch(1)
        self.layout().addLayout(hbox)
        self.layout().addStretch(1)

    def on_ready(self):
        self.scan_devices()

    def on_rescan(self):
        self.scan_devices()

    def on_add_plugin(self):
        d = PluginsDialog(self.config, self.plugins)
        d.exec()
        self.scan_devices()

    def on_scan_failed(self, code, message):
        self.error_l.setText(message)
        self.error_l.setVisible(True)
        self.device_list.setVisible(False)

        self.valid = False

    def on_scan_complete(self):
        self.error_l.setVisible(False)
        self.device_list.setVisible(True)

        choices = []
        for name, info in self.devices:
            state = _("initialized") if info.initialized else _("wiped")
            label = info.label or _("An unnamed {}").format(name)
            try:
                transport_str = info.device.transport_ui_string[:20]
            except Exception:
                transport_str = 'unknown transport'
            descr = f"{label} [{info.model_name or name}, {state}, {transport_str}]"
            choices.append(ChoiceItem(key=(name, info), label=descr))
        msg = _('Select a device') + ':'

        if self.choice_w:
            self.device_list_layout.removeWidget(self.choice_w)

        self.choice_w = ChoiceWidget(message=msg, choices=choices)
        self.device_list_layout.addWidget(self.choice_w)

        self.valid = True

        if self.valid:
            self.wizard.next_button.setFocus()
        else:
            self.rescan_button.setFocus()

    def scan_devices(self):
        self.valid = False
        self.busy_msg = _('Scanning devices...')
        self.busy = True

        def scan_task():

            supported_plugins = self.plugins.get_hardware_support()
            devices = []
            devmgr = self.plugins.device_manager
            debug_msg = ''

            def failed_getting_device_infos(name, e):
                nonlocal debug_msg
                err_str_oneline = ' // '.join(str(e).splitlines())
                self.logger.warning(f'error getting device infos for {name}: {err_str_oneline}')
                _indented_error_msg = '    '.join([''] + str(e).splitlines(keepends=True))
                debug_msg += f'  {name}: (error getting device infos)\n{_indented_error_msg}\n'


            try:


                scanned_devices = devmgr.scan_devices()
            except BaseException as e:
                self.logger.info('error scanning devices: {}'.format(repr(e)))
                debug_msg = '  {}:\n    {}'.format(_('Error scanning devices'), e)
            else:
                for splugin in supported_plugins:
                    name, plugin = splugin.name, splugin.plugin

                    if not plugin:
                        e = splugin.exception
                        indented_error_msg = '    '.join([''] + str(e).splitlines(keepends=True))
                        debug_msg += f'  {name}: (error during plugin init)\n'
                        debug_msg += '    {}\n'.format(_('You might have an incompatible library.'))
                        debug_msg += f'{indented_error_msg}\n'
                        continue

                    try:

                        device_infos = devmgr.list_pairable_device_infos(
                            handler=None, plugin=plugin, devices=scanned_devices, include_failing_clients=True)
                    except HardwarePluginLibraryUnavailable as e:
                        failed_getting_device_infos(name, e)
                        continue
                    except BaseException as e:
                        self.logger.exception('')
                        failed_getting_device_infos(name, e)
                        continue
                    device_infos_failing = list(filter(lambda di: di.exception is not None, device_infos))
                    for di in device_infos_failing:
                        failed_getting_device_infos(name, di.exception)
                    device_infos_working = list(filter(lambda di: di.exception is None, device_infos))
                    devices += list(map(lambda x: (name, x), device_infos_working))
            if not debug_msg:
                debug_msg = '  {}'.format(_('No exceptions encountered.'))
            if not devices:
                msg = (_('No hardware device detected.') + '\n\n')
                if sys.platform == 'win32':
                    msg += _('If your device is not detected on Windows, go to "Settings", "Devices", "Connected devices", '
                             'and do "Remove device". Then, plug your device again.') + '\n'
                    msg += _('While this is less than ideal, it might help if you run 405LiteWallet as Administrator.') + '\n'
                else:
                    msg += _('On Linux, you might have to add a new permission to your udev rules.') + '\n'
                msg += '\n\n'
                msg += _('Debug message') + '\n' + debug_msg

                self.scanFailed.emit('no_devices', msg)
                self.busy = False
                return


            self.devices = devices
            self.scanComplete.emit()
            self.busy = False

        t = threading.Thread(target=scan_task, daemon=True)
        t.start()

    def apply(self):
        if self.choice_w:
            cosigner_data = self.wizard.current_cosigner(self.wizard_data)
            cosigner_data['hardware_device'] = self.choice_w.selected_key


class WCWalletPasswordHardware(WalletWizardComponent):

    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Encrypt using hardware'))
        self.plugins = wizard.plugins


        class Hack:
            def setEnabled(self2, b):
                self.valid = b
        self.next_button = Hack()
        self.playout = PasswordLayoutForHW(
            MSG_HW_STORAGE_ENCRYPTION,
            kind=PW_NEW,
            OK_button=self.next_button,
        )
        self.layout().addLayout(self.playout.layout())
        self.layout().addStretch(1)

        self._valid = True

    def apply(self):
        self.wizard_data['encrypt'] = True
        if self.playout.should_encrypt_storage_with_xpub():
            self.wizard_data['xpub_encrypt'] = True
            _name, _info = self.wizard_data['hardware_device']
            device_id = _info.device.id_
            client = self.plugins.device_manager.client_by_id(device_id, scan_now=False)



            self.wizard_data['password'] = client.get_password_for_storage_encryption()
        else:
            self.wizard_data['xpub_encrypt'] = False
            self.wizard_data['password'] = self.playout.new_password()


class WCHWUnlock(WalletWizardComponent, Logger):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Unlocking hardware'))
        Logger.__init__(self)
        self.plugins = wizard.plugins
        self.plugin = None
        self._busy = True
        self.password = None

        ok_icon = QLabel()
        ok_icon.setPixmap(QPixmap(icon_path('confirmed.png')).scaledToWidth(48, mode=Qt.TransformationMode.SmoothTransformation))
        ok_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ok_l = WWLabel(_('Hardware successfully unlocked'))
        self.ok_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout().addStretch(1)
        self.layout().addWidget(ok_icon)
        self.layout().addWidget(self.ok_l)
        self.layout().addStretch(1)

    def on_ready(self):
        _name, _info = self.wizard_data['hardware_device']
        self.plugin = self.plugins.get_plugin(_info.plugin_name)
        self.title = _('Unlocking {} ({})').format(_info.model_name, _info.label)

        device_id = _info.device.id_
        client = self.plugins.device_manager.client_by_id(device_id, scan_now=False)
        if client is None:
            self.error = _("Client for hardware device was unpaired.")
            self.busy = False
            self.validate()
            return
        client.handler = self.plugin.create_handler(self.wizard)

        def unlock_task(client):
            try:
                self.password = client.get_password_for_storage_encryption()
            except UserCancelled as e:
                self.error = repr(e)
            except Exception as e:
                self.error = repr(e)
                self.logger.exception(repr(e))
            self.busy = False
            self.validate()

        t = threading.Thread(target=unlock_task, args=(client,), daemon=True)
        t.start()

    def validate(self):
        self.valid = False
        if self.password and not self.error:
            if not self.check_hw_decrypt():
                self.error = _('This hardware device could not decrypt this wallet. Is it the correct one?')
            else:
                self.apply()
                self.valid = True

        if self.valid:
            self.wizard.requestNext.emit()

    def check_hw_decrypt(self):
        wallet_file = self.wizard_data['wallet_name']

        storage = WalletStorage(wallet_file)
        if not storage.is_encrypted_with_hw_device():
            return True

        try:
            storage.decrypt(self.password)
        except InvalidPassword:
            return False
        return True

    def apply(self):
        if self.valid:
            self.wizard_data['password'] = self.password


class WCHWXPub(WalletWizardComponent, Logger):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Retrieving extended public key from hardware'))
        Logger.__init__(self)
        self.plugins = wizard.plugins
        self.plugin = None
        self._busy = True

        self.xpub = None
        self.root_fingerprint = None
        self.label = None
        self.soft_device_id = None

        ok_icon = QLabel()
        ok_icon.setPixmap(QPixmap(icon_path('confirmed.png')).scaledToWidth(48, mode=Qt.TransformationMode.SmoothTransformation))
        ok_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ok_l = WWLabel(_('Hardware keystore added to wallet'))
        self.ok_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout().addStretch(1)
        self.layout().addWidget(ok_icon)
        self.layout().addWidget(self.ok_l)
        self.layout().addStretch(1)

    def on_ready(self):
        cosigner_data = self.wizard.current_cosigner(self.wizard_data)
        _name, _info = cosigner_data['hardware_device']
        self.plugin = self.plugins.get_plugin(_info.plugin_name)
        self.title = _('Retrieving extended public key from {} ({})').format(_info.model_name, _info.label)

        device_id = _info.device.id_
        client = self.plugins.device_manager.client_by_id(device_id, scan_now=False)
        if client is None:
            self.error = _("Client for hardware device was unpaired.")
            self.busy = False
            self.validate()
            return
        if not client.handler:
            client.handler = self.plugin.create_handler(self.wizard)

        xtype = cosigner_data['script_type']
        derivation = cosigner_data['derivation_path']

        def get_xpub_task(_client, _derivation, _xtype):
            try:
                self.xpub = self.get_xpub_from_client(_client, _derivation, _xtype)
                self.root_fingerprint = _client.request_root_fingerprint_from_device()
                self.label = _client.label()
                self.soft_device_id = _client.get_soft_device_id()
            except UserFacingException as e:
                self.error = str(e)
                self.logger.error(repr(e))
            except Exception as e:
                self.error = repr(e)
                self.logger.exception(repr(e))
            if self.xpub:
                self.logger.debug(f'Done retrieve xpub: {self.xpub[:10]}...{self.xpub[-5:]}')
            self.busy = False
            self.validate()

        t = threading.Thread(target=get_xpub_task, args=(client, derivation, xtype), daemon=True)
        t.start()

    def get_xpub_from_client(self, client, derivation, xtype):
        cosigner_data = self.wizard.current_cosigner(self.wizard_data)
        _name, _info = cosigner_data['hardware_device']
        if xtype not in self.plugin.SUPPORTED_XTYPES:
            raise ScriptTypeNotSupported(_('This type of script is not supported with {}').format(_info.model_name))
        return client.get_xpub(derivation, xtype)

    def validate(self):
        if self.xpub and not self.error:
            self.apply()
            valid, error = self.wizard.check_multisig_constraints(self.wizard_data)
            if not valid:
                self.error = '\n'.join([
                    _('Could not add hardware keystore to wallet'),
                    error
                ])
            self.valid = valid
        else:
            self.valid = False

        if self.valid:
            self.wizard.requestNext.emit()

    def apply(self):
        cosigner_data = self.wizard.current_cosigner(self.wizard_data)
        _name, _info = cosigner_data['hardware_device']
        cosigner_data['hw_type'] = _info.plugin_name
        cosigner_data['master_key'] = self.xpub
        cosigner_data['root_fingerprint'] = self.root_fingerprint
        cosigner_data['label'] = self.label
        cosigner_data['soft_device_id'] = self.soft_device_id


class WCHWUninitialized(WalletWizardComponent):
    def __init__(self, parent, wizard):
        WalletWizardComponent.__init__(self, parent, wizard, title=_('Hardware not initialized'))

    def on_ready(self):
        cosigner_data = self.wizard.current_cosigner(self.wizard_data)
        _name, _info = cosigner_data['hardware_device']
        w_icon = QLabel()
        w_icon.setPixmap(QPixmap(icon_path('warning.png')).scaledToWidth(48, mode=Qt.TransformationMode.SmoothTransformation))
        w_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = WWLabel(_('This {} is not initialized. Use manufacturer tooling to initialize the device.').format(_info.model_name))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout().addStretch(1)
        self.layout().addWidget(w_icon)
        self.layout().addWidget(label)
        self.layout().addStretch(1)

    def apply(self):
        pass
