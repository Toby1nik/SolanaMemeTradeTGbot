import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from bot.auth_manager import check_authorized_user

router = Router()
logger = logging.getLogger(__name__)

from bot.wallet_manager import (
    generate_private_key,
    save_user_data,
    get_user_data,
    user_exists,
    initialize_user_balances,
    update_user_balances,
    get_user_balances,
    generate_public_key_from_private_key
)


router = Router()
logger = logging.getLogger(__name__)

# Main menu
def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Balance")],
            [KeyboardButton(text="Create private key")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

# /start command handler
@router.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    if not await check_authorized_user(user_id, message):
        return

    if user_exists(user_id):
        user_data = get_user_data(user_id)
        logger.info(f"User {user_id} started the bot. Returning existing public address.")
        await message.answer(
            f"Welcome back! Your public address:\n`{user_data['solana_wallet_address']}`",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
    else:
        logger.info(f"User {user_id} started the bot with no private key.")
        await message.answer("No private key found. Press 'Create private key'.", reply_markup=main_menu())


@router.message(lambda msg: msg.text == "Create private key")
async def create_private_key(message: types.Message):
    user_id = message.from_user.id
    if not await check_authorized_user(user_id, message):
        return

    # Проверяем, существует ли пользователь
    if user_exists(user_id):
        user_data = get_user_data(user_id)
        private_key_str = user_data.get("private_key")

        if private_key_str:
            # Если private_key существует, обновляем solana_wallet_address
            try:
                wallet_address = generate_public_key_from_private_key(private_key_str)
                if user_data["solana_wallet_address"] != str(wallet_address):
                    user_data["solana_wallet_address"] = str(wallet_address)
                    save_user_data(user_id, private_key_str, wallet_address)
                    logger.info(f"User {user_id} updated solana_wallet_address.")
                await message.answer(
                    f"Your private key already exists. Public address:\n`{user_data['solana_wallet_address']}`",
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Failed to update solana_wallet_address for user {user_id}: {e}")
                await message.answer("An error occurred while updating your wallet address. Please try again.")
        else:
            # Если private_key отсутствует, создаем новый
            private_key, public_key = generate_private_key()
            save_user_data(user_id, private_key, public_key)
            logger.info(f"User {user_id} created a new private key.")
            await message.answer(
                f"The private key has been created and saved.\n\nYour public key:\n`{public_key}`",
                parse_mode="Markdown",
            )
    else:
        # Если пользователь не существует, создаем нового
        private_key, public_key = generate_private_key()
        save_user_data(user_id, private_key, public_key)
        logger.info(f"User {user_id} created a new private key.")
        await message.answer(
            f"The private key has been created and saved.\n\nYour public key:\n`{public_key}`",
            parse_mode="Markdown",
        )


@router.message(lambda msg: msg.text == "💰 Balance")
async def balance_command(message: types.Message):
    user_id = message.from_user.id
    if not await check_authorized_user(user_id, message):
        return

    # Check if the user exists in users.json
    if not user_exists(user_id):
        logger.info(f"User {user_id} requested balance without a private key.")
        await message.answer("No private key found. Please create it first from the menu.")
        return

    # Get user data and ensure balances are initialized
    user_data = get_user_data(user_id)
    initialize_user_balances(user_id, user_data["solana_wallet_address"])

    # Update balances for the user
    update_user_balances(user_id, user_data["solana_wallet_address"])

    # Retrieve updated balances
    balances = get_user_balances(user_id)

    # Generate response
    if balances:
        response = "Your balances:\n\n"
        for token in balances:
            balance_in_decimal = token["balance"] / (10 ** token["decimals"])
            response += f"{token['ticker']}: {balance_in_decimal:.6f}\n`{token['contract_address']}`\n\n"
        await message.answer(response,
            parse_mode="Markdown")
    else:
        await message.answer("No balances found for your account.")
