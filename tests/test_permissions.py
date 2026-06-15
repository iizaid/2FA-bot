from types import SimpleNamespace

import pytest

from app.bot.permissions import ensure_owner


class DummyMessage:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str, **kwargs) -> None:
        self.replies.append(text)


@pytest.mark.asyncio
async def test_owner_allowed() -> None:
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=123),
        callback_query=None,
        effective_message=DummyMessage(),
    )
    context = SimpleNamespace(bot_data={"settings": SimpleNamespace(owner_telegram_id=123)})

    assert await ensure_owner(update, context) is True


@pytest.mark.asyncio
async def test_unauthorized_user_rejected() -> None:
    message = DummyMessage()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=999),
        callback_query=None,
        effective_message=message,
    )
    context = SimpleNamespace(bot_data={"settings": SimpleNamespace(owner_telegram_id=123)})

    assert await ensure_owner(update, context) is False
    assert message.replies == ["Access denied. This private bot is configured for its owner only."]

