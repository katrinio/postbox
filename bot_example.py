#!/usr/bin/env python3
"""
Minimal Telegram bot with Web App for Postbox.
This is just an example - you can use any Telegram bot library or even BotAPI directly.

Usage:
    BOT_TOKEN=your_token python bot_example.py

Then configure Web App URL in @BotFather:
    Bot Settings → Web App → http://localhost:3000 (for dev)
"""

import asyncio
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("ERROR: BOT_TOKEN env var not set")
        print("Usage: BOT_TOKEN=your_token python bot_example.py")
        return

    bot = Bot(token=token)
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def start_handler(message: types.Message):
        """Respond to /start with Web App button"""

        # Web App button that opens Postbox
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📖 Открыть Postbox", web_app=WebAppInfo(url="http://localhost:3000"))]
            ]
        )

        await message.answer(
            "👋 Добро пожаловать в Postbox!\n\nНажмите кнопку ниже, чтобы открыть журнал писем:", reply_markup=keyboard
        )

    # Ignore other messages
    @dp.message()
    async def echo_handler(message: types.Message):
        await message.answer("Используйте команду /start или нажмите кнопку 'Открыть Postbox' ↓")

    print("Bot started. Press Ctrl+C to stop.")
    print(f"Chat with bot: https://t.me/{(await bot.get_me()).username}")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
