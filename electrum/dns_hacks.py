                                            
                                                                  
                                                                    

import sys
import socket
import concurrent
from concurrent import futures
import ipaddress
import asyncio

import dns
import dns.asyncresolver

from .logging import get_logger
from .util import get_asyncio_loop
from . import util

_logger = get_logger(__name__)


def configure_dns_resolver() -> None:
                                                     
    if not hasattr(socket, "_getaddrinfo"):
        socket._getaddrinfo = socket.getaddrinfo
    if sys.platform == 'win32':
                                                                                              
                                                                                                      
                                                              
        try:
            _prepare_windows_dns_hack()
        except Exception as e:
            _logger.exception('failed to apply windows dns hack.')
        else:
            socket.getaddrinfo = _fast_getaddrinfo


def _prepare_windows_dns_hack():
                      
    resolver = dns.asyncresolver.get_default_resolver()
    if resolver.cache is None:
        resolver.cache = dns.resolver.Cache()
                                                        
    resolver.lifetime = max(resolver.lifetime or 1, 30.0)


def _is_force_system_dns_for_host(host: str) -> bool:
    return str(host) in ('localhost', 'localhost.',)


def _fast_getaddrinfo(host, *args, **kwargs):
    def needs_dns_resolving(host):
        try:
            ipaddress.ip_address(host)
            return False                    
        except ValueError:
            pass             
        if _is_force_system_dns_for_host(host):
            return False
        return True

    def resolve_with_dnspython(host):
        addrs = []
        expected_errors = (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
                           concurrent.futures.CancelledError, concurrent.futures.TimeoutError)
        loop = get_asyncio_loop()
        assert util.get_running_loop() != loop, 'must not be called from asyncio thread'
        ipv6_fut = asyncio.run_coroutine_threadsafe(
            dns.asyncresolver.resolve(host, dns.rdatatype.AAAA),
            loop,
        )
        ipv4_fut = asyncio.run_coroutine_threadsafe(
            dns.asyncresolver.resolve(host, dns.rdatatype.A),
            loop,
        )
                  
        try:
            answers = ipv6_fut.result()
            addrs += [str(answer) for answer in answers]
        except expected_errors as e:
            pass
        except BaseException as e:
            _logger.info(f'dnspython failed to resolve dns (AAAA) for {repr(host)} with error: {repr(e)}')
                  
        try:
            answers = ipv4_fut.result()
            addrs += [str(answer) for answer in answers]
        except expected_errors as e:
                                                                                    
                                                                                 
            if not addrs:
                raise socket.gaierror(11001, 'getaddrinfo failed') from e
        except BaseException as e:
                                                                         
            _logger.info(f'dnspython failed to resolve dns (A) for {repr(host)} with error: {repr(e)}')
        if addrs:
            return addrs
                                                                  
        return [host]

    addrs = [host]
    if needs_dns_resolving(host):
        addrs = resolve_with_dnspython(host)
    list_of_list_of_socketinfos = [socket._getaddrinfo(addr, *args, **kwargs) for addr in addrs]
    list_of_socketinfos = [item for lst in list_of_list_of_socketinfos for item in lst]
    return list_of_socketinfos
