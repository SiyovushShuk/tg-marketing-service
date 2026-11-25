import pytest
from unittest.mock import patch

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