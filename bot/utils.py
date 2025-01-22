from solders.pubkey import Pubkey
from bot.wallet_manager import get_solana_client, get_user_data
from solders.token.associated import get_associated_token_address
from solders.rpc.errors import InvalidParamsMessage
from loguru import logger
import requests
import json

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


def get_token_balance_lamports(user_id: int, token_address: str) -> int:
    """
    Get token balance in lamports for a given token address.

    Args:
        token_address (str): Token associated account address.

    Returns:
        int: Token balance in lamports.

    """

    user_data = get_user_data(user_id)
    pub_key_str = user_data["solana_wallet_address"]

    client = get_solana_client()
    try:
        token_program_id = (client.get_account_info(Pubkey.from_string(token_address))).value.owner
        associated_token = get_associated_token_address(
            wallet_address=Pubkey.from_string(pub_key_str),
            token_mint_address=Pubkey.from_string(token_address),
            token_program_id=token_program_id
        )
        response = client.get_token_account_balance(associated_token)
        if isinstance(response, InvalidParamsMessage):
            return 0
        return int(response.value.amount)
    except Exception as e:
        print(f"Unknown error check fun get_token_balance_lamports : {e}")
        return 0


def get_token_price_from_coingecko(token: str) -> float:
    # Сопоставление токенов с их идентификаторами на CoinGecko
    token_id = {
        "SOL": 'solana',
        "USDC": 'usd-coin',
        "USDT": 'tether',
        "tETH": 'ethereum'
    }

    # Для USDC и USDT возвращаем фиксированную цену 1.0
    if token in ["USDC", "USDT"]:
        return 1.0

    # Формируем URL для запроса
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={token_id.get(token)}&vs_currencies=usd"

    try:
        # Выполняем HTTP GET-запрос
        response = requests.get(url)

        # Проверяем успешность запроса
        if response.status_code != 200:
            raise ValueError(f"Request error: {response.status_code} - {response.text}")

        # Декодируем JSON-ответ
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise ValueError(f"JSON decode error: {response.text}")

        # Извлекаем цену токена
        return data.get(token_id[token], {}).get('usd', None)

    except Exception as e:
        raise RuntimeError(f"Error fetching token price: {str(e)}") from e


def get_sol_balance(user_id: int) -> int:
    user_data = get_user_data(user_id)
    client = get_solana_client()
    return (client.get_account_info(Pubkey.from_string(user_data["solana_wallet_address"]))).value.lamports
