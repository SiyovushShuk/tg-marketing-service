from unittest.mock import patch

import pytest

from apps.ai.services.ask_service import ask_about_channel
from apps.parser.models import ChannelStats, TelegramChannel

pytestmark = pytest.mark.django_db


@pytest.fixture
def channel():
    ch = TelegramChannel.objects.create(
        channel_id=1001,
        username="testchan",
        title="Тестовый канал",
        description="О тестах",
        participants_count=12345,
        average_views=800,
    )
    ChannelStats.objects.create(
        channel=ch, participants_count=12345, daily_growth=42
    )
    return ch


def test_fallback_when_no_api_key(settings, channel):
    settings.AI_ENABLED = True
    settings.AI_API_KEY = None

    result = ask_about_channel(channel, "Когда постить?")

    assert result.is_fallback is True
    assert "Тестовый канал" in result.answer


def test_fallback_is_deterministic(settings, channel):
    settings.AI_API_KEY = None

    first = ask_about_channel(channel, "Когда постить?")
    second = ask_about_channel(channel, "Когда постить?")

    assert first.answer == second.answer


def test_channel_context_goes_into_prompt(settings, channel):
    settings.AI_ENABLED = True
    settings.AI_API_KEY = "test-key"

    with patch("apps.ai.parsing.generate") as mock_generate:
        mock_generate.return_value = '{"answer": "ok"}'
        result = ask_about_channel(channel, "Как дела?")

    assert result.is_fallback is False
    assert result.answer == "ok"
    prompt = mock_generate.call_args.kwargs["prompt"]
    assert "Тестовый канал" in prompt
    assert "12345" in prompt
    assert "Как дела?" in prompt


def _ask_and_get_prompt(channel, settings) -> str:
    settings.AI_ENABLED = True
    settings.AI_API_KEY = "test-key"
    with patch("apps.ai.parsing.generate") as mock_generate:
        mock_generate.return_value = '{"answer": "ok"}'
        ask_about_channel(channel, "Как дела?")
    return mock_generate.call_args.kwargs["prompt"]


def test_last_messages_go_into_prompt_newest_first(settings, channel):
    channel.last_messages = [
        {"post_id": 1, "post_text": "Старый пост", "post_views": 100},
        {
            "post_id": 2,
            "post_text": "Свежий пост про Django",
            "post_views": 250,
        },
    ]
    channel.save()

    prompt = _ask_and_get_prompt(channel, settings)

    assert "Свежий пост про Django" in prompt
    assert "250" in prompt
    assert prompt.index("Свежий пост") < prompt.index("Старый пост")


def test_dirty_last_messages_do_not_break_context(settings, channel):
    channel.last_messages = [
        "мусор",
        {"post_id": "x", "post_text": "не число"},
        {"post_id": 3, "post_text": None, "post_views": "много"},
        {"post_id": 4, "post_text": "Нормальный пост", "post_views": 10},
    ]
    channel.save()

    prompt = _ask_and_get_prompt(channel, settings)

    assert "Нормальный пост" in prompt
    assert "мусор" not in prompt


def test_long_message_text_is_truncated(settings, channel):
    channel.last_messages = [
        {"post_id": 1, "post_text": "я" * 1000, "post_views": 5},
    ]
    channel.save()

    prompt = _ask_and_get_prompt(channel, settings)

    assert "я" * 300 in prompt
    assert "я" * 301 not in prompt