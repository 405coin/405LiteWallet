#!/usr/bin/env python
 
                                       
                                            
 
                                                             
                                                                      
                                                                
                                                                      
                                                                      
                                                                   
                                      
 
                                                                
                                                                 
 
                                                                 
                                                                    
                                                       
                                                                     
                                                                    
                                                                   
                                                                  
           
import asyncio
import json
import ssl
import time
from contextlib import asynccontextmanager

import electrum_ecc as ecc
import electrum_aionostr as aionostr
from electrum_aionostr.key import PrivateKey
from typing import Dict, TYPE_CHECKING, Union, List, Tuple, Optional, Callable

from electrum import util, Transaction
from electrum.crypto import sha256
from electrum.i18n import _
from electrum.logging import Logger
from electrum.plugin import BasePlugin
from electrum.transaction import PartialTransaction, tx_from_any
from electrum.util import (
    log_exceptions, OldTaskGroup, ca_path, trigger_callback, event_listener, json_decode, make_aiohttp_proxy_connector
)
from electrum.wallet import Multisig_Wallet

if TYPE_CHECKING:
    from electrum.wallet import Abstract_Wallet
    from aiohttp_socks import ProxyConnector

                                                          
NOSTR_EVENT_KIND = 4

now = lambda: int(time.time())


class PsbtNostrPlugin(BasePlugin):

    def __init__(self, parent, config, name):
        BasePlugin.__init__(self, parent, config, name)
        self.cosigner_wallets = {}                                               

    def is_available(self):
        return True

    def add_cosigner_wallet(self, wallet: 'Abstract_Wallet', cosigner_wallet: 'CosignerWallet'):
        assert isinstance(wallet, Multisig_Wallet)
        self.cosigner_wallets[wallet] = cosigner_wallet

    def remove_cosigner_wallet(self, wallet: 'Abstract_Wallet'):
        if cw := self.cosigner_wallets.get(wallet):
            cw.close()
            self.cosigner_wallets.pop(wallet)


class CosignerWallet(Logger):
                                                       
                                              
                                                          

    KEEP_DELAY = 24*60*60

    def __init__(self, wallet: 'Multisig_Wallet', db_storage: dict):
        assert isinstance(wallet, Multisig_Wallet)
        self.wallet = wallet

        Logger.__init__(self)

        self.network = wallet.network
        self.config = self.wallet.config

        self.pending = asyncio.Event()

        self.known_events = db_storage.setdefault('cosigner_events', {})

        for k, v in list(self.known_events.items()):
            if v < now() - self.KEEP_DELAY:
                self.logger.info(f'deleting old event {k}')
                self.known_events.pop(k)
        self.ssl_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH, cafile=ca_path)
        self.logger.info(f"relays {self.config.NOSTR_RELAYS.split(',')}")

        self.cosigner_list = []                               
        self.nostr_pubkey = None

        for keystore in wallet.get_keystores():
                                                                              
                                                                                      
            xpub = keystore.get_master_public_key()             
            privkey = sha256('nostr_psbt:' + xpub)
            pubkey = ecc.ECPrivkey(privkey).get_public_key_bytes()[1:]
            if self.nostr_pubkey is None and not keystore.is_watching_only():
                self.nostr_privkey = privkey.hex()
                self.nostr_pubkey = pubkey.hex()
                self.logger.info(f'nostr pubkey: {self.nostr_pubkey}')
            else:
                self.cosigner_list.append((xpub, pubkey.hex()))

        self.messages = asyncio.Queue()
        self.taskgroup = OldTaskGroup()
        if self.network and self.nostr_pubkey:
            asyncio.run_coroutine_threadsafe(self.main_loop(), self.network.asyncio_loop)

    @event_listener
    async def on_event_proxy_set(self, *args):
        if not (self.network and self.nostr_pubkey):
            return
        await self.stop()
        self.taskgroup = OldTaskGroup()
        asyncio.run_coroutine_threadsafe(self.main_loop(), self.network.asyncio_loop)

    @log_exceptions
    async def main_loop(self):
        self.logger.info("starting taskgroup.")
        try:
                                                                    
            while not self.wallet.is_up_to_date():
                await self.wallet.up_to_date_changed_event.wait()
            self.logger.debug('starting handling of PSBTs')
            async with self.taskgroup as group:
                await group.spawn(self.check_direct_messages())
        except Exception as e:
            self.logger.exception("taskgroup died.")
        finally:
            self.logger.info("taskgroup stopped.")

    async def stop(self):
        await self.taskgroup.cancel_remaining()

    @asynccontextmanager
    async def nostr_manager(self):
        if self.network.proxy and self.network.proxy.enabled:
            proxy = make_aiohttp_proxy_connector(self.network.proxy, self.ssl_context)
        else:
            proxy: Optional['ProxyConnector'] = None
        manager_logger = self.logger.getChild('aionostr')
        manager_logger.setLevel("INFO")                                            
        async with aionostr.Manager(
                relays=self.config.NOSTR_RELAYS.split(','),
                private_key=self.nostr_privkey,
                ssl_context=self.ssl_context,
                proxy=proxy,
                log=manager_logger
        ) as manager:
            yield manager

    @log_exceptions
    async def send_direct_messages(self, messages: List[Tuple[str, dict]]):
        our_private_key: PrivateKey = aionostr.key.PrivateKey(bytes.fromhex(self.nostr_privkey))
        async with self.nostr_manager() as manager:
            for pubkey, msg in messages:
                encrypted_msg: str = our_private_key.encrypt_message(json.dumps(msg), pubkey)
                eid = await aionostr._add_event(
                    manager,
                    kind=NOSTR_EVENT_KIND,
                    content=encrypted_msg,
                    private_key=self.nostr_privkey,
                    tags=[['p', pubkey], ['expiration', str(int(now() + self.KEEP_DELAY))]])
                self.logger.info(f'message sent to {pubkey}: {eid}')

    @log_exceptions
    async def check_direct_messages(self):
        privkey = PrivateKey(bytes.fromhex(self.nostr_privkey))
        async with self.nostr_manager() as manager:
            await manager.connect()
            query = {
                "kinds": [NOSTR_EVENT_KIND],
                "limit": 100,
                "#p": [self.nostr_pubkey],
                "since": int(now() - self.KEEP_DELAY),
            }
            async for event in manager.get_events(query, single_event=False, only_stored=False):
                if event.id in self.known_events:
                    self.logger.info(f'known event {event.id} {util.age(event.created_at)}')
                    continue
                if not any(event.pubkey == pubkey for _xpub, pubkey in self.cosigner_list):
                    self.logger.warning(f"got event from unknown author: {event.pubkey}")
                    continue
                if event.created_at > now() + self.KEEP_DELAY:
                                        
                    continue
                if event.created_at < now() - self.KEEP_DELAY:
                    continue
                self.logger.info(f'new event {event.id}')
                try:
                    message = privkey.decrypt_message(event.content, event.pubkey)
                except Exception as e:
                    self.logger.info(f'could not decrypt message {event.pubkey}')
                    self.known_events[event.id] = now()
                    continue
                try:
                    message = json_decode(message)
                    if not isinstance(message, dict):
                        raise Exception("malformed message, not dict")
                    tx_hex = message.get('tx')
                    label = message.get('label', '')
                    tx = tx_from_any(tx_hex)
                except Exception as e:
                    self.logger.info(_("Unable to deserialize the transaction:") + "\n" + str(e))
                    self.known_events[event.id] = now()
                    continue
                self.logger.info(f"received PSBT from {event.pubkey}")
                trigger_callback('psbt_nostr_received', self.wallet, event.pubkey, event.id, tx, label)
                await self.pending.wait()
                self.pending.clear()

    def diagnostic_name(self):
        return self.wallet.diagnostic_name()

    def close(self):
        if not self.network:
            return
        self.logger.info("shutting down listener")
        asyncio.run_coroutine_threadsafe(self.stop(), self.network.asyncio_loop)

    def cosigner_can_sign(self, tx: Transaction, cosigner_xpub: str) -> bool:
                                       
                                                                                                 
                                                                                       
        return True

    def can_send_psbt(self, tx: Union[Transaction, PartialTransaction]) -> bool:
        if tx.is_complete() or self.wallet.can_sign(tx):
            return False
        for xpub, pubkey in self.cosigner_list:
            if self.cosigner_can_sign(tx, xpub):
                return True
        return False

    def mark_pending_event_rcvd(self, event_id):
        self.logger.debug('marking event rcvd')
        self.known_events[event_id] = now()
        self.pending.set()

    def prepare_messages(self, tx: Union[Transaction, PartialTransaction], label: str = None) -> List[Tuple[str, dict]]:
        messages = []
        for xpub, pubkey in self.cosigner_list:
            if not self.cosigner_can_sign(tx, xpub):
                continue
            payload = {'tx': tx.serialize_as_bytes().hex()}
            if label:
                payload['label'] = label
            messages.append((pubkey, payload))
        return messages

    def send_psbt(self, tx: Union[Transaction, PartialTransaction], label: str):
        self.do_send(self.prepare_messages(tx, label), tx.txid())

    def do_send(self, messages: List[Tuple[str, dict]], txid: Optional[str] = None):
        raise NotImplementedError()

    def on_receive(self, pubkey, event_id, tx, label: str):
        raise NotImplementedError()

    def add_transaction_to_wallet(
        self,
        tx: Union['Transaction', 'PartialTransaction'],
        *,
        label: str = None,
        on_failure: Callable[[str], None] = None,
        on_success: Callable[[], None] = None
    ) -> None:
        assert tx.txid(), "Shouldn't allow to save tx without txid"
        try:
                                                                     
                                                                   
                                                                            
                                     
            if not self.wallet.adb.add_transaction(tx):
                                                                                                       
                raise Exception('transaction was not added')
            if label:
                self.wallet.set_label(tx.txid(), label)
        except Exception as e:
            if on_failure:
                on_failure(str(e))
        else:
            self.wallet.save_db()
            if on_success:
                on_success()
