#!/usr/bin/env python
 
                                       
                                            
 
                                                             
                                                                      
                                                                
                                                                      
                                                                      
                                                                   
                                      
 
                                                                
                                                                 
 
                                                                 
                                                                    
                                                       
                                                                     
                                                                    
                                                                   
                                                                  
           
from typing import TYPE_CHECKING

from electrum.plugin import BasePlugin, hook

from .server import HttpSwapServer

if TYPE_CHECKING:
    from electrum.simple_config import SimpleConfig
    from electrum.daemon import Daemon
    from electrum.wallet import Abstract_Wallet


class SwapServerPlugin(BasePlugin):

    def __init__(self, parent, config: 'SimpleConfig', name):
        BasePlugin.__init__(self, parent, config, name)
        self.config = config
        self.server = None

    @hook
    def daemon_wallet_loaded(self, daemon: 'Daemon', wallet: 'Abstract_Wallet'):
                                        
        if self.server is not None:
            return
        sm = wallet.lnworker.swap_manager
        sm.is_server = True
        sm.http_server = HttpSwapServer(self.config, wallet)
