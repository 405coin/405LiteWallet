                                                                
                                                 
 
                             
                                                                   
                                                                                
                                                                                        
                                                                                                         
                                                                                                                  
                                                             
 
                                                                
                                 
 
          
 
                                       
                                        
                                                                
                                                                 
                                                                                                      
                                     
                                                                                                       
 
                                                   
                                               
                                                     
                                                  
 
                                                                                        
                       
                        
 
                                                                   
                                                                                                   
                                                                                                            
 
                                                                                                   
                                       
                                                                                
                                                 
 
 
        
 
          
                                                                                                            
                                                                                           
 
            
                                                                     
                                                                                                
                                                                                           
 
                                                       
                                                                                                
                                                                                                  
                                                          

import asyncio
import threading
import copy
from typing import Dict, Sequence, Optional, TYPE_CHECKING, Mapping, Set, List, Tuple

from . import util
from .bitcoin import dust_threshold
from .logging import Logger
from .util import log_exceptions, NotEnoughFunds, BelowDustLimit, NoDynamicFeeEstimates, OldTaskGroup
from .transaction import PartialTransaction, PartialTxOutput, Transaction, TxOutpoint, PartialTxInput
from .address_synchronizer import TX_HEIGHT_LOCAL, TX_HEIGHT_FUTURE
from .lnsweep import SweepInfo
from .json_db import locked, StoredDict
from .fee_policy import FeePolicy

if TYPE_CHECKING:
    from .wallet import Abstract_Wallet


class TxBatcher(Logger):

    SLEEP_INTERVAL = 1

    def __init__(self, wallet: 'Abstract_Wallet'):
        Logger.__init__(self)
        self.lock = threading.RLock()
        self.storage = wallet.db.get_stored_item("tx_batches", {})
        self.tx_batches = {}                            
        self.wallet = wallet
        for key, item_storage in self.storage.items():
            self.tx_batches[key] = TxBatch(self.wallet, item_storage)
        self._legacy_htlcs = {}                                     
        self.taskgroup = None                                
        self.password_future = None                                                 

    @locked
    def add_payment_output(self, key: str, output: 'PartialTxOutput') -> None:
        batch = self._maybe_create_new_batch(key, fee_policy_name=key)
        batch.add_payment_output(output)

    @locked
    def add_sweep_input(self, key: str, sweep_info: 'SweepInfo') -> None:
        """Can raise BelowDustLimit or NoDynamicFeeEstimates."""
        if sweep_info.txin and sweep_info.txout:
                                                         
            if sweep_info.name in ['received-htlc', 'offered-htlc'] and sweep_info.csv_delay == 0:
                if sweep_info.txin.prevout not in self._legacy_htlcs:
                    self.logger.info(f'received {sweep_info.name}')
                    self._legacy_htlcs[sweep_info.txin.prevout] = sweep_info
                return
        fee_policy_name = key
        if not sweep_info.can_be_batched:
                                                
            key = sweep_info.txin.prevout.to_str()
        batch = self._maybe_create_new_batch(key, fee_policy_name)
        batch.add_sweep_input(sweep_info)

    def _maybe_create_new_batch(self, key: str, fee_policy_name: str) -> 'TxBatch':
        assert util.get_running_loop() == util.get_asyncio_loop(), f"this must be run on the asyncio thread!"
        if key not in self.storage:
            self.logger.info(f'creating new batch: {key}')
            self.storage[key] = { 'fee_policy_name': fee_policy_name, 'txids': [], 'prevout': None }
            self.tx_batches[key] = batch = TxBatch(self.wallet, self.storage[key])
            if self.taskgroup:
                asyncio.ensure_future(self.taskgroup.spawn(self.run_batch(key, batch)))
        return self.tx_batches[key]

    @locked
    def delete_batch(self, key: str) -> None:
        self.logger.info(f'deleting TxBatch {key}')
        self.storage.pop(key)
        self.tx_batches.pop(key)

    def find_batch_by_prevout(self, prevout: str) -> Optional['TxBatch']:
        for k, v in self.tx_batches.items():
            if v._prevout == prevout:
                return v
        return None

    def find_batch_of_txid(self, txid: str) -> Optional[str]:
        for k, v in self.tx_batches.items():
            if v.is_mine(txid):
                return k
        return None

    def is_mine(self, txid: str) -> bool:
                                              
        return bool(self.find_batch_of_txid(txid))

    async def run_batch(self, key: str, batch: 'TxBatch') -> None:
        await batch.run()
        self.delete_batch(key)

    @log_exceptions
    async def run(self):
        self.taskgroup = OldTaskGroup()
        for key, batch in self.tx_batches.items():
            await self.taskgroup.spawn(self.run_batch(key, batch))
        async with self.taskgroup as group:
            await group.spawn(self.redeem_legacy_htlcs())

    async def redeem_legacy_htlcs(self) -> None:
        while True:
            await asyncio.sleep(self.SLEEP_INTERVAL)
            for sweep_info in self._legacy_htlcs.values():
                await self._maybe_redeem_legacy_htlcs(sweep_info)

    async def _maybe_redeem_legacy_htlcs(self, sweep_info: 'SweepInfo') -> None:
        assert sweep_info.csv_delay == 0
        local_height = self.wallet.network.get_local_height()
        wanted_height = sweep_info.cltv_abs
        if wanted_height - local_height > 0:
            return
        outpoint = sweep_info.txin.prevout.to_str()
        prev_txid, index = outpoint.split(':')
        if spender_txid := self.wallet.adb.db.get_spent_outpoint(prev_txid, int(index)):
            tx_mined_status = self.wallet.adb.get_tx_height(spender_txid)
            if tx_mined_status.height() > 0:
                return
            if tx_mined_status.height() not in [TX_HEIGHT_LOCAL, TX_HEIGHT_FUTURE]:
                return
        self.logger.info(f'will broadcast standalone tx {sweep_info.name}')
        tx = PartialTransaction.from_io([sweep_info.txin], [sweep_info.txout], locktime=sweep_info.cltv_abs, version=2)
        self.wallet.sign_transaction(tx, password=None, ignore_warnings=True)
        if await self.wallet.network.try_broadcasting(tx, sweep_info.name):
            self.wallet.adb.add_transaction(tx)

    async def get_password(self, txid: str) -> Optional[str]:
                                                 
        password = self.wallet.get_unlocked_password()
        if password:
            return password
        future = self.get_password_future(txid)
        try:

            await future
        except asyncio.CancelledError as e:
            return None
        password = future.result()
        return password

    @locked
    def set_password_future(self, password: Optional[str]) -> None:
        if self.password_future is not None:
            if password is not None:
                self.password_future.set_result(password)
            else:
                self.password_future.cancel()
            self.password_future = None
            util.trigger_callback('password_not_required', self.wallet)

    @locked
    def get_password_future(self, txid: str):
        if self.password_future is None:
            self.password_future = asyncio.Future()
            self.password_future.txids = []
            self.logger.info(f'password required: {txid}')
        self.password_future.txids.append(txid)
        util.trigger_callback('password_required', self.wallet)
        return self.password_future


class TxBatch(Logger):

    def __init__(self, wallet: 'Abstract_Wallet', storage: StoredDict):
        Logger.__init__(self)
        self.wallet = wallet
        self.storage = storage
        self.lock = threading.RLock()
        self.batch_payments = []                                                               
        self.batch_inputs = {}                                                                
                                                                                                                  
        self._prevout = storage.get('prevout')                       
        self._batch_txids = storage['txids']                   
        self._fee_policy_name = storage.get('fee_policy_name', 'default')             
        self._base_tx = None                                                                                        
        self._parent_tx = None                                      
        self._unconfirmed_sweeps = set()                                                                                    

    @property
    def fee_policy(self) -> FeePolicy:
                                                             
        cv_name = 'fee_policy' + '.' + self._fee_policy_name
        descriptor = self.wallet.config.get(cv_name, 'eta:2')
        return FeePolicy(descriptor)

    @log_exceptions
    async def run(self) -> None:
        while not self.is_done():
            await asyncio.sleep(self.wallet.txbatcher.SLEEP_INTERVAL)
            if not (self.wallet.network and self.wallet.network.is_connected()):
                continue
            try:
                await self.run_iteration()
            except Exception as e:
                self.logger.exception(f'TxBatch error: {repr(e)}')
                break

    def is_mine(self, txid: str) -> bool:
        return txid in self._batch_txids

    @locked
    def add_payment_output(self, output: 'PartialTxOutput') -> None:
                                                         
        self.batch_payments.append(output)

    def is_dust(self, sweep_info: SweepInfo) -> bool:
        """Can raise NoDynamicFeeEstimates."""
        if sweep_info.dust_override:
            return False
        if sweep_info.txout is not None:
            return False
        value = sweep_info.txin.value_sats()
        witness_size = len(sweep_info.txin.make_witness(71*b'\x00'))
        tx_size_vbytes = 84 + witness_size//4                                           
        fee = self.fee_policy.estimate_fee(tx_size_vbytes, network=self.wallet.network)
        is_dust = value - fee <= dust_threshold()
        self.logger.info(f'{sweep_info.name} size = {tx_size_vbytes}: {is_dust=}')
        return is_dust

    @locked
    def add_sweep_input(self, sweep_info: 'SweepInfo') -> None:
        """Can raise BelowDustLimit or NoDynamicFeeEstimates."""
        if self.is_dust(sweep_info):
                                                                                       
                                                                                     
                                                                              
            raise BelowDustLimit
        txin = sweep_info.txin
        if txin.prevout in self._unconfirmed_sweeps:
            return
                                                      
                                                                
        prevout = txin.prevout.to_str()
        prev_txid, index = prevout.split(':')
        if spender_txid := self.wallet.adb.db.get_spent_outpoint(prev_txid, int(index)):
            tx_mined_status = self.wallet.adb.get_tx_height(spender_txid)
            if tx_mined_status.height() > 0:
                return
        self._unconfirmed_sweeps.add(txin.prevout)
        self.logger.info(f'add_sweep_info: {sweep_info.name} {sweep_info.txin.prevout.to_str()}')
        self.batch_inputs[txin.prevout] = sweep_info

    @locked
    def _to_pay_after(self, tx: Optional[PartialTransaction]) -> Sequence[PartialTxOutput]:
        if not tx:
            return self.batch_payments
                                          
                                                                           
        to_pay = []
        outputs = copy.deepcopy(tx.outputs())
        for x in self.batch_payments:
            if x not in outputs:
                to_pay.append(x)
            else:
                outputs.remove(x)
        return to_pay

    @locked
    def _to_sweep_after(self, tx: Optional[PartialTransaction]) -> Dict[TxOutpoint, SweepInfo]:
        tx_prevouts = set(txin.prevout for txin in tx.inputs()) if tx else set()
        result = []                                            
        for prevout, sweep_info in list(self.batch_inputs.items()):
            assert prevout == sweep_info.txin.prevout
            prev_txid, index = prevout.to_str().split(':')
            if not self.wallet.adb.db.get_transaction(prev_txid):
                continue
            if sweep_info.is_anchor():
                prev_tx_mined_status = self.wallet.adb.get_tx_height(prev_txid)
                if prev_tx_mined_status.conf > 0:
                    self.logger.info(f"anchor not needed {prevout}")
                    self.batch_inputs.pop(prevout)                                                                               
                    continue
            if spender_txid := self.wallet.adb.db.get_spent_outpoint(prev_txid, int(index)):
                tx_mined_status = self.wallet.adb.get_tx_height(spender_txid)
                if tx_mined_status.height() not in [TX_HEIGHT_LOCAL, TX_HEIGHT_FUTURE]:
                    continue
            if prevout in tx_prevouts:
                continue
            result.append((prevout, sweep_info))
        return dict(result)

    def _should_bump_fee(self, base_tx: Optional[PartialTransaction]) -> bool:
        if base_tx is None:
            return False
        if not self.is_mine(base_tx.txid()):
            return False
        base_tx_fee = base_tx.get_fee()
        recommended_fee = self.fee_policy.estimate_fee(base_tx.estimated_size(), network=self.wallet.network)
        should_bump_fee = base_tx_fee * 1.1 < recommended_fee
        if should_bump_fee:
            self.logger.info(f'base tx fee too low {base_tx_fee} < {recommended_fee}. we will bump the fee')
        return should_bump_fee

    def is_done(self):
                                                  
        return len(self.batch_inputs) == 0 and len(self.batch_payments) == 0 and len(self._batch_txids) == 0

    async def find_base_tx(self) -> Optional[PartialTransaction]:
        if not self._prevout:
            return None
        prev_txid, index = self._prevout.split(':')
        txid = self.wallet.adb.db.get_spent_outpoint(prev_txid, int(index))
        tx = self.wallet.adb.get_transaction(txid) if txid else None
        if not tx:
            return None
        tx = PartialTransaction.from_tx(tx)
        tx.add_info_from_wallet(self.wallet)                       

        if self.is_mine(txid):
            if self._base_tx is None:
                self.logger.info(f'found base_tx {txid}')
            self._base_tx = tx
        else:
            self.logger.info(f'base tx was replaced by {tx.txid()}')
            self._new_base_tx(tx)
                                                                
        tx_mined_status = self.wallet.adb.get_tx_height(txid)
        if tx_mined_status.conf > 0:
            self.logger.info(f'base tx confirmed {txid}')
            self._clear_unconfirmed_sweeps(tx)
            self._start_new_batch(tx)
        if tx_mined_status.height() in [TX_HEIGHT_LOCAL]:
                                                                    
                                                                    
                                                          
            await self.wallet.network.try_broadcasting(tx, 'batch')

        return self._base_tx

    async def run_iteration(self) -> None:
        base_tx = await self.find_base_tx()
        try:
            tx = self.create_next_transaction(base_tx)
        except NoDynamicFeeEstimates:
            self.logger.debug('no dynamic fee estimates available')
            return
        except Exception as e:
            if base_tx:
                self.logger.exception(f'Cannot create batch transaction: {repr(e)}')
                self._start_new_batch(base_tx)
                return
            else:
                                             
                raise

        if tx is None:
                           
            return

                                                     
                                                      
                                                                          
                                                                         
        self.wallet.adb.add_transaction(tx)
                        
        if not await self.sign_transaction(tx):
            self.wallet.adb.remove_transaction(tx.txid())
            return

                            
        self._new_base_tx(tx)

        if not await self.wallet.network.try_broadcasting(tx, 'batch'):
            self.logger.info(f'cannot broadcast tx {tx.txid()}')
            if base_tx:
                                                              
                                                                      
                                                                    
                                                                 
                                                      

                                                             
                                                                      
                                                                 
                                    
                self.wallet.adb.remove_transaction(tx.txid())
                self.logger.info(f'starting new batch because could not broadcast')
                self._start_new_batch(base_tx)
            else:
                                                                    
                                                                   
                                                                     
                                                                     
                         
                 
                                                             
                                                                   
                                                                 
                                                                      
                pass

    async def sign_transaction(self, tx: PartialTransaction) -> Optional[PartialTransaction]:
        tx.add_info_from_wallet(self.wallet)                           
        self.add_sweep_info_to_tx(tx)
        pw_required = self.wallet.has_keystore_encryption() and tx.requires_keystore()
        password = await self.wallet.txbatcher.get_password(tx.txid()) if pw_required else None
        if password is None and pw_required:
            return None
        self.wallet.sign_transaction(tx, password)
        assert tx.is_complete()
        return tx

    def create_next_transaction(self, base_tx: Optional[PartialTransaction]) -> Optional[PartialTransaction]:
        to_pay = self._to_pay_after(base_tx)
        to_sweep = self._to_sweep_after(base_tx)
        to_sweep_now = []                         
        for k, v in to_sweep.items():
            can_broadcast, wanted_height = self._can_broadcast(v, base_tx)
            if can_broadcast:
                to_sweep_now.append(v)
            else:
                self.wallet.add_future_tx(v, wanted_height)
        while True:
            if not to_pay and not to_sweep_now and not self._should_bump_fee(base_tx):
                return None
            try:
                tx = self._create_batch_tx(base_tx=base_tx, to_sweep=to_sweep_now, to_pay=to_pay)
            except NotEnoughFunds:
                if to_pay:
                    k = max(to_pay, key=lambda x: x.value)
                    self.logger.info(f'Not enough funds, removing output {k}')
                    to_pay.remove(k)
                    continue
                else:
                    self.logger.info(f'Not enough funds, waiting')
                    return None
                                          
            if tx.estimated_size() < 100_000:
                break
            to_sweep_now = to_sweep_now[0:len(to_sweep_now)//2]
            to_pay = to_pay[0:len(to_pay)//2]

        self.logger.info(f'created tx {tx.txid()} with {len(tx.inputs())} inputs and {len(tx.outputs())} outputs')
        return tx

    def add_sweep_info_to_tx(self, base_tx: PartialTransaction) -> None:
        for txin in base_tx.inputs():
            if sweep_info := self.batch_inputs.get(txin.prevout):
                if hasattr(sweep_info.txin, 'make_witness'):
                    txin.make_witness = sweep_info.txin.make_witness
                    txin.privkey = sweep_info.txin.privkey
                    txin.witness_script = sweep_info.txin.witness_script
                    txin.script_sig = sweep_info.txin.script_sig

    def _create_batch_tx(
        self,
        *,
        base_tx: Optional[PartialTransaction],
        to_sweep: Sequence[SweepInfo],
        to_pay: Sequence[PartialTxOutput],
    ) -> PartialTransaction:
        self.logger.info(f'to_sweep: {[x.txin.prevout.to_str() for x in to_sweep]}')
        self.logger.info(f'to_pay: {to_pay}')
        inputs = []                              
        outputs = []                               
        locktime = base_tx.locktime if base_tx else None
                                                        
        for sweep_info in sorted(to_sweep, key=lambda x: not bool(x.txout)):
            if sweep_info.cltv_abs is not None:
                if locktime is None or locktime < sweep_info.cltv_abs:
                                                                                   
                    locktime = sweep_info.cltv_abs
            inputs.append(copy.deepcopy(sweep_info.txin))
            if sweep_info.txout:
                outputs.append(sweep_info.txout)
        self.logger.info(f'locktime: {locktime}')
        outputs += to_pay
        inputs += self._create_inputs_from_tx_change(self._parent_tx) if self._parent_tx else []
                   
        coins = self.wallet.get_spendable_coins(nonlocal_only=True)
        tx = self.wallet.make_unsigned_transaction(
            coins=coins,
            fee_policy=self.fee_policy,
            base_tx=base_tx,
            inputs=inputs,
            outputs=outputs,
            locktime=locktime,
            BIP69_sort=False,
            merge_duplicate_outputs=False,
        )
                                                             
        for o in outputs: assert o in tx.outputs()
        return tx

    def _clear_unconfirmed_sweeps(self, tx: PartialTransaction) -> None:
                                                         
                                                                                    
        for txin in tx.inputs():
            if txin.prevout in self._unconfirmed_sweeps:
                self._unconfirmed_sweeps.remove(txin.prevout)

    @locked
    def _start_new_batch(self, tx: Optional[PartialTransaction]) -> None:
        use_change = tx and tx.has_change() and any([txout in self.batch_payments for txout in tx.outputs()])
        self.batch_payments = self._to_pay_after(tx)
        self.batch_inputs = self._to_sweep_after(tx)
        self._batch_txids.clear()
        self._base_tx = None
        self._parent_tx = tx if use_change else None
        self._prevout = None

    @locked
    def _new_base_tx(self, tx: PartialTransaction) -> None:
        self._prevout = tx.inputs()[0].prevout.to_str()
        self.storage['prevout'] = self._prevout
        if tx.has_change():
            self._batch_txids.append(tx.txid())
            self._base_tx = tx
        else:
            self.logger.info(f'starting new batch because current base tx does not have change')
            self._start_new_batch(tx)

    def _create_inputs_from_tx_change(self, parent_tx: PartialTransaction) -> List[PartialTxInput]:
        inputs = []
        for o in parent_tx.get_change_outputs():
            coins = self.wallet.adb.get_addr_utxo(o.address)
            inputs += list(coins.values())
        for txin in inputs:
            txin.nsequence = 0xffffffff - 2
        return inputs

    def _can_broadcast(self, sweep_info: 'SweepInfo', base_tx: 'Transaction') -> Tuple[bool, Optional[int]]:
        prevout = sweep_info.txin.prevout.to_str()
        name = sweep_info.name
        prev_txid, index = prevout.split(':')
        can_broadcast = True
        wanted_height_cltv = None
        wanted_height_csv = None
        local_height = self.wallet.network.get_local_height()
        if sweep_info.cltv_abs:
            wanted_height_cltv = sweep_info.cltv_abs
            if wanted_height_cltv - local_height > 0:
                can_broadcast = False
        prev_height = self.wallet.adb.get_tx_height(prev_txid).height()
        if sweep_info.csv_delay:
            if prev_height > 0:
                wanted_height_csv = prev_height + sweep_info.csv_delay - 1
                if wanted_height_csv - local_height > 0:
                    can_broadcast = False
            else:
                can_broadcast = False
                wanted_height_csv = local_height + sweep_info.csv_delay
        if not can_broadcast:
            wanted_height = max((wanted_height_csv or 0), (wanted_height_cltv or 0))
        else:
            wanted_height = None
        if base_tx and prev_height <= 0:
                                                                                  
                                                                     
            if can_broadcast:
                can_broadcast = False
                wanted_height = local_height + 1
        return can_broadcast, wanted_height

