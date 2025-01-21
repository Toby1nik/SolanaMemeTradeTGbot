import json
import logging

logger = logging.getLogger(__name__)

def get_token_decimals(user_id, token_address, balances_file="data/balances.json"):
    """
    Get the decimals for a given token for a specific user from the balances.json file.

    Args:
        user_id (str): The user's ID (e.g., Telegram ID).
        token_address (str): The token's contract address.
        balances_file (str): Path to the balances.json file.

    Returns:
        int: The decimals for the token as a power of 10.

    Raises:
        ValueError: If the token or user is not found or there is an error reading the file.
    """
    try:
        with open(balances_file, "r") as f:
            balances = json.load(f)

        # Check if user exists
        user_data = balances.get(str(user_id))
        if not user_data or "tokens" not in user_data:
            raise ValueError(f"User ID {user_id} not found in {balances_file}")

        # Search for the token in the user's tokens list
        token_data = next(
            (token for token in user_data["tokens"] if token["contract_address"] == token_address),
            None
        )
        if not token_data:
            raise ValueError(f"Token {token_address} not found for user {user_id} in {balances_file}")

        # Return decimals as a power of 10
        return 10 ** token_data["decimals"]

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from {balances_file}: {e}")
        raise ValueError("Invalid JSON format in balances file.")
    except Exception as e:
        logger.error(f"Error reading decimals for token {token_address} for user {user_id}: {e}")
        raise ValueError("Failed to fetch token decimals.")
