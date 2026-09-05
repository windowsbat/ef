_disabled_chats: set[str] = set()


def is_enabled(chat_key: str) -> bool:
    return chat_key not in _disabled_chats


def set_enabled(chat_key: str, enabled: bool) -> None:
    if enabled:
        _disabled_chats.discard(chat_key)
    else:
        _disabled_chats.add(chat_key)