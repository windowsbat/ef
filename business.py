"""
Обрабатывает сообщения, которые приходят в личку аккаунта 8623340602
через Telegram Business (подключённый бот-секретарь).
Работает ТОЛЬКО если business_connection принадлежит разрешённому аккаунту.
"""
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import BusinessMessagesDeleted, Message

from config import config
import ai_state
import delay_manager
import firebase_db
import message_archive
import openrouter

router = Router(name="business")

# Кэш: business_connection_id -> user_id владельца (чтобы не дёргать API каждый раз)
_connection_owner_cache: dict[str, int] = {}


async def _is_allowed_connection(bot: Bot, business_connection_id: str) -> bool:
    if business_connection_id in _connection_owner_cache:
        owner_id = _connection_owner_cache[business_connection_id]
    else:
        conn = await bot.get_business_connection(business_connection_id)
        owner_id = conn.user.id
        _connection_owner_cache[business_connection_id] = owner_id
    return owner_id == config.allowed_business_user_id


def _chat_key(message: Message) -> str:
    return f"business:{message.chat.id}"


@router.business_message(Command("off"))
async def turn_ai_off(message: Message, bot: Bot):
    if not message.business_connection_id:
        return
    if not message.from_user or message.from_user.id != config.allowed_business_user_id:
        return
    if not await _is_allowed_connection(bot, message.business_connection_id):
        return
    ai_state.set_enabled(_chat_key(message), False)
    await bot.send_message(
        chat_id=message.chat.id,
        text="ИИ выключен. Для включения напишите /on.",
        business_connection_id=message.business_connection_id,
    )


@router.business_message(Command("on"))
async def turn_ai_on(message: Message, bot: Bot):
    if not message.business_connection_id:
        return
    if not message.from_user or message.from_user.id != config.allowed_business_user_id:
        return
    if not await _is_allowed_connection(bot, message.business_connection_id):
        return
    ai_state.set_enabled(_chat_key(message), True)
    await bot.send_message(
        chat_id=message.chat.id,
        text="ИИ включен.",
        business_connection_id=message.business_connection_id,
    )


@router.business_message(F.text)
async def on_business_message(message: Message, bot: Bot):
    if not message.business_connection_id:
        return
    if not await _is_allowed_connection(bot, message.business_connection_id):
        return  # чужой бизнес-аккаунт подключил этого же бота — игнорируем
    message_archive.remember(message)
    if message.from_user and message.from_user.id == config.allowed_business_user_id:
        return
    if not ai_state.is_enabled(_chat_key(message)):
        return

    dialog_id = f"business:{message.chat.id}"

    if await firebase_db.firebase_store.is_processed(dialog_id, message.message_id):
        return
    await firebase_db.firebase_store.mark_processed(dialog_id, message.message_id)

    async def _on_fire(d_id: str, combined_text: str):
        if not ai_state.is_enabled(_chat_key(message)):
            return
        history = await firebase_db.firebase_store.get_history(d_id)
        reply_text = await openrouter.generate_reply(history, combined_text)

        await bot.send_message(
            chat_id=message.chat.id,
            text=reply_text,
            business_connection_id=message.business_connection_id,
        )

        await firebase_db.firebase_store.append_message(d_id, "user", combined_text)
        await firebase_db.firebase_store.append_message(d_id, "assistant", reply_text)

    await delay_manager.schedule_reply(
        dialog_id, message.text, config.reply_delay_seconds, _on_fire
    )


@router.business_message()
async def on_business_media(message: Message, bot: Bot):
    if not message.business_connection_id:
        return
    if not await _is_allowed_connection(bot, message.business_connection_id):
        return
    message_archive.remember(message)


@router.edited_business_message()
async def on_edited_business_message(message: Message, bot: Bot):
    if not message.business_connection_id:
        return
    if not await _is_allowed_connection(bot, message.business_connection_id):
        return
    previous = message_archive.update(message)
    await message_archive.notify_edited(
        bot,
        message,
        previous,
        config.allowed_business_user_id,
    )


@router.deleted_business_messages()
async def on_deleted_business_messages(event: BusinessMessagesDeleted, bot: Bot):
    if not await _is_allowed_connection(bot, event.business_connection_id):
        return
    await message_archive.notify_owner(bot, event, config.allowed_business_user_id)
