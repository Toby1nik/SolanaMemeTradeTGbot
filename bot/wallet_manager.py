import json
import logging
from solders.pubkey import Pubkey
from solana.rpc.api import Client
from solders.keypair import Keypair
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import get_associated_token_address

logger = logging.getLogger(__name__)

USERS_FILE = "data/users.json"
BALANCES_FILE = "data/balances.json"
SETTINGS_FILE = "data/settings.json"


# Generate a private key and public address
def generate_private_key():
    """
    Generates a new private key and public address using solders.
    :return: (private_key, public_key)
    """
    account = Keypair()
    address = account.pubkey()
    priv_key: Keypair = account.from_json(account.to_json())

    return  priv_key, address

def save_user_data(user_id, private_key, public_key):
    """
    Saves user data to a JSON file.
    :param user_id: User ID
    :param private_key: Private key in Base58 format
    :param public_key: Public key as a string
    """
    try:
        with open(USERS_FILE, "r") as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        users = {}

    # Обновляем или создаем запись для пользователя
    users[str(user_id)] = {
        "private_key": str(private_key),
        "solana_wallet_address": str(public_key),
    }

    # Сохраняем обновленные данные в файл
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

# Get user data from users.json
def get_user_data(user_id: int) -> dict:
    """
    Retrieve user data (private key and public address) from the JSON file.
    :param user_id: Telegram user ID
    :return: Dictionary with private_key and solana_wallet_address or an empty dict if not found.
    """
    try:
        with open(USERS_FILE, "r") as f:
            users = json.load(f)
        return users.get(str(user_id), {})
    except FileNotFoundError:
        return {}

# Check if a user exists in users.json
def user_exists(user_id: int) -> bool:
    """
    Check if a user has data stored in the JSON file.
    :param user_id: Telegram user ID
    :return: True if user exists, False otherwise.
    """
    user_data = get_user_data(user_id)
    return bool(user_data)


# Load Solana RPC URL
def get_solana_client():
    with open(SETTINGS_FILE, "r") as f:
        settings = json.load(f)
    return Client(endpoint=settings["solana_rpc_url"])

# Initialize balances for a user
def initialize_user_balances(user_id: int, public_key: str):
    try:
        with open(BALANCES_FILE, "r") as f:
            balances = json.load(f)
    except FileNotFoundError:
        balances = {}

    # Add user to balances.json if not present
    if str(user_id) not in balances:
        balances[str(user_id)] = {
            "tokens": [
                {
                    "ticker": "SOL",
                    "contract_address": "",
                    "associated_token_address": public_key,
                    "balance": 0,
                    "decimals": 9,
                    "program_id": ""
                },
                {
                    "ticker": "USDC",
                    "contract_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    "associated_token_address": "",
                    "balance": 0,
                    "decimals": 6,
                    "program_id": str(TOKEN_PROGRAM_ID)
                },
                {
                    "ticker": "USDT",
                    "contract_address": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
                    "associated_token_address": "",
                    "balance": 0,
                    "decimals": 6,
                    "program_id": str(TOKEN_PROGRAM_ID)
                }
            ]
        }
        with open(BALANCES_FILE, "w") as f:
            json.dump(balances, f, indent=4)
        logger.info(f"Initialized balances for user {user_id}")
    else:
        logger.info(f"Balances for user {user_id} already initialized.")

# Get SOL balance
def get_sol_balance(public_key: str) -> float:
    client = get_solana_client()
    account_info = client.get_account_info(Pubkey.from_string(public_key))
    if account_info.value is not None:
        # decimals = 9  # Fixed decimals for SOL
        lamports = account_info.value.lamports
        return lamports
    return 0

# Update user token balances
def update_user_balances(user_id: int, wallet_address: str):
    client = get_solana_client()
    try:
        with open(BALANCES_FILE, "r") as f:
            balances = json.load(f)
    except FileNotFoundError:
        logger.error("Balances file not found.")
        return

    # Get the user's token balances
    user_balances = balances.get(str(user_id), {}).get("tokens", [])
    for token in user_balances:
        if token["ticker"] == "SOL":
            # Update SOL balance
            token["balance"] = get_sol_balance(wallet_address)
        else:
            # Get associated token address
            associated_token_address = get_associated_token_address(
                owner=Pubkey.from_string(wallet_address),
                mint=Pubkey.from_string(token["contract_address"])
            )
            try:
                token_info = client.get_token_account_balance(associated_token_address)
                if hasattr(token_info, "value") and token_info.value is not None:
                    token["balance"] = int(token_info.value.amount)  # Store as raw lamports
                else:
                    logger.warning(f"No balance data for {token['ticker']}.")
                token["associated_token_address"] = str(associated_token_address)
            except Exception as e:
                logger.error(f"Failed to fetch balance for {token['ticker']}: {e}")

    # Save updated balances
    balances[str(user_id)]["tokens"] = user_balances
    with open(BALANCES_FILE, "w") as f:
        json.dump(balances, f, indent=4)
    logger.info(f"Updated balances for user {user_id}")

# Get user balances
def get_user_balances(user_id: int):
    try:
        with open(BALANCES_FILE, "r") as f:
            balances = json.load(f)
        return balances.get(str(user_id), {}).get("tokens", [])
    except FileNotFoundError:
        return []


def generate_public_key_from_private_key(private_key_str: str) -> Pubkey:
    """
    Generates a public key from a private key string (Base58 format).
    :param private_key_str: Private key in Base58 format
    :return: Corresponding public key (Pubkey object)
    """
    try:
        # Key pair from Base58 (str)
        private_key = Keypair.from_base58_string(private_key_str)
        return private_key.pubkey()
    except Exception as e:
        logger.error(f"Failed to generate public key from private key: {e}")
        raise