import json
import logging

logger = logging.getLogger(__name__)

def is_allowed_user(user_id: int) -> bool:
    """
    Check if the user is in the allowed list.
    """
    with open("data/settings.json", "r") as f:
        config = json.load(f)
    return user_id in config["allowed_users"]

async def check_authorized_user(user_id: int, message):
    """
    Verify if a user is authorized to use the bot.
    If not authorized, log the attempt and notify the user.

    :param user_id: Telegram user ID
    :param message: Telegram message object
    :return: True if authorized, False otherwise
    """
    if not is_allowed_user(user_id):
        logger.warning(f"Unauthorized access attempt by user {user_id}")
        await message.answer("You are not authorized to use this bot.")
        return False
    return True
