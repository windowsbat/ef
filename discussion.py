"""
Обрабатывает сообщения в группе-обсуждении (linked discussion group) канала.
Бот должен быть добавлен в эту группу как админ (или без ограничений на чтение сообщений).
Отвечает в той же "теме" (message_thread_id), которая соответствует конкретному посту.
"""
import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message

from config import config
import ai_state
import delay_manager
import firebase_db
import openrouter

router = Router(name="discussion")
logger = logging.getLogger(__name__)


def _dialog_id(message: Message) -> str:
    # Каждый пост в канале создаёт свою "тему" в группе обсуждений —
    # используем thread_id, чтобы у каждого поста был свой контекст диалога.
    thread = message.message_thread_id or 0
    return f"discussion:{message.chat.id}:{thread}"


def _chat_key(message: Message) -> str:
    return f"discussion:{message.chat.id}"


@router.message(F.chat.id == config.discussion_group_id, Command("off"))
async def turn_ai_off(message: Message):
    if not message.from_user or message.from_user.id != config.allowed_business_user_id:
        return
    ai_state.set_enabled(_chat_key(message), False)
    await message.reply("ИИ выключен в этом чате. Для включения напишите /on.")


@router.message(F.chat.id == config.discussion_group_id, Command("on"))
async def turn_ai_on(message: Message):
    if not message.from_user or message.from_user.id != config.allowed_business_user_id:
        return
    ai_state.set_enabled(_chat_key(message), True)
    await message.reply("ИИ включен в этом чате.")


@router.message(F.chat.id == config.discussion_group_id, F.text)
async def on_discussion_message(message: Message, bot: Bot):
    # Пропускаем служебное авто-сообщение о репосте самого поста канала
    if message.is_automatic_forward or (message.from_user and message.from_user.is_bot):
        return
    if message.from_user and message.from_user.id == config.allowed_business_user_id:
        return
    if not ai_state.is_enabled(_chat_key(message)):
        return

    dialog_id = _dialog_id(message)

    if await firebase_db.firebase_store.is_processed(dialog_id, message.message_id):
        return
    await firebase_db.firebase_store.mark_processed(dialog_id, message.message_id)

    async def _on_fire(d_id: str, combined_text: str):
        if not ai_state.is_enabled(_chat_key(message)):
            return
        try:
            history = await firebase_db.firebase_store.get_history(d_id)
            reply_text = await openrouter.generate_reply(history, combined_text)
        except Exception:
            logger.exception("Не удалось сформировать ответ для %s", d_id)
            return

        await bot.send_message(
            chat_id=message.chat.id,
            text=reply_text,
            message_thread_id=message.message_thread_id,
        )

        await firebase_db.firebase_store.append_message(d_id, "user", combined_text)
        await firebase_db.firebase_store.append_message(d_id, "assistant", reply_text)

    await delay_manager.schedule_reply(
        dialog_id, message.text, config.reply_delay_seconds, _on_fire
    )
