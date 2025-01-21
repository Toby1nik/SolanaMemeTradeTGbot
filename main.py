from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from bot.handlers import router
import asyncio
import json
import logging
import os

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

# Load settings
with open("data/settings.json", "r") as f:
    config = json.load(f)

# Initialize bot
bot = Bot(token=config["telegram_token"])
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
    asyncio.run(main())
