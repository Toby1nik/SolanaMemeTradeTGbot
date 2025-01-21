from solders.pubkey import Pubkey
from bot.wallet_manager import get_solana_client
from loguru import logger
from typing import Union

def fetch_token_decimals(token_address: str) -> int:
    client = get_solana_client()
    try:
        token_info = client.get_account_info(pubkey=Pubkey.from_string(token_address))
        data = token_info.value.data
        if len(data) < 45:  # At least 45 bytes needed for offset 44
            raise ValueError("Data is too short to extract decimals.")
        return int(data[44])
    except Exception as e:
        logger.error(f"Error fetching token decimals for {token_address}: {e}")
        raise ValueError("Failed to fetch token decimals.")


def get_token_balance_lamports(token_address: str) -> int:
    """
    Get token balance in lamports for a given token address.

    Args:
        token_address (str): Token associated account address.

    Returns:
        int: Token balance in lamports.
    """
    client = get_solana_client()
    try:
        response = client.get_token_account_balance(Pubkey.from_string(token_address))
        return int(response.value.amount)
    except Exception as e:
        print(f"Error getting token balance: {e}")
        return 0
