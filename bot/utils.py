from solders.pubkey import Pubkey
from bot.wallet_manager import get_solana_client

from loguru import logger

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
