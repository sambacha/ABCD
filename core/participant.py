from typing import cast

import requests
import bitcoinutils.keys as btckeys
import litecoinutils.keys as ltckeys
import bitcoinutils.script as btcscript
import litecoinutils.script as ltcscript
import bitcoinutils.transactions as btctrans
import litecoinutils.transactions as ltctrans
from bitcoinutils.constants import SIGHASH_ALL

from core.secret import Secret
from website.webapp import *


def broadcast_transaction(raw_transaction, network):
    if network == 'btc-test3':
        # headers = {'content-type': 'application/x-www-form-urlencoded'}
        # url = 'https://api.blockcypher.com/v1/btc/test3/txs/push'
        # data = '{"tx": "%s"}' % raw_transaction

        # url = 'https://testnet-api.smartbit.com.au/v1/blockchain/pushtx'
        # data = '{"hex": "%s"}' % raw_transaction

        url = 'https://api.cryptoapis.io/v1/bc/btc/testnet/txs/send/'
        headers = {'Content-Type': 'application/json', 'X-API-Key': 'c186f1a43625f540e474a1653f4e5ccfe6003c3a'}
        data = '{"hex": "%s"}' % raw_transaction

    elif network == 'bcy-tst':
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        url = 'https://api.blockcypher.com/v1/bcy/test/txs/push'
        data = '{"tx": "%s"}' % raw_transaction
    elif network == 'ltc-tst':
        url = 'https://api.bitaps.com/ltc/testnet/native/'
        data = '{"jsonrpc":"1.0","id":"1","method":"sendrawtransaction","params":["%s"]}' % raw_transaction
        headers = {'content - type': 'application / x - www - form - urlencoded;charset = UTF - 8',}

        # return requests.post('https://api.bitaps.com/ltc/testnet/native/',
        #                      data='{"jsonrpc":"1.0","id":"1","method":"sendrawtransaction","params":["%s"]}' % raw_transaction,
        #                      headers=headers)
    else:
        raise ValueError("Network must be one of 'btc-test3', 'bcy-tst', or 'ltc-tst")

    return requests.post(
        url,
        headers=headers,
        data=data)


def get_network_2(network="btctest3"):
    return {"keys": btckeys, "script": btcscript, "trans": btctrans} if network == "btc-test3" \
        else {"keys": ltckeys, "script": ltcscript, "trans": ltctrans}


async def wait_until_next_interrupt():
    # return
    while True:
        await asyncio.sleep(0.3)
        if asyncState.next == 'P':
            # print("Waiting")
            continue
        else:
            asyncState.next = 'P'
            return


class Participant:
    # network: str
    # _wif: str
    # secret_key: PrivateKey
    # public_key: PublicKey

    # _wif_BCY: str
    # secret_key_BCY: PrivateKey
    # public_key_BCY: PublicKey

    # websocket: websockets

    def __init__(self, wif: str, name, network="btc-test3"):
        self.name = name
        self.network = network
        self.load_keys(wif=wif, network=network)

    def load_keys(self, wif: str, network="btc-test3"):
        if network == "btc-test3":
            self._wif = wif
            self.secret_key = btckeys.PrivateKey.from_wif(self._wif)
            self.public_key = self.secret_key.get_public_key()
        elif network == "ltc-tst":
            self._wif_LTC = wif
            self.secret_key_LTC = ltckeys.PrivateKey.from_wif(self._wif_LTC)
            self.public_key_LTC = self.secret_key_LTC.get_public_key()
        else:
            raise ValueError("Network must be one of 'btc-test3', 'ltc-tst'")

    def pubkey_hash(self, network=None) -> str:
        if network == 'btc-test3' or (self.network == 'btc-test3' and network is None):
            return self.public_key.to_hash160()
        elif network == 'ltc-tst' or (self.network == 'ltc-tst' and network is None):
            return self.public_key_LTC.to_hash160()
        else:
            raise ValueError("Network must be one of 'btc-test3', 'ltc-tst'")

    def p2pkh_script_pubkey(self, network=None):
        if network == 'btc-test3' or (self.network == 'btc-test3' and network is None):
            return self.public_key.get_address().to_script_pub_key()
        elif network == 'ltc-tst' or (self.network == 'ltc-tst' and network is None):
            return self.public_key_LTC.get_address().to_script_pub_key()
        else:
            raise ValueError("Network must be one of 'btc-test3', 'ltc-tst'")

    # mutate TX
    def sign_p2pkh(self, tx, input_idx: int, network=None) -> str:
        if network == 'btc-test3' or (self.network == 'btc-test3' and network is None):
            sig = self.secret_key.sign_input(tx, input_idx, self.p2pkh_script_pubkey(network=network))
            script_sig = btcscript.Script([sig, self.public_key.to_hex()])
        elif network == 'ltc-tst' or (self.network == 'ltc-tst' and network is None):
            sig = self.secret_key_LTC.sign_input(tx, input_idx, self.p2pkh_script_pubkey(network=network))
            script_sig = ltcscript.Script([sig, self.public_key_LTC.to_hex()])
        else:
            raise ValueError("Network must be one of 'btc-test3', 'ltc-tst'")

        tx.inputs[input_idx].script_sig = script_sig
        return sig

    def make_segwit_signature(
            self,
            tx,
            input_idx: int,
            utxo: UTXO,
            sighash: int = SIGHASH_ALL,
    ) -> str:
        # assume p2wpkh if not rede
        witness_script = \
            cast(get_network_2(utxo.network)["script"].Script, utxo.redeem_script) \
                if utxo.redeem_script is not None \
                else self.p2pkh_script_pubkey()
        if utxo.network == "btc-test3":
            sig = self.secret_key.sign_segwit_input(
                tx,
                input_idx,
                witness_script,
                utxo.value,
                sighash=sighash,
            )
        else:
            sig = self.secret_key_LTC.sign_segwit_input(
                tx,
                input_idx,
                witness_script,
                utxo.value,
                sighash=sighash,
            )
        return sig

    def audit_transaction(
            self,
            tx,
            utxo: UTXO
    ):
        pass

    def make_second_HTLC_output_tx(
            self,
            utxo: UTXO,
            locktime: int,
            fee: int = DEFAULT_TX_FEE,
            network: str = "btc-tst3"
    ):
        amount_to_send = utxo.value - fee
        txin = utxo.create_tx_in(sequence=0xFFFFFFFE.to_bytes(4, "little"))
        txout = get_network_2(network)["trans"].TxOutput(
            amount_to_send,
            self.p2pkh_script_pubkey(network=network)
        )

        self.second_HTLC_output_tx = new_tx([txin], [txout], locktime=locktime.to_bytes(4, "little"), network=network)

        print("HTLC output transaction made. TXID:", self.second_HTLC_output_tx.get_txid())
        return self.second_HTLC_output_tx

    def commit_second_HTLC_output(self, sig: str, network="btc-test3"):
        self.second_HTLC_output_tx.inputs[0].script_sig = get_network_2(network)["script"].Script([
            sig,
            self.public_key.to_hex() if network == "btc-test3" else self.public_key_LTC.to_hex(),
            'OP_1'
        ])
        self.second_HTLC_output_tx = get_network_2(network)["trans"].Transaction.copy(self.second_HTLC_output_tx)
        self.second_HTLC_output_ser = self.second_HTLC_output_tx.serialize()

    def make_HTLC_output_tx(
            self,
            utxo: UTXO,
            fee: int = DEFAULT_TX_FEE,
            network: str = "btc-tst"
    ):
        amount_to_send = utxo.value - fee
        txin = utxo.create_tx_in()
        txout = get_network_2(utxo.network)["trans"].TxOutput(
            amount_to_send,
            self.p2pkh_script_pubkey(network=network)
        )

        self.HTLC_output_tx = get_network_2(utxo.network)["trans"].Transaction([txin], [txout])

        print("HTLC output transaction made. TXID:", self.HTLC_output_tx.get_txid())
        return self.HTLC_output_tx

    def commit_HTLC_output(self, sig, secret: Secret, network="btc-test3"):
        self.HTLC_output_tx.inputs[0].script_sig = get_network_2(network)["script"].Script([
            sig,
            self.public_key_LTC.to_hex() if network == "ltc-tst" else self.public_key.to_hex(),
            secret.hex(),
            'OP_0'
        ])
        self.HTLC_output_tx = get_network_2(network)["trans"].Transaction.copy(self.HTLC_output_tx)
        self.HTLC_output_ser = self.HTLC_output_tx.serialize()

    async def new_message(self, msg, end=False):
        await notify_new_msg(msg, self.name.lower())
        if not end:
            await wait_until_next_interrupt()
        else:
            await notify_finish()

    async def update_balance(self, msg):
        await notify_update_balance(msg, self.name.lower())

    async def broadcast_transaction(self, raw_transaction, transaction_name, network="btc-test3",
                                    send_to_websocket=False, txid=None):
        response = broadcast_transaction(raw_transaction, network)
        if send_to_websocket:
            if network == 'btc-test3':
                await notify_users(notify_new_trx(new_trx(self.name + " " + transaction_name + " " + txid,
                                                          url='https://blockexplorer.one/btc/testnet/tx/' +
                                                              txid + '?utm_source=cryptoapis.io')))
            elif network == "bcy-tst":
                await notify_users(notify_new_trx(new_trx(self.name + " " + transaction_name + " " + txid,
                                                          url='https://live.blockcypher.com/bcy/tx/' + txid)))
            elif network == "ltc-tst":
                await notify_users(notify_new_trx(new_trx(self.name + " " + transaction_name + " " + txid,
                                                          url='https://tltc.bitaps.com/' + txid)))

        if response.status_code == 201:
            print(self.name, "broadcasts", transaction_name)
        else:
            print(self.name, "failed to broadcast", transaction_name)
            print(response.text)

    def set_websocket(self, connection):
        self.websocket = connection

    def make_defaults_tx(self,
                         prev_utxo: UTXO,
                         locktime: int,
                         network: str = "btc-test3",
                         fee: int = int(DEFAULT_TX_FEE * 2 / 3),
                         ):
        amount_to_send = prev_utxo.value - fee
        txout = get_network_2(network)["trans"].TxOutput(
            amount_to_send,
            self.p2pkh_script_pubkey(network=network)
        )
        txin = prev_utxo.create_tx_in(sequence=0xFFFFFFFE.to_bytes(4, "little"))
        transaction = get_network_2(network)["trans"].Transaction([txin], [txout], has_segwit=True,
                                                                  locktime=locktime.to_bytes(4, "little"))
        self.defaults_tx = transaction

        return self.defaults_tx

    def make_refund_tx(self,
                       locktime: int,
                       funding_utxo: UTXO,
                       network: str = "btc-test3",
                       fee: int = DEFAULT_TX_FEE,
                       ):
        amount_to_send = funding_utxo.value - fee
        txout = get_network_2(network)["trans"].TxOutput(
            amount_to_send,
            self.p2pkh_script_pubkey(network=network)
        )
        txin = funding_utxo.create_tx_in(sequence=0xFFFFFFFE.to_bytes(4, "little"))
        transaction = new_tx([txin], [txout], has_segwit=True, locktime=locktime.to_bytes(4, "little"), network=network)
        self.refund_tx = transaction

        return self.refund_tx

    def commit_refund(self,
                      sig: str,
                      funding_script: hex,
                      network="btc-test3"):
        if network == "btc-test3":
            self.refund_tx.witnesses.append(
                get_network_2(network)["script"].Script([sig, self.public_key.to_hex(),
                                                         self.public_key.to_hex(), funding_script])
            )
        elif network == "ltc-tst":
            self.refund_tx.witnesses.append(
                get_network_2(network)["script"].Script([sig, self.public_key_LTC.to_hex(),
                                                         self.public_key_LTC.to_hex(), funding_script])
            )
        self.refund_tx = get_network_2(network)["trans"].Transaction.copy(self.refund_tx)
        self.refund_ser = self.refund_tx.serialize()
        print(self.name, "refund transaction created.")

    def commit_defaults(self,
                        sig: str,
                        prev_script: hex,
                        network="btc-test3"):
        if network == "btc-test3":
            self.defaults_tx.witnesses.append(
                get_network_2(network)["script"].Script(
                    [sig, self.public_key.to_hex(), self.public_key.to_hex(), prev_script])
            )
        elif network == "ltc-tst":
            self.refund_tx.witnesses.append(
                get_network_2(network)["script"].Script(
                    [sig, self.public_key_LTC.to_hex(), self.public_key_LTC.to_hex(), prev_script])
            )
        self.defaults_tx = get_network_2(network)["trans"].Transaction.copy(self.defaults_tx)
        self.defaults_ser = self.defaults_tx.serialize()
        print(self.name, "created other party's defaults transaction.")
