from types import SimpleNamespace

import pytest

from api.services import chat_generation


@pytest.mark.asyncio
async def test_grounded_stream_only_emits_sentences_with_valid_citations(monkeypatch):
    async def tokens(*_args):
        for token in (
            "Thông tin được nguồn xác nhận [1]. ",
            "Câu không có nguồn. ",
            "Citation ngoài phạm vi [3].\n",
            "Nguồn thứ hai bổ sung chi tiết [2].",
        ):
            yield token

    monkeypatch.setattr(chat_generation, "_model_tokens", tokens)
    chunks = [chunk async for chunk in chat_generation.stream_grounded_answer(
        "Câu hỏi", "Trích đoạn", [{"article_id": "a"}, {"article_id": "b"}],
    )]
    assert chunks == [
        "Thông tin được nguồn xác nhận [1].\n",
        "Nguồn thứ hai bổ sung chi tiết [2].\n",
    ]


def test_generation_is_opt_in_and_only_for_cited_content_answers(monkeypatch):
    monkeypatch.setattr(chat_generation, "get_settings", lambda: SimpleNamespace(
        CHAT_LLM_ENABLED=True, CHAT_LLM_MODEL="local-model",
    ))
    eligible = SimpleNamespace(tool="search_article_content", sources=[{"article_id": "a"}])
    assert chat_generation.can_generate(eligible)
    assert not chat_generation.can_generate(SimpleNamespace(tool="count_articles", sources=[]))

