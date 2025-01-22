import base64
import logging
import requests
from time import time, sleep
from solders.keypair import Keypair
from solana.rpc.types import TxOpts
from typing import Any, Dict, Optional
from solders.message import to_bytes_versioned
from solders.transaction import VersionedTransaction
from solders.transaction_status import TransactionConfirmationStatus
from solana.rpc.commitment import Processed, Confirmed, Finalized
from bot.wallet_manager import get_user_data, get_solana_client
from bot.utils import get_token_balance_lamports, fetch_token_decimals

logger = logging.getLogger(__name__)
SOL = "So11111111111111111111111111111111111111112"

class TransactionManager:
    @staticmethod
    def confirm_txn(txn_sig: str, timeout: int = 90, sleep_seconds: float = 2.0) -> bool:
        client = get_solana_client()
        try:
            timeout_time = time() + timeout
            while time() < timeout_time:
                response = client.get_signature_statuses([txn_sig])
                # print(response)
                if response.value:  # Проверяем, что есть значение
                    txn_status = response.value[0]  # Получаем первый статус
                    if txn_status:  # Проверяем, что статус существует
                        # Достаем confirmation_status
                        confirmation_status = txn_status.confirmation_status
                        # print(confirmation_status.Confirmed)
                        # print(type(confirmation_status))
                        if confirmation_status == TransactionConfirmationStatus.Finalized:
                            return True
                sleep(sleep_seconds)
            return False  # Возвращаем False, если таймаут истёк
        except Exception as e:
            print(f"Error confirming transaction: {e}")
            return False

    @staticmethod
    def get_quote(input_mint: str, output_mint: str, amount: int, pub_key_str: str) -> Optional[Dict[str, Any]]:
        try:
            url = "https://quote-proxy.jup.ag/quote"
            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': amount,
                'dynamicSlippage': 'true',
                'swapMode': 'ExactIn',
                'onlyDirectRoutes': 'false',
                'asLegacyTransaction': 'false',
                'maxAccounts': '64',
                'minimizeSlippage': 'false',
                'taker': pub_key_str,
            }
            headers = {"Accept": "application/json"}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error in get_quote: {e}")
            return None

    @staticmethod
    def get_swap(user_wallet: str, quote_response: dict) -> Optional[Dict[str, Any]]:
        try:
            url = "https://quote-proxy.jup.ag/swap"
            params = {
                'swapType': 'aggregator',
            }
            payload = {
                "quoteResponse": quote_response,
                "userPublicKey": user_wallet,
                "wrapAndUnwrapSol": True,
                'dynamicComputeUnitLimit': True,
                'correctLastValidBlockHeight': True,
                'asLegacyTransaction': False,
                'allowOptimizedWrappedSolTokenAccount': True,
                'addConsensusAccount': False,
                'prioritizationFeeLamports': {
                    'priorityLevelWithMaxLamports': {
                        'maxLamports': 50000000,
                        # 'maxLamports': 5000000,
                        'global': False,
                        # 'priorityLevel': 'High',
                        'priorityLevel': 'veryHigh',
                    },
                },
                'blockhashSlotsToExpiry': 32,
                'dynamicSlippage': True,
            }
            response = requests.post(url, json=payload, params=params)
            response.raise_for_status()
            # print(response.json())
            return response.json()
        except requests.RequestException as e:
            print(f"Error in get_swap: {e}")
            return None

    # @staticmethod
    # def add_compute_budget_instructions(txn_message):
    #     compute_budget_program_id = Pubkey.from_string("ComputeBudget111111111111111111111111111111")
    #
    #     # Проверяем, есть ли уже инструкции Compute Budget
    #     existing_compute_budget_instructions = [
    #         instr for instr in txn_message.instructions
    #         if instr.program_id == compute_budget_program_id
    #     ]
    #     if existing_compute_budget_instructions:
    #         print("Compute Budget instructions already present. Skipping addition.")
    #         return
    #
    #     compute_unit_limit_instruction = Instruction(
    #         program_id=compute_budget_program_id,
    #         accounts=[],
    #         data=bytes([0]) + (1_800_000).to_bytes(4, "little")
    #     )
    #
    #     compute_unit_price_instruction = Instruction(
    #         program_id=compute_budget_program_id,
    #         accounts=[],
    #         data=bytes([3]) + (50_000).to_bytes(8, "little")
    #     )
    #
    #     txn_message.instructions.insert(0, compute_unit_limit_instruction)
    #     txn_message.instructions.insert(1, compute_unit_price_instruction)

    @staticmethod
    def swap(user_id: str, input_mint: str, output_mint: str, amount_lamports: int, slippage_bps: int):
        client = get_solana_client()
        user_data = get_user_data(user_id)
        pub_key_str = user_data["solana_wallet_address"]
        payer_keypair = Keypair.from_base58_string(user_data["private_key"])

        # print("Fetching quote JupiteAPI...")
        logger.info(f"[{user_id}] {pub_key_str} | start getting quote via JupiteAPI...")
        quote_response = TransactionManager.get_quote(input_mint, output_mint, amount_lamports, pub_key_str)
        if not quote_response:
            logger.error(f"[{user_id}] {pub_key_str} | Failed get quote via JupiteAPI...")
            return False

        logger.info(f"[{user_id}] {pub_key_str} | start getting transaction via JupiteAPI...")
        swap_transaction = TransactionManager.get_swap(pub_key_str, quote_response)
        if not swap_transaction:
            logger.error(f"[{user_id}] {pub_key_str} | Failed getting transaction via JupiteAPI...")
            return False

        logger.info(f'[{user_id}] {pub_key_str} | TODO SYBMOLS WHAT SWAP TO WHAT')

        logger.info(f"[{user_id}] {pub_key_str} | make deserializing transaction from JupiterAPI")
        raw_transaction = VersionedTransaction.from_bytes(
            base64.b64decode(swap_transaction['swapTransaction'])
        )
        # print("Adding Compute Budget instructions...")
        # TransactionManager.add_compute_budget_instructions(raw_transaction.message)

        signature = payer_keypair.sign_message(to_bytes_versioned(raw_transaction.message))
        signed_txn = VersionedTransaction.populate(raw_transaction.message, [signature])

        opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)

        try:
            logger.info(f"[{user_id}] {pub_key_str} | Sending transaction")
            tx_hash = client.send_raw_transaction(
                txn=bytes(signed_txn),
                opts=opts).value

            logger.info(f"[{user_id}] {pub_key_str} | Confirming transaction... | TxHash: {tx_hash}")
            confirmed = TransactionManager.confirm_txn(tx_hash, timeout=90, sleep_seconds=3)
            if confirmed :
                logger.info(f"[{user_id}] {pub_key_str} | Success send transaction | TxHash: {tx_hash}")
                print("Transaction confirmed:", confirmed)
                return confirmed, tx_hash
            else:
                logger.error(f"[{user_id}] {pub_key_str} | Failed send transaction... | TxHash: {tx_hash}")
                return confirmed, tx_hash

        except Exception as e:
            print(f"Failed to send transaction: {e}")
            return False

    @staticmethod
    def buy(user_id: str, token_address: str, sol_amount: float, slippage: int = 1) -> bool:
        amount_lamports = int(sol_amount * 1e9)
        slippage_bps = slippage * 100  # 100 is 1%
        return TransactionManager.swap(user_id, SOL, token_address, amount_lamports, slippage_bps)

    @staticmethod
    def sell(user_id: str, token_address: str, percentage: int = 100, slippage: int = 5) -> bool:
        if not (1 <= percentage <= 100):
            print("Percentage must be between 1 and 100.")
            return False

        token_balance = get_token_balance_lamports(token_address)
        if token_balance == 0:
            print("No token balance available to sell.")
            return False

        sell_amount = int(token_balance * (percentage / 100))
        slippage_bps = slippage * 100

        return TransactionManager.swap(user_id, token_address, SOL, sell_amount, slippage_bps)

    @staticmethod
    def fetch_decimals_safe(token_address: str) -> int:
        try:
            return int(fetch_token_decimals(token_address))
        except ValueError:
            print(f"Invalid decimal value for token {token_address}, defaulting to 0.")
            return 0

    @staticmethod
    def calculate_output_amount(estimated_amount: Dict[str, Any], token_address: str) -> float:
        decimals = TransactionManager.fetch_decimals_safe(token_address)
        try:
            return estimated_amount["outAmount"] / (10 ** decimals)
        except (KeyError, TypeError) as e:
            print(f"Error calculating output amount: {e}")
            return 0.0
