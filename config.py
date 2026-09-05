import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Config:
    # Токен бота, выданный @BotFather
    bot_token: str = os.getenv("BOT_TOKEN", "")

    # Ключ OpenRouter (sk-or-v1-...)
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

    # Firebase Realtime Database
    # Пример FIREBASE_DB_URL: https://your-project-id-default-rtdb.firebaseio.com
    firebase_db_url: str = os.getenv("FIREBASE_DB_URL", "")
    # Секрет БД (Database secret, legacy token) — из Firebase Console -> Project settings -> Service accounts -> Database secrets
    firebase_db_secret: str = os.getenv("FIREBASE_DB_SECRET", "")

    # Telegram user_id владельца аккаунта, для которого бот работает как "бизнес-секретарь"
    # (единственный аккаунт, который подключает бота через Telegram Business)
    allowed_business_user_id: int = int(os.getenv("ALLOWED_BUSINESS_USER_ID", "8623340602"))

    # Юзернейм/ID канала, чьи обсуждения бот комментирует (например @news_karamod)
    target_channel_username: str = os.getenv("TARGET_CHANNEL_USERNAME", "news_karamod")
    # ID группы-обсуждения канала (число со знаком минус, начинается на -100...)
    discussion_group_id: int = int(os.getenv("DISCUSSION_GROUP_ID", "0"))

    # Задержка перед ответом, сек
    reply_delay_seconds: int = int(os.getenv("REPLY_DELAY_SECONDS", "10"))

    # Системный промпт "секретаря/модератора"
    system_prompt: str = os.getenv(
        "SYSTEM_PROMPT",
        "Ты — вежливый секретарь-модератор. Отвечай по теме кратко и по делу, "
        "поддерживай контекст переписки, не выдумывай факты."
    )


config = Config()
