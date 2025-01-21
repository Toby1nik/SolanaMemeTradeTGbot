import base64
import json
import requests
from typing import Any, Dict, Optional, Union
from solders.keypair import Keypair
from solders.message import to_bytes_versioned
from solders.transaction import VersionedTransaction
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.instruction import Instruction
from solders.signature import Signature
from solders.pubkey import Pubkey
from solana.rpc.api import Client
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts
from time import time, sleep
from bot.wallet_manager import get_user_data, get_solana_client
from bot.utils import get_token_balance_lamports, fetch_token_decimals

SOL = "So11111111111111111111111111111111111111112"

class TransactionManager:
    @staticmethod
    def confirm_txn(txn_sig: str, timeout: int = 90, sleep_seconds: float = 2.0) -> bool:
        client = get_solana_client()
        try:
            timeout_time = time() + timeout
            while time() < timeout_time:
                response = client.get_signature_statuses([txn_sig]).value
                if response and response[0] and response[0].confirmation_status in ["finalized", "confirmed"]:
                    return True
                sleep(sleep_seconds)
            return False
        except Exception as e:
            print(f"Error confirming transaction: {e}")
            return False

    @staticmethod
    def get_quote(input_mint: str, output_mint: str, amount: int, slippage_bps: int) -> Optional[Dict[str, Any]]:
        try:
            url = "https://quote-api.jup.ag/v6/quote"
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": amount,
                "slippageBps": slippage_bps,
                "directRoutesOnly": False,  # Updated to match Jupiter's expectations
            }
            headers = {"Accept": "application/json"}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error in get_quote: {e}")
            return None

    @staticmethod
    def get_swap(user_wallet: str, quote_response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            url = "https://quote-api.jup.ag/v6/swap"
            payload = {
                "userPublicKey": user_wallet,
                "wrapAndUnwrapSol": True,
                "quoteResponse": quote_response
            }
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error in get_swap: {e}")
            return None

    @staticmethod
    def add_compute_budget_instructions(txn_message):
        compute_budget_program_id = Pubkey.from_string("ComputeBudget111111111111111111111111111111")

        # Проверяем, есть ли уже инструкции Compute Budget
        existing_compute_budget_instructions = [
            instr for instr in txn_message.instructions
            if instr.program_id == compute_budget_program_id
        ]
        if existing_compute_budget_instructions:
            print("Compute Budget instructions already present. Skipping addition.")
            return

        compute_unit_limit_instruction = Instruction(
            program_id=compute_budget_program_id,
            accounts=[],
            data=bytes([0]) + (1_800_000).to_bytes(4, "little")
        )

        compute_unit_price_instruction = Instruction(
            program_id=compute_budget_program_id,
            accounts=[],
            data=bytes([3]) + (50_000).to_bytes(8, "little")
        )

        txn_message.instructions.insert(0, compute_unit_limit_instruction)
        txn_message.instructions.insert(1, compute_unit_price_instruction)

    @staticmethod
    def swap(user_id: str, input_mint: str, output_mint: str, amount_lamports: int, slippage_bps: int) -> bool:
        client = get_solana_client()
        user_data = get_user_data(user_id)
        pub_key_str = user_data["solana_wallet_address"]
        payer_keypair = Keypair.from_base58_string(user_data["private_key"])

        print("Fetching quote...")
        quote_response = TransactionManager.get_quote(input_mint, output_mint, amount_lamports, slippage_bps)
        if not quote_response:
            print("Failed to fetch quote.")
            return False

        print("Fetching swap transaction...")
        swap_transaction = TransactionManager.get_swap(pub_key_str, quote_response)
        if not swap_transaction:
            print("Failed to fetch swap transaction.")
            return False

        print("Deserializing transaction...")
        raw_transaction = VersionedTransaction.from_bytes(
            base64.b64decode(swap_transaction['swapTransaction'])
        )

        print("Adding Compute Budget instructions...")
        TransactionManager.add_compute_budget_instructions(raw_transaction.message)

        signature = payer_keypair.sign_message(to_bytes_versioned(raw_transaction.message))
        signed_txn = VersionedTransaction.populate(raw_transaction.message, [signature])

        opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)

        try:
            print("Sending transaction...")
            txn_sig = client.send_raw_transaction(bytes(signed_txn), opts=opts).value
            print("Transaction Signature:", txn_sig)

            print("Confirming transaction...")
            confirmed = TransactionManager.confirm_txn(txn_sig, timeout=60, sleep_seconds=5)
            print("Transaction confirmed:", confirmed)

            return confirmed
        except Exception as e:
            print(f"Failed to send transaction: {e}")
            return False

    @staticmethod
    def buy(user_id: str, token_address: str, sol_amount: float, slippage: int = 5) -> bool:
        amount_lamports = int(sol_amount * 1e9)
        slippage_bps = slippage * 100
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
