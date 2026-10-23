from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bot import run


def test_cycle_start_hook_is_optional(monkeypatch):
    monkeypatch.delenv("BOT_CYCLE_START_URL", raising=False)
    monkeypatch.setattr(run, "BOT_CYCLE_START_TOKEN", "")

    run.run_cycle_start_hook()


def test_cycle_start_hook_requires_token_when_configured(monkeypatch):
    monkeypatch.setenv("BOT_CYCLE_START_URL", "http://127.0.0.1:8768/cycle-start")
    monkeypatch.setattr(run, "BOT_CYCLE_START_TOKEN", "")

    with pytest.raises(RuntimeError, match="Cycle-start callback token is not configured"):
        run.run_cycle_start_hook()


def test_cycle_start_hook_posts_bearer_token_without_proxy(monkeypatch):
    url = "http://127.0.0.1:8768/cycle-start"
    token = "cycle-secret"
    monkeypatch.setenv("BOT_CYCLE_START_URL", url)
    monkeypatch.setattr(run, "BOT_CYCLE_START_TOKEN", token)
    session = MagicMock()

    with patch("bot.run.httpx.Client") as client_factory:
        client_factory.return_value.__enter__.return_value = session
        run.run_cycle_start_hook()

    client_factory.assert_called_once_with(trust_env=False, timeout=5)
    session.post.assert_called_once_with(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    session.post.return_value.raise_for_status.assert_called_once_with()
