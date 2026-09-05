import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import config
import business
import discussion

logging.basicConfig(level=logging.INFO)


async def main():
    if not config.bot_token:
        raise RuntimeError("BOT_TOKEN не задан в переменных окружения")

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.include_router(business.router)
    dp.include_router(discussion.router)

    # Явно указываем нужные типы апдейтов, включая business_message
    allowed_updates = [
        "message",
        "business_connection",
        "business_message",
        "edited_business_message",
        "deleted_business_messages",
    ]

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=allowed_updates)


if __name__ == "__main__":
    asyncio.run(main())
