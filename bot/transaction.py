import base64
import json
import requests
from typing import Any, Dict, Optional, Union
from solders.keypair import Keypair
from solders.message import to_bytes_versioned
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts
from bot.utils import get_token_balance_lamports
from bot.wallet_manager import get_user_data, get_solana_client
from solders.signature import Signature
from solders.compute_budget import set_compute_unit_limit
from solders.instruction import Instruction, CompiledInstruction
from time import time, sleep

SOL = "So11111111111111111111111111111111111111112"

is_confirming = False
class TransactionManager:
    @staticmethod

    def confirm_txn(txn_sig: Union[str, Signature], timeout: int = 30, sleep_seconds: float = 2.0) -> bool:
        client = get_solana_client()
        global is_confirming
        if is_confirming:
            print("confirm_txn already running, skipping this call.")
            return False
        is_confirming = True
        try:
            if isinstance(txn_sig, str):
                txn_sig = Signature.from_string(txn_sig)

            timeout_time = time() + timeout
            while time() < timeout_time:
                response = client.confirm_transaction(txn_sig, commitment="finalized")
                if response.value:
                    return True
                sleep(sleep_seconds)
            return False
        except Exception as e:
            print(f"Error confirming transaction: {e}")
            return False

    @staticmethod
    def get_quote(input_mint: str, output_mint: str, amount: int, slippage_bps: int) -> Optional[Dict[str, Any]]:
        """
        Fetch price quote from Jupiter API.
        """
        try:
            url = "https://quote-api.jup.ag/v6/quote"
            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': amount,
                'slippageBps': slippage_bps,
                'onlyDirectRoutes': 'true'
            }
            headers = {'Accept': 'application/json'}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error in get_quote: {e}")
            return None

    @staticmethod
    def get_swap(user_public_key: str, quote_response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch swap transaction from Jupiter API.
        """
        try:
            url = "https://quote-api.jup.ag/v6/swap"
            payload = json.dumps({
                "userPublicKey": user_public_key,
                "wrapAndUnwrapSol": True,
                "useSharedAccounts": True,
                "quoteResponse": quote_response
            })
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error in get_swap: {e}")
            return None

    @staticmethod
    def swap(user_id: str, input_mint: str, output_mint: str, amount_lamports: int, slippage_bps: int) -> bool:
        """
        Perform the swap transaction with custom compute budget instructions.
        """
        client = get_solana_client()
        user_data = get_user_data(user_id)

        pub_key_str = user_data["solana_wallet_address"]
        private_key = user_data["private_key"]
        payer_keypair = Keypair.from_base58_string(private_key)

        # Fetch quote
        print("Fetching quote...")
        quote_response = TransactionManager.get_quote(input_mint, output_mint, amount_lamports, slippage_bps)
        if not quote_response:
            print("Failed to fetch quote.")
            return False

        # Fetch swap transaction
        print("Fetching swap transaction...")
        swap_transaction = TransactionManager.get_swap(pub_key_str, quote_response)
        if not swap_transaction:
            print("Failed to fetch swap transaction.")
            return False

        # Deserialize transaction
        print("Deserializing transaction...")
        raw_transaction = VersionedTransaction.from_bytes(
            base64.b64decode(swap_transaction['swapTransaction'])
        )

        # Add Compute Budget instructions
        print("Adding Compute Budget instructions...")
        add_compute_budget_instructions(raw_transaction.message)

        # Sign transaction
        signature = payer_keypair.sign_message(to_bytes_versioned(raw_transaction.message))
        signed_txn = VersionedTransaction.populate(raw_transaction.message, [signature])

        opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)

        try:
            # Send transaction
            print("Sending transaction...")
            txn_sig = client.send_raw_transaction(
                txn=bytes(signed_txn), opts=opts
            ).value
            print("Transaction Signature:", txn_sig)

            print("Confirming transaction...")
            confirmed = TransactionManager.confirm_txn(txn_sig, timeout=60, sleep_seconds=5)
            print("Transaction confirmed:", confirmed)

            return confirmed
        except Exception as e:
            print(f"Failed to send transaction: {e}")
            return False

    @staticmethod
    def buy(user_id: str, token_address: str, sol_in: Union[int, float], slippage: int = 5) -> bool:
        """
        Buy tokens using SOL.
        """
        amount_lamports = int(sol_in * 1e9)
        slippage_bps = slippage * 100
        return TransactionManager.swap(user_id, SOL, token_address, amount_lamports, slippage_bps)

    @staticmethod
    def sell(user_id: str, token_address: str, percentage: int = 100, slippage: int = 5) -> bool:
        """
        Sell tokens for SOL.
        """
        if not (1 <= percentage <= 100):
            print("Percentage must be between 1 and 100.")
            return False

        token_balance = get_token_balance_lamports(token_address)
        print("Token Balance:", token_balance)

        if token_balance == 0:
            print("No token balance available to sell.")
            return False

        sell_amount = int(token_balance * (percentage / 100))
        slippage_bps = slippage * 100

        return TransactionManager.swap(user_id, token_address, SOL, sell_amount, slippage_bps)

from solders.pubkey import Pubkey

def add_compute_budget_instructions(txn_message):
    # Compute Budget Program ID
    compute_budget_program_id = Pubkey.from_string("ComputeBudget111111111111111111111111111111")

    # Instruction to set Compute Unit Limit (e.g., 1,400,000)
    compute_unit_limit_instruction = Instruction(
        program_id=compute_budget_program_id,
        accounts=[],
        data=bytes([0]) + (1_800_000).to_bytes(4, "little")  # Instruction 0: Set Compute Unit Limit
    )

    # Instruction to set Compute Unit Price (e.g., 71,428 micro-lamports)
    compute_unit_price_instruction = Instruction(
        program_id=compute_budget_program_id,
        accounts=[],
        data=bytes([3]) + (91_428).to_bytes(8, "little")  # Instruction 3: Set Compute Unit Price
    )

    # Add the instructions at the beginning of the transaction message
    txn_message.instructions.insert(0, compute_unit_limit_instruction)
    txn_message.instructions.insert(1, compute_unit_price_instruction)

