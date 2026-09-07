import html
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import BusinessMessagesDeleted, Message

logger = logging.getLogger(__name__)


@dataclass
class ArchivedMessage:
    chat_id: int
    message_id: int
    user_id: int | None
    user_name: str
    username: str | None
    text: str
    media_type: str | None = None
    file_id: str | None = None


_messages: dict[tuple[str, int, int], ArchivedMessage] = {}


def _key(business_connection_id: str, chat_id: int, message_id: int) -> tuple[str, int, int]:
    return business_connection_id, chat_id, message_id


def _media(message: Message) -> tuple[str | None, str | None]:
    if message.photo:
        return "photo", message.photo[-1].file_id
    if message.animation:
        return "animation", message.animation.file_id
    if message.video:
        return "video", message.video.file_id
    if message.document:
        return "document", message.document.file_id
    if message.audio:
        return "audio", message.audio.file_id
    if message.voice:
        return "voice", message.voice.file_id
    if message.video_note:
        return "video_note", message.video_note.file_id
    if message.sticker:
        return "sticker", message.sticker.file_id
    return None, None


def _build(message: Message) -> ArchivedMessage | None:
    if not message.business_connection_id:
        return None

    media_type, file_id = _media(message)
    text = message.text or message.caption or ""
    if not text and not file_id:
        return None

    user = message.from_user
    return ArchivedMessage(
        chat_id=message.chat.id,
        message_id=message.message_id,
        user_id=user.id if user else None,
        user_name=user.full_name if user else "Неизвестный пользователь",
        username=user.username if user else None,
        text=text,
        media_type=media_type,
        file_id=file_id,
    )


def remember(message: Message) -> None:
    archived = _build(message)
    if archived:
        _messages[_key(message.business_connection_id, message.chat.id, message.message_id)] = archived


def update(message: Message) -> ArchivedMessage | None:
    archived = _build(message)
    if not archived or not message.business_connection_id:
        return None
    key = _key(message.business_connection_id, message.chat.id, message.message_id)
    previous = _messages.get(key)
    _messages[key] = archived
    return previous


def take(
    business_connection_id: str,
    chat_id: int,
    message_id: int,
) -> ArchivedMessage | None:
    return _messages.pop(_key(business_connection_id, chat_id, message_id), None)


def _user_line(message: ArchivedMessage) -> str:
    username = f"@{message.username}" if message.username else "без юзернейма"
    return (
        f"👤 <b>От кого:</b> {html.escape(message.user_name)} "
        f"({html.escape(username)}, ID: <code>{message.user_id}</code>)"
    )


async def _send_media(bot: Bot, chat_id: int, message: ArchivedMessage) -> None:
    if not message.file_id or not message.media_type:
        return
    sender = {
        "photo": bot.send_photo,
        "animation": bot.send_animation,
        "video": bot.send_video,
        "document": bot.send_document,
        "audio": bot.send_audio,
        "voice": bot.send_voice,
        "video_note": bot.send_video_note,
        "sticker": bot.send_sticker,
    }[message.media_type]
    await sender(chat_id=chat_id, **{message.media_type: message.file_id})


async def notify_edited(
    bot: Bot,
    message: Message,
    previous: ArchivedMessage | None,
    owner_user_id: int,
) -> None:
    if not previous or previous.user_id == owner_user_id:
        return
    current = _build(message)
    if not current:
        return

    old_text = previous.text or "[медиа без подписи]"
    new_text = current.text or "[медиа без подписи]"
    text = (
        "✏️ <b>Сообщение изменено</b>\n\n"
        f"{_user_line(previous)}\n"
        f"<b>Было:</b> {html.escape(old_text)}\n"
        f"<b>Стало:</b> {html.escape(new_text)}"
    )
    try:
        await bot.send_message(chat_id=owner_user_id, text=text)
        await _send_media(bot, owner_user_id, current)
    except Exception:
        logger.exception("Не удалось отправить изменённое сообщение %s", message.message_id)


async def notify_owner(
    bot: Bot,
    event: BusinessMessagesDeleted,
    owner_user_id: int,
) -> None:
    for message_id in event.message_ids:
        archived = take(event.business_connection_id, event.chat.id, message_id)
        if not archived or archived.user_id == owner_user_id:
            continue

        text = "🗑️ <b>Удалённое сообщение</b>\n\n" + _user_line(archived)
        if archived.text:
            text += f"\n💬 <b>Текст:</b> {html.escape(archived.text)}"
        try:
            await bot.send_message(chat_id=owner_user_id, text=text)
            await _send_media(bot, owner_user_id, archived)
        except Exception:
            logger.exception("Не удалось отправить удалённое сообщение %s", message_id)
