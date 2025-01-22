import logging
from aiogram import Router, types
from aiogram.filters import Command
from bot.auth_manager import check_authorized_user
from bot.utils import fetch_token_decimals
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import StateFilter
from bot.utils import get_token_balance_lamports, get_token_price_from_coingecko
from bot.states import BuyState, SellState
from bot.transaction import TransactionManager

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

# Main menu
def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Balance")],
            [KeyboardButton(text="Create private key")],
            [KeyboardButton(text="Buy")],
            [KeyboardButton(text="Sell")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

# ----------------- /start command handler  -----------------
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

# ----------------- Button: Create private key -----------------
@router.message(lambda msg: msg.text == "Create private key")
async def create_private_key(message: types.Message):
    user_id = message.from_user.id
    if not await check_authorized_user(user_id, message):
        return

    if user_exists(user_id):
        user_data = get_user_data(user_id)
        private_key_str = user_data.get("private_key")

        if private_key_str:
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
            private_key, public_key = generate_private_key()
            save_user_data(user_id, private_key, public_key)
            logger.info(f"User {user_id} created a new private key.")
            await message.answer(
                f"The private key has been created and saved.\n\nYour public key:\n`{public_key}`",
                parse_mode="Markdown",
            )
    else:
        private_key, public_key = generate_private_key()
        save_user_data(user_id, private_key, public_key)
        logger.info(f"User {user_id} created a new private key.")
        await message.answer(
            f"The private key has been created and saved.\n\nYour public key:\n`{public_key}`",
            parse_mode="Markdown",
        )

# ----------------- Button: 💰 Balance -----------------
@router.message(lambda msg: msg.text == "💰 Balance")
async def balance_command(message: types.Message):
    user_id = message.from_user.id
    if not await check_authorized_user(user_id, message):
        return

    if not user_exists(user_id):
        logger.info(f"User {user_id} requested balance without a private key.")
        await message.answer("No private key found. Please create it first from the menu.")
        return

    user_data = get_user_data(user_id)
    initialize_user_balances(user_id, user_data["solana_wallet_address"])
    update_user_balances(user_id, user_data["solana_wallet_address"])
    balances = get_user_balances(user_id)

    if balances:
        response = "Your balances:\n\n"
        for token in balances:
            balance_in_decimal = token["balance"] / (10 ** token["decimals"])
            response += f"{token['ticker']}: {balance_in_decimal:.6f}\n`{token['contract_address']}`\n\n"
        await message.answer(response, parse_mode="Markdown")
    else:
        await message.answer("No balances found for your account.")

# ----------------- Menu: BUY -----------------
def buy_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Back")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

@router.message(lambda msg: msg.text == "Buy")
async def start_buy_process(message: Message, state: FSMContext):
    await message.answer("Please enter the token address or click 'Back' to return.", reply_markup=buy_menu())
    await state.set_state(BuyState.waiting_for_token_address)

@router.message(lambda msg: msg.text == "Back", StateFilter(BuyState.waiting_for_token_address))
@router.message(lambda msg: msg.text == "Back", StateFilter(BuyState.waiting_for_sol_amount))
@router.message(lambda msg: msg.text == "Back", StateFilter(BuyState.waiting_for_confirmation))  # Добавлено!

@router.message(lambda msg: msg.text == "Back", StateFilter(SellState.waiting_for_token_address))
@router.message(lambda msg: msg.text == "Back", StateFilter(SellState.waiting_for_token_amount))
@router.message(lambda msg: msg.text == "Back", StateFilter(SellState.waiting_for_confirmation))
async def back_to_main_menu(message: Message, state: FSMContext):
    current_state = await state.get_state()
    logger.info(f"[DEBUG] User {message.from_user.id} pressed 'Back'. Current state: {current_state}")
    # print(f"[DEBUG] User {message.from_user.id} pressed 'Back'. Current state: {current_state}")

    await state.clear()
    logger.info(f"[DEBUG] State cleared for user {message.from_user.id}.")
    # print(f"[DEBUG] State cleared for user {message.from_user.id}.")
    await message.answer("You are back to the main menu.", reply_markup=main_menu())

@router.message(StateFilter(BuyState.waiting_for_token_address))
async def handle_token_address(message: Message, state: FSMContext):
    token_address = message.text.strip()
    if len(token_address) != 44:
        await message.answer("Invalid token address. Please enter a valid address.")
        return
    await state.update_data(token_address=token_address)
    await message.answer(
        "Token address saved. Now enter the SOL amount you want to sell or click 'Back' to change the address.",
        reply_markup=buy_menu(),
    )
    await state.set_state(BuyState.waiting_for_sol_amount)

@router.message(StateFilter(BuyState.waiting_for_sol_amount))
async def handle_sol_amount(message: Message, state: FSMContext):
    sol_amount_text = message.text.replace(",", ".").strip()
    try:
        if sol_amount_text.startswith("0") and not "." in sol_amount_text:
            sol_amount_text = f"0.{sol_amount_text[1:]}"
            logger.info(f"Adjusted sol_amount_text with leading zero: {sol_amount_text}")

            # Convert to float
        sol_amount = float(sol_amount_text)
        logger.info(f"Converted sol_amount: {sol_amount}")

        if sol_amount <= 0:
            await message.answer("Amount must be positive.")
            return

        await state.update_data(sol_amount=sol_amount)
        data = await state.get_data()
        token_address = data.get("token_address")

        user_data = get_user_data(message.from_user.id)
        estimated_amount = TransactionManager.get_quote(
            input_mint="So11111111111111111111111111111111111111112",
            output_mint=token_address,
            amount=int(sol_amount * 1e9),
            pub_key_str=user_data['solana_wallet_address']
        )

        if not estimated_amount:
            await message.answer("Failed to fetch a quote. Please try again later.")
            return

        await state.update_data(token_out_amount=int(estimated_amount["outAmount"]))
        output_amount = int(estimated_amount["outAmount"]) / (10 ** int(fetch_token_decimals(token_address)))

        await message.answer(
            f"You want to sell {sol_amount} SOL for the token:\n`{token_address}`\n"
            f"Approximate result: {output_amount} tokens.\n\n"
            "Click 'Back' to change the amount or 'Confirm' to proceed.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Back")], [KeyboardButton(text="Confirm and send transaction")]],
                resize_keyboard=True,
                one_time_keyboard=False,
            ),
            parse_mode="Markdown"
        )

        await state.set_state(BuyState.waiting_for_confirmation)

    except ValueError:
        await message.answer("Please enter a valid number (e.g., 0.123).")

@router.message(lambda msg: msg.text == "Confirm and send transaction", StateFilter(BuyState.waiting_for_confirmation))
async def confirm_transaction(message: Message, state: FSMContext):
    current_state = await state.get_state()
    logger.info(f"[DEBUG] Current state before confirmation: {current_state}")
    try:
        data = await state.get_data()
        token_address = data.get("token_address")
        sol_amount = data.get("sol_amount")
        amount_out_token = data.get('token_out_amount')

        if not token_address or sol_amount is None:
            await message.answer("Transaction data is incomplete. Please start again.")
            await state.clear()
            await message.answer("You are back to the main menu.", reply_markup=main_menu())
            return

        await message.answer("Try to send transaction wait... (90 sec basic)")

        success, tx_hash = TransactionManager.buy(
            user_id=message.from_user.id,
            token_address=token_address,
            sol_amount=sol_amount,
        )

        if success:
            await message.answer(
                "✅ Your transaction has been successfully sent!\n\n"
                f"🔹 Token Address: `{token_address}`\n"
                f"🔹 Amount: {sol_amount} SOL to token {amount_out_token / (10 ** int(fetch_token_decimals(token_address)))}\n\n"
                f"https://solana.fm/tx/{tx_hash}",
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ Transaction failed. Please try again later.")

        await state.clear()
        await message.answer("You are back to the main menu.", reply_markup=main_menu())

    except Exception as e:
        logger.error(f"Unexpected error in confirm_transaction: {e}")
        await message.answer("An unexpected error occurred. Please try again later.")
        await state.clear()


# ----------------- Menu: SELL -----------------
def sell_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Back")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

@router.message(lambda msg: msg.text == "Sell")
async def start_sell_process(message: Message, state: FSMContext):
    await message.answer("Please enter the token address you want to sell or click 'Back' to return.", reply_markup=sell_menu())
    await state.set_state(SellState.waiting_for_token_address)

# @router.message(lambda msg: msg.text == "Back", StateFilter(SellState.waiting_for_token_address))
# @router.message(lambda msg: msg.text == "Back", StateFilter(SellState.waiting_for_token_amount))
# @router.message(lambda msg: msg.text == "Back", StateFilter(SellState.waiting_for_confirmation))
# async def back_to_main_menu(message: Message, state: FSMContext):
#     current_state = await state.get_state()
#     logger.info(f"[DEBUG] User {message.from_user.id} pressed 'Back'. Current state: {current_state}")
#     await state.clear()
#     await message.answer("You are back to the main menu.", reply_markup=main_menu())

@router.message(StateFilter(SellState.waiting_for_token_address))
async def handle_token_address_for_sell(message: Message, state: FSMContext):
    token_address = message.text.strip()
    if len(token_address) != 44:
        await message.answer("Invalid token address. Please enter a valid address.")
        return
    await state.update_data(token_address=token_address)
    await message.answer(
        "Token address saved. Now enter the amount you want to sell (as a percentage of your balance 1 to 100) or click 'Back' to change the address.",
        reply_markup=sell_menu(),
    )
    await state.set_state(SellState.waiting_for_token_amount)

@router.message(StateFilter(SellState.waiting_for_token_amount))
async def handle_token_amount_for_sell(message: Message, state: FSMContext):
    try:
        percentage_text = message.text.strip()
        percentage = int(percentage_text)
        await state.update_data(percentage=percentage)

        if not (1 <= percentage <= 100):
            await message.answer("Percentage must be between 1 and 100. Please try again.")
            return

        data = await state.get_data()
        token_address = data.get("token_address")
        token_balance = get_token_balance_lamports(user_id=message.from_user.id, token_address=token_address)
        if token_balance == 0:
            await message.answer("No token balance. Nothing to sell.")
            return

        sell_amount = int(token_balance * (percentage / 100))
        await state.update_data(sell_amount=sell_amount, percentage=percentage)
        user_data = get_user_data(message.from_user.id)

        output_amount_out = TransactionManager.get_quote(
            input_mint=token_address,
            output_mint='So11111111111111111111111111111111111111112',
            amount=token_balance,
            pub_key_str=user_data['solana_wallet_address']
        )
        if not output_amount_out:
            await message.answer("Failed to fetch a quote. Please try again later.")
            return
        output_amount = int(output_amount_out["outAmount"]) / (10**9)
        await state.update_data(output_amount=output_amount)
        await state.update_data(token_balance=token_balance)

        await message.answer(
            text=f"You want to sell {percentage}% of your tokens.\n"
            f"Token amount: {(token_balance / (10 ** int(fetch_token_decimals(token_address)))) * (percentage/100)}\n"
            f"Token Address: `{token_address}`\n"
            f"Approximate SOL result: {output_amount}\n\n"
            "Click 'Back' to change the amount or 'Confirm' to proceed.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Back")], [KeyboardButton(text="Confirm and send transaction")]],
                resize_keyboard=True,
                one_time_keyboard=False,
            ),
            parse_mode="Markdown",
        )
        await state.set_state(SellState.waiting_for_confirmation)

    except ValueError:
        await message.answer("Please enter a valid percentage (1-100).")

@router.message(lambda msg: msg.text == "Confirm and send transaction", StateFilter(SellState.waiting_for_confirmation))
async def confirm_sell_transaction(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        token_address = data.get("token_address")
        sell_amount = data.get("sell_amount")
        percentage = data.get('percentage')
        token_balance  = data.get('token_balance')
        output_amount = data.get('output_amount')

        if not token_address or sell_amount is None:
            await message.answer("Transaction data is incomplete. Please start again.")
            await state.clear()
            await message.answer("You are back to the main menu.", reply_markup=main_menu())
            return

        await message.answer("Try to send transaction wait... (90 sec basic)")

        success, tx_hash = TransactionManager.sell(
            user_id=message.from_user.id,
            token_address=token_address,
            percentage=percentage,  # Always 100% as we already calculate sell_amount
        )

        if success:
            await message.answer(
                f"✅ Your transaction has been successfully sent!\n\n"
                f"🔹 Token Address: `{token_address}`\n"
                f"🔹 Amount: {(token_balance / (10 ** int(fetch_token_decimals(token_address)))) * (percentage/100)}\n\n"
                f"🔹 Get SOL: {output_amount}\n\n"
                f"https://solana.fm/tx/{tx_hash}",
                parse_mode="Markdown",
            )
        else:
            await message.answer("❌ Transaction failed. Please try again later.")

        await state.clear()
        await message.answer("You are back to the main menu.", reply_markup=main_menu())

    except Exception as e:
        logger.error(f"Unexpected error in confirm_sell_transaction: {e}")
        await message.answer("An unexpected error occurred. Please try again later.")
        await state.clear()