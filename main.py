import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import config
import business
import discussion

logging.basicConfig(level=logging.INFO)


async def health_check(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def start_health_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "10000")))
    await site.start()
    return runner


async def main():
    if not config.bot_token:
        raise RuntimeError("BOT_TOKEN не задан в переменных окружения")

    health_runner = await start_health_server()

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

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    finally:
        await health_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
