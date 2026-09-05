import logging
import re

import aiohttp
from config import config

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
logger = logging.getLogger(__name__)


def _clean_response(content: str) -> str:
    """Убирает рассуждение провайдеров, которые помещают его в content."""
    if "thinking process" not in content.lower():
        return content.strip()

    draft = re.search(
        r"(?:draft response|draft\s*\(internal\)|draft|possible response|черновик ответа)\s*:?\s*(.*?)(?:\n\s*(?:check against|проверка)|$)",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if draft:
        quoted = re.findall(r'["“](.*?)["”]', draft.group(1), flags=re.DOTALL)
        if quoted:
            return quoted[-1].strip().strip('"“”')
        lines = [line.strip() for line in draft.group(1).splitlines() if line.strip()]
        if lines:
            return lines[0].strip('"“”')

    return content.strip()


async def generate_reply(history: list[dict], new_message: str) -> str:
    """
    history: [{"role": "user"/"assistant", "text": "..."}]
    Возвращает текст ответа ИИ с учётом контекста диалога.
    """
    messages = [{"role": "system", "content": config.system_prompt}]
    for item in history:
        role = "assistant" if item["role"] == "assistant" else "user"
        messages.append({"role": role, "content": item["text"]})
    messages.append({"role": "user", "content": new_message})

    headers = {
        "Authorization": f"Bearer {config.openrouter_api_key}",
        "Content-Type": "application/json",
        # Рекомендуется OpenRouter для рейтинга приложений (необязательно)
        "HTTP-Referer": "https://t.me/news_karamod",
        "X-Title": "news_karamod-secretary-bot",
    }
    payload = {
        "model": config.openrouter_model,
        "messages": messages,
        "temperature": 0.6,
        "max_tokens": 800,
        "reasoning": {"exclude": True},
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60) as resp:
            data = await resp.json(content_type=None)
            if resp.status >= 400:
                error = data.get("error", {}) if isinstance(data, dict) else {}
                message = error.get("message", "неизвестная ошибка")
                logger.error("OpenRouter %s: %s", resp.status, message)
                raise RuntimeError(f"OpenRouter API error {resp.status}: {message}")

            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                logger.error("Неожиданный ответ OpenRouter: %s", data)
                raise RuntimeError("OpenRouter вернул ответ без текста") from exc

            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("OpenRouter вернул пустой ответ")
            cleaned_content = _clean_response(content)
            if not cleaned_content:
                raise RuntimeError("OpenRouter вернул пустой ответ")
            return cleaned_content
