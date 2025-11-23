import sys
import os

                                               
is_bundle = getattr(sys, 'frozen', False)
is_local = not is_bundle and os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)), "405litewallet.desktop"))

                                                                                       
if is_local and os.name == 'nt':                                                            
    os.add_dll_directory(os.path.dirname(__file__))


class GuiImportError(ImportError):
    pass


from .version import ELECTRUM_VERSION
from .util import format_satoshis
from .wallet import Wallet
from .storage import WalletStorage
from .coinchooser import COIN_CHOOSERS
from .network import Network, pick_random_server
from .interface import Interface
from .simple_config import SimpleConfig
from . import bitcoin
from . import transaction
from . import daemon
from .transaction import Transaction
from .plugin import BasePlugin
from .commands import Commands, known_commands
from .logging import get_logger


__version__ = ELECTRUM_VERSION

_logger = get_logger(__name__)


                                                                            
                                                                                                   
                                                                                             
try:
    assert False              
except AssertionError:
    pass
else:
    raise ImportError("Running with asserts disabled. Refusing to continue. Exiting...")
