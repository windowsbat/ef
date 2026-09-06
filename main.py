import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update

from config import config
import business
import discussion

logging.basicConfig(level=logging.INFO)


async def health_check(request: web.Request) -> web.Response:
    return web.Response(text="ok")


def create_app(bot: Bot, dp: Dispatcher) -> web.Application:
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    async def telegram_webhook(request: web.Request) -> web.Response:
        webhook_secret = os.getenv("WEBHOOK_SECRET", "")
        if webhook_secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != webhook_secret:
            return web.Response(status=403, text="forbidden")

        try:
            update = Update.model_validate(await request.json())
        except (ValueError, TypeError):
            return web.Response(status=400, text="invalid update")

        await dp.feed_update(bot, update)
        return web.Response(text="ok")

    app.router.add_post("/telegram/webhook", telegram_webhook)
    return app


async def start_webhook_server(bot: Bot, dp: Dispatcher) -> web.AppRunner:
    app = create_app(bot, dp)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "10000")))
    await site.start()
    return runner


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

    allowed_updates = [
        "message",
        "business_connection",
        "business_message",
        "edited_business_message",
        "deleted_business_messages",
    ]

    webhook_base_url = os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL")
    if not webhook_base_url:
        raise RuntimeError(
            "WEBHOOK_URL не задан. На Render добавьте WEBHOOK_URL с адресом сервиса "
            "или используйте переменную RENDER_EXTERNAL_URL."
        )

    webhook_url = f"{webhook_base_url.rstrip('/')}/telegram/webhook"
    webhook_secret = os.getenv("WEBHOOK_SECRET", "")
    webhook_runner = await start_webhook_server(bot, dp)
    try:
        await bot.set_webhook(
            url=webhook_url,
            allowed_updates=allowed_updates,
            drop_pending_updates=True,
            secret_token=webhook_secret or None,
        )
        logging.info("Webhook установлен: %s", webhook_url)
        await asyncio.Event().wait()
    finally:
        await bot.delete_webhook()
        await webhook_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
