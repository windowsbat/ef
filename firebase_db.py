"""
Простой асинхронный клиент для Firebase Realtime Database через REST API.
Используем Database Secret (legacy token) как ?auth= параметр — этого достаточно
для серверного доступа без установки firebase-admin.
"""
import time
import aiohttp
from config import config


class FirebaseContextStore:
    def __init__(self):
        self.base_url = config.firebase_db_url.rstrip("/")
        self.secret = config.firebase_db_secret
        # Сколько последних сообщений храним на один диалог
        self.max_history = 20

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path}.json?auth={self.secret}"

    async def get_history(self, dialog_id: str) -> list[dict]:
        """dialog_id — например user_id клиента или chat_id обсуждения"""
        url = self._url(f"dialogs/{dialog_id}/messages")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                if not data:
                    return []
                # data — словарь {push_id: {role, text, ts}}
                items = sorted(data.values(), key=lambda x: x.get("ts", 0))
                return items[-self.max_history:]

    async def append_message(self, dialog_id: str, role: str, text: str):
        url = self._url(f"dialogs/{dialog_id}/messages")
        payload = {"role": role, "text": text, "ts": time.time()}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                await resp.json()

    async def is_processed(self, dialog_id: str, message_id: int) -> bool:
        """Дедупликация — чтобы одно и то же сообщение не отвечалось дважды"""
        url = self._url(f"dialogs/{dialog_id}/processed/{message_id}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                return bool(data)

    async def mark_processed(self, dialog_id: str, message_id: int):
        url = self._url(f"dialogs/{dialog_id}/processed/{message_id}")
        async with aiohttp.ClientSession() as session:
            async with session.put(url, json=True) as resp:
                await resp.json()


firebase_store = FirebaseContextStore()
