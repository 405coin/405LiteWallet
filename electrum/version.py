ELECTRUM_VERSION = '1.0.1'                                      

PROTOCOL_VERSION_MIN = '1.4'                        
PROTOCOL_VERSION_MAX = '1.6'

                                                    
SEED_PREFIX        = '01'                       
SEED_PREFIX_SW     = '100'                    
SEED_PREFIX_2FA    = '101'                                
SEED_PREFIX_2FA_SW = '102'                                    


def seed_prefix(seed_type):
    if seed_type == 'standard':
        return SEED_PREFIX
    elif seed_type == 'segwit':
        return SEED_PREFIX_SW
    elif seed_type == '2fa':
        return SEED_PREFIX_2FA
    elif seed_type == '2fa_segwit':
        return SEED_PREFIX_2FA_SW
    raise Exception(f"unknown seed_type: {seed_type!r}")
