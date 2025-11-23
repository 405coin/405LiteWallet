                            
                                            
                                                                  
                                                                    
 
                                                                                                              
 
                                                                                                   
                                                                                         
                                                                                              
                                                                      
 
                                                                                      
                                                                                          
                                                                       
                                               
                                                                           
                                                                   
                                                                     
                                                                              
                                                            
                                                                            
                                     
                                   
                                                                                  
 
                                       
                                  
                                          
                                                                                               

import ctypes
import ctypes.util
import os
import sys
from typing import Optional

from .logging import get_logger


_logger = get_logger(__name__)

PR_GET_DUMPABLE = 3
PR_SET_DUMPABLE = 4


_libc = None                               
def _load_libc():
    global _libc
    if _libc is not None:
        return
                                                 
                                                                                                                 
    _libc_path = ctypes.util.find_library("c")
    _libc = ctypes.CDLL(_libc_path, use_errno=True)
    _libc.prctl.argtypes = (ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong)
    _libc.prctl.restype = ctypes.c_int


def set_dumpable(flag: bool) -> None:
    """Set the "dumpable" attribute on the current process.
    This controls whether a core dump will be produced if the process receives a signal whose
    default behavior is to produce a core dump.
    In addition, processes that are not dumpable cannot be attached with ptrace() PTRACE_ATTACH.

    In effect, another process running as the same user as us can read our memory if we are dumpable.
    """
    _load_libc()
    res = _libc.prctl(PR_SET_DUMPABLE, int(bool(flag)), 0, 0, 0)
    if res < 0:
        eno = ctypes.get_errno()
        raise OSError(eno, os.strerror(eno), None, None, None)


def set_dumpable_safe(flag: bool) -> None:
    try:
        _load_libc()
    except Exception as e:
        _logger.exception("error loading libc")
        return
    assert _libc is not None
    try:
        set_dumpable(flag)
    except OSError as e:
        _logger.error(f"libc.prctl(PR_SET_DUMPABLE, {flag}) errored: {e}")


def get_dumpable() -> bool:
    _load_libc()
    res = _libc.prctl(PR_GET_DUMPABLE, 0, 0, 0, 0)
    if res < 0:
        eno = ctypes.get_errno()
        raise OSError(eno, os.strerror(eno), None, None, None)
    return res != 0
