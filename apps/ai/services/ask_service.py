from dataclasses import dataclass
from typing import Any

from apps.ai.parsing import with_ai_fallback
from apps.parser.models import ChannelStats, TelegramChannel

MAX_QUESTION_LENGTH = 500
LAST_MESSAGES_LIMIT = 5
MESSAGE_TEXT_LIMIT = 300


@dataclass(frozen=True)
class AskResult:
    answer: str
    is_fallback: bool


def build_last_messages_block(channel: TelegramChannel) -> str:
    """Последние посты канала: одна строка на пост, свежие сверху.

    last_messages это свободный JSONField, поэтому типы проверяются:
    грязные записи не должны ронять ответ.
    """
    entries = [
        message
        for message in (channel.last_messages or [])
        if isinstance(message, dict)
        and isinstance(message.get("post_id"), int)
        and not isinstance(message.get("post_id"), bool)
    ]
    entries.sort(key=lambda message: message["post_id"], reverse=True)

    lines: list[str] = []
    for message in entries[:LAST_MESSAGES_LIMIT]:
        raw_text = message.get("post_text")
        text = raw_text if isinstance(raw_text, str) else ""
        # split/join схлопывает переводы строк: пост не сможет
        # притвориться отдельной строкой или тегом промпта
        text = " ".join(text.split())[:MESSAGE_TEXT_LIMIT]
        raw_views = message.get("post_views")
        views = raw_views if isinstance(raw_views, int) else 0
        lines.append(f"- {text or '(без текста)'} (просмотров: {views})")
    return "\n".join(lines) or "нет данных"


def build_channel_context(channel: TelegramChannel) -> dict[str, Any]:
    """Собрать данные канала под переменные шаблона ASK_V1."""
    last_stat = (
        ChannelStats.objects.filter(channel=channel)
        .order_by("-parsed_at")
        .first()
    )
    return {
        "channel_title": channel.title,
        "category": channel.category,
        "channel_description": channel.description or "нет описания",
        "participants_count": channel.participants_count,
        "daily_growth": last_stat.daily_growth if last_stat else 0,
        "average_views": channel.average_views,
        "last_messages_block": build_last_messages_block(channel),
    }


def build_fallback_answer(ctx: dict[str, Any]) -> str:
    """Детерминированный ответ без AI: только данные канала, без random."""
    return (
        f"Канал «{ctx['channel_title']}»: "
        f"{ctx['participants_count']} подписчиков, "
        f"прирост за день {ctx['daily_growth']}, "
        f"в среднем {ctx['average_views']} просмотров на пост. "
        "Это автоматический ответ без AI-анализа."
    )


def ask_about_channel(channel: TelegramChannel, question: str) -> AskResult:
    ctx = build_channel_context(channel)
    used_fallback = False

    def fallback() -> dict[str, str]:
        nonlocal used_fallback
        used_fallback = True
        return {"answer": build_fallback_answer(ctx)}

    response = with_ai_fallback("ask", fallback, question=question, **ctx)
    return AskResult(answer=response.answer, is_fallback=used_fallback)