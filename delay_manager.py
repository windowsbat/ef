"""
Логика "секретаря": если человек пишет несколько сообщений подряд,
мы не отвечаем на каждое, а ждём config.reply_delay_seconds тишины,
собираем все накопленные сообщения в один текст и отвечаем один раз.
Это стандартный паттерн для "живого" секретаря/модератора.
"""
import asyncio
from typing import Callable, Awaitable

# dialog_id -> list[str] накопленных сообщений
_pending: dict[str, list[str]] = {}
# dialog_id -> asyncio.Task таймера
_timers: dict[str, asyncio.Task] = {}


async def schedule_reply(
    dialog_id: str,
    text: str,
    delay_seconds: int,
    on_fire: Callable[[str, str], Awaitable[None]],
):
    """
    dialog_id: уникальный ключ диалога (chat_id, либо chat_id:thread_id)
    on_fire(dialog_id, combined_text): корутина, вызывается по истечении задержки
    """
    _pending.setdefault(dialog_id, []).append(text)

    # Если уже есть таймер — отменяем и ставим заново (сброс задержки на новое сообщение)
    old_task = _timers.get(dialog_id)
    if old_task and not old_task.done():
        old_task.cancel()

    async def _fire():
        try:
            await asyncio.sleep(delay_seconds)
        except asyncio.CancelledError:
            return
        combined = "\n".join(_pending.pop(dialog_id, []))
        _timers.pop(dialog_id, None)
        if combined.strip():
            await on_fire(dialog_id, combined)

    _timers[dialog_id] = asyncio.create_task(_fire())
