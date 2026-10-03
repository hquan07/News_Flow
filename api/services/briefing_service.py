"""Citation-first extractive summaries and factual event briefings."""

import re

from api.services.analytics import _query
from api.services.event_clustering import event_detail


def citation_summary(answer: str, sources: list[dict]) -> str:
    """Turn retrieved excerpts into compact bullets without generating new claims."""
    if not sources:
        return answer
    degraded = next((line for line in answer.splitlines() if "chỉ tìm theo từ khóa" in line), None)
    excerpts = []
    for line in answer.splitlines():
        match = re.match(r"\[(\d+)\]\s+(.+)", line.strip())
        if match:
            citation = int(match.group(1))
            text = match.group(2).strip()
            if citation <= len(sources):
                excerpts.append(f"- {text} [{citation}]")
    if not excerpts:
        return answer
    prefix = f"{degraded}\n" if degraded else ""
    return prefix + "Tóm tắt trích xuất từ các bài đã đối chiếu:\n" + "\n".join(excerpts[:5]) + "\nMỗi ý giữ nguyên nội dung nguồn; số trong ngoặc vuông khớp danh sách trích dẫn."


def event_briefing(event_id: str) -> dict:
    event = event_detail(event_id, days=30)
    ids = [str(item["article_id"]) for item in event["articles"]]
    sentiment = _query(
        "SELECT sentiment_label AS label, count() AS count FROM ("
        "SELECT url_hash, argMax(sentiment_label, loaded_at) AS sentiment_label "
        "FROM newspulse.raw_article_sentiment WHERE url_hash IN {ids:Array(String)} GROUP BY url_hash"
        ") GROUP BY sentiment_label ORDER BY count DESC",
        {"ids": ids},
    ) if ids else []
    keywords = _query(
        "SELECT keyword, countDistinct(url_hash) AS article_count FROM newspulse.raw_article_keywords "
        "WHERE url_hash IN {ids:Array(String)} GROUP BY keyword ORDER BY article_count DESC LIMIT 10",
        {"ids": ids},
    ) if ids else []
    citations = [
        {"article_id": str(item["article_id"]), "title": item["title"], "url": item["url"], "source": item["source"], "published_at": item.get("published_at")}
        for item in event["articles"][:10]
    ]
    timeline = sorted(
        [{"published_at": item.get("published_at"), "source": item["source"], "title": item["title"], "citation": index}
         for index, item in enumerate(event["articles"][:10], 1)],
        key=lambda item: str(item["published_at"]),
    )
    return {
        "event_id": event_id,
        "title": event["title"],
        "summary": [
            f"{event['article_count']} bài từ {len(event['sources'])} nguồn [{1 if citations else ''}]",
            f"{event['duplicate_count']} bài được đánh dấu gần trùng",
            f"Nguồn tham gia: {', '.join(event['sources'])}",
        ],
        "sentiment": sentiment,
        "keywords": keywords,
        "timeline": timeline,
        "citations": citations,
        "generated_from": "warehouse facts and extractive metadata",
    }
