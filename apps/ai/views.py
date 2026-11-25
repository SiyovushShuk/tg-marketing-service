import json
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.generic.base import View
from django_ratelimit.core import get_usage  # type: ignore[import-untyped]

from apps.ai.services.ai_cabinet_service import AICabinetService
from apps.ai.services.ask_service import MAX_QUESTION_LENGTH, ask_about_channel
from apps.parser.models import TelegramChannel
from config.renderers import render_inertia_from_dto


class AICabinetView(View):
    """AI-кабинет автора (Inertia: AICabinet).

    Данные собираются из AIInsight, Post, TelegramChannel и ChannelStats.
    """

    def get(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        dto = AICabinetService(request.user).build()

        return render_inertia_from_dto(
            request,
            "AICabinet",
            props=dto,
        )


def _error(message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


class AskAIView(View):
    """POST: вопрос AI о канале автора.

    Тело запроса: {"channel": int, "question": str}.
    """

    def post(self, request: HttpRequest) -> JsonResponse:
        if not request.user.is_authenticated:
            return _error("Требуется авторизация.", 401)

        usage = get_usage(
            request,
            group="ask_ai",
            key="user",
            rate=settings.ASK_AI_RATE_LIMIT,
            method="POST",
            increment=True,
        )
        if usage and usage["should_limit"]:
            return _error("Слишком много запросов. Попробуйте позже.", 429)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return _error("Некорректный JSON.", 400)
        if not isinstance(payload, dict):
            return _error("Ожидается JSON-объект.", 400)

        channel_id = payload.get("channel")
        question = payload.get("question")
        if not isinstance(channel_id, int) or isinstance(channel_id, bool):
            return _error("Поле channel должно быть числом.", 400)
        if not isinstance(question, str) or not question.strip():
            return _error("Поле question не должно быть пустым.", 400)
        question = question.strip()
        if len(question) > MAX_QUESTION_LENGTH:
            return _error(
                f"Вопрос длиннее {MAX_QUESTION_LENGTH} символов.", 400
            )

        # Один запрос: канал существует И пользователь его модератор.
        # Для чужого и несуществующего канала ответ одинаковый,
        # чтобы не раскрывать, какие каналы есть в базе.
        channel = TelegramChannel.objects.filter(
            pk=channel_id, moderators__user=request.user
        ).first()
        if channel is None:
            return _error("Нет доступа к каналу.", 403)

        result = ask_about_channel(channel, question)
        return JsonResponse(
            {"answer": result.answer, "fallback": result.is_fallback}
        )