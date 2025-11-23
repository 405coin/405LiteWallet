#!/usr/bin/env python3
 
                                            
                                                  
 
                                                             
                                                                      
                                                                
                                                                      
                                                                      
                                                                   
                                      
 
                                                                
                                                                 
 
                                                                 
                                                                    
                                                       
                                                                     
                                                                    
                                                                   
                                                                  
           
 
                                                                             

from typing import Optional

from ..logging import get_logger

from .abstract_base import AbstractQrCodeReader, QrCodeResult


_logger = get_logger(__name__)


class MissingQrDetectionLib(RuntimeError):
    ''' Raised if we can't find zbar or whatever other platform lib
    we require to detect QR in image frames. '''


def get_qr_reader() -> AbstractQrCodeReader:
    """
    Get the Qr code reader for the current platform.
    Might raise exception: MissingQrDetectionLib.
    """
    excs = []
    try:
        from .zbar import ZbarQrCodeReader
        return ZbarQrCodeReader()
        """
        # DEBUG CODE BELOW
        # If you want to test this code on a platform that doesn't yet work or have
        # zbar, use the below...
        class Fake(AbstractQrCodeReader):
            def read_qr_code(self, buffer, buffer_size, dummy, width, height, frame_id = -1):
                ''' fake noop to test '''
                return []
        return Fake()
        """
    except MissingLib as e:
        _logger.exception("")
        excs.append(e)

    raise MissingQrDetectionLib(f"The platform QR detection library is not available.\nerrors: {excs!r}")


                                                

class MissingLib(RuntimeError):
    ''' Raised by underlying implementation if missing libs '''
    pass
