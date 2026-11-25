from dataclasses import dataclass
from typing import Any

from apps.ai.parsing import with_ai_fallback
from apps.parser.models import ChannelStats, TelegramChannel

MAX_QUESTION_LENGTH = 500


@dataclass(frozen=True)
class AskResult:
    answer: str
    is_fallback: bool


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
        "last_messages_block": "нет данных",  # TODO: подтянуть из Post
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