from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from utils.setup import ensure_directories_and_files_exist
from bot.handlers import router
import asyncio
import json
import logging
import os
import sys

# Setup logging
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)  # Create logs directory if it doesn't exist
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "bot.log"),
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())  # Also output logs to console

# Ensure directories and files exist
ensure_directories_and_files_exist()

# Load settings
try:
    with open("data/settings.json", "r") as f:
        config = json.load(f)
except FileNotFoundError:
    logger.error("Settings file not found! Please ensure 'data/settings.json' exists.")
    sys.exit(1)

# Validate Telegram token
if not config.get("telegram_token"):
    print('')
    logger.error("Telegram token is missing in 'data/settings.json'. Please fill it and restart the bot.")
    print('')
    sys.exit(1)

# Initialize bot
try:
    bot = Bot(token=config["telegram_token"])
except Exception as e:
    logger.error(f"Failed to initialize bot: {e}")
    sys.exit(1)

dp = Dispatcher()

# Register routes
dp.include_router(router)

# Set Telegram commands
async def set_commands():
    commands = [
        BotCommand(command="/start", description="Start working with the bot"),
    ]
    await bot.set_my_commands(commands)
    logger.info("Commands successfully set in Telegram")

async def main():
    logger.info("Bot is starting...")
    await set_commands()
    logger.info("Bot is ready! Waiting for messages...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually via KeyboardInterrupt.")