import json

import pytest
from django.core.cache import cache

from apps.parser.models import ChannelModerator, TelegramChannel

pytestmark = pytest.mark.django_db

URL = "/author/ask-ai/"


@pytest.fixture(autouse=True)
def local_cache(settings):
    # В settings кеш на Redis, в тестах он не нужен
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "ask-ai-tests",
        }
    }
    settings.AI_API_KEY = None  # значит, всегда fallback
    cache.clear()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="author", email="a@example.com", password="pass12345"
    )


@pytest.fixture
def channel(user):
    ch = TelegramChannel.objects.create(
        channel_id=1001,
        username="testchan",
        title="Тестовый канал",
        participants_count=12345,
        average_views=800,
    )
    ChannelModerator.objects.create(user=user, channel=ch, is_owner=True)
    return ch


def post(client, payload):
    return client.post(
        URL, data=json.dumps(payload), content_type="application/json"
    )


def test_anonymous_gets_401(client, channel):
    response = post(client, {"channel": channel.pk, "question": "Привет?"})
    assert response.status_code == 401


def test_not_moderator_gets_403(client, channel, django_user_model):
    stranger = django_user_model.objects.create_user(
        username="stranger", email="s@example.com", password="pass12345"
    )
    client.force_login(stranger)
    response = post(client, {"channel": channel.pk, "question": "Привет?"})
    assert response.status_code == 403


def test_unknown_channel_gets_same_403(client, user):
    client.force_login(user)
    response = post(client, {"channel": 999999, "question": "Привет?"})
    assert response.status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"channel": 1, "question": ""},
        {"channel": 1, "question": "   "},
        {"channel": 1, "question": "я" * 501},
        {"channel": 1},
        {"question": "Привет?"},
        {"channel": "abc", "question": "Привет?"},
    ],
)
def test_invalid_payload_gets_400(client, user, payload):
    client.force_login(user)
    assert post(client, payload).status_code == 400


def test_invalid_json_gets_400(client, user):
    client.force_login(user)
    response = client.post(URL, data="не json", content_type="application/json")
    assert response.status_code == 400


def test_owner_gets_fallback_answer(client, user, channel):
    client.force_login(user)
    response = post(client, {"channel": channel.pk, "question": "Как дела?"})

    assert response.status_code == 200
    body = response.json()
    assert body["fallback"] is True
    assert "Тестовый канал" in body["answer"]


def test_rate_limit_gets_429(client, user, channel, settings):
    settings.ASK_AI_RATE_LIMIT = "2/m"
    client.force_login(user)
    payload = {"channel": channel.pk, "question": "Как дела?"}

    assert post(client, payload).status_code == 200
    assert post(client, payload).status_code == 200
    assert post(client, payload).status_code == 429