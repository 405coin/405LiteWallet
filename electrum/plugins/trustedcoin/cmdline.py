#!/usr/bin/env python
 
                                       
                                    
 
                                                             
                                                                      
                                                                
                                                                      
                                                                      
                                                                   
                                      
 
                                                                
                                                                 
 
                                                                 
                                                                    
                                                       
                                                                     
                                                                    
                                                                   
                                                                  
           

from electrum.i18n import _
from .trustedcoin import TrustedCoinPlugin


class Plugin(TrustedCoinPlugin):

    def prompt_user_for_otp(self, wallet, tx):                        
        if not isinstance(wallet, self.wallet_class):
            return
        if not wallet.can_sign_without_server():
            self.logger.info("twofactor:sign_tx")
            auth_code = None
            if wallet.keystores['x3'].can_sign(tx, ignore_watching_only=True):
                msg = _('Please enter your Google Authenticator code:')
                auth_code = int(input(msg))
            else:
                self.logger.info("twofactor: xpub3 not needed")
            wallet.auth_code = auth_code

