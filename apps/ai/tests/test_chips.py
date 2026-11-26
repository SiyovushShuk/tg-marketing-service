from apps.ai.chips import DEFAULT_CHIPS
from apps.ai.services.ask_service import MAX_QUESTION_LENGTH


def test_chip_ids_are_unique():
    ids = [chip["id"] for chip in DEFAULT_CHIPS]
    assert len(ids) == len(set(ids))


def test_chip_prompts_fit_question_limit():
    # Чип нажимают, и его prompt уходит в POST /author/ask-ai/ как question
    for chip in DEFAULT_CHIPS:
        assert 0 < len(chip["prompt"]) <= MAX_QUESTION_LENGTH