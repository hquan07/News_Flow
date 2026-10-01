"""Read-only, bounded data tools available to the Phase 2 chatbot."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import HTTPException

from api.models.chat import ChatRequest
from api.services.analytics import _query, get_alerts


_TIME_WINDOWS = {
    "today": "24 HOUR",
    "7d": "7 DAY",
    "30d": "30 DAY",
}
_TIME_LABELS = {"today": "24 giờ qua", "7d": "7 ngày qua", "30d": "30 ngày qua"}


@dataclass
class ToolResult:
    answer: str
    tool: str | None = None
    sources: list[dict] = field(default_factory=list)
    queried_at: datetime | None = None
    time_range: str | None = None


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn").replace("đ", "d")


def _intent(message: str) -> str | None:
    normalized = _normalized(message)
    if any(word in normalized for word in ("canh bao", "alert", "khung hoang", "bat thuong")):
        return "alerts"
    if any(word in normalized for word in ("sentiment", "cam xuc", "tich cuc", "tieu cuc")):
        return "sentiment"
    if any(word in normalized for word in ("trending", "xu huong", "thinh hanh", "tu khoa", "chu de nao")):
        return "trending"
    if any(word in normalized for word in ("bai viet", "bai bao", "tin moi", "tim tin", "tim bai", "tom tat", "articles")):
        return "articles"
    return None


def _time_range(request: ChatRequest) -> str:
    if request.time_range:
        return request.time_range
    normalized = _normalized(request.message)
    if "hom nay" in normalized or "today" in normalized or "24 gio" in normalized:
        return "today"
    if "30 ngay" in normalized or "30d" in normalized or "thang qua" in normalized:
        return "30d"
    return "7d"


def _search_term(request: ChatRequest) -> str | None:
    if request.query:
        return request.query.strip() or None
    match = re.search(r"\b(?:về|ve|about)\s+(.+)", request.message, re.IGNORECASE)
    if not match:
        return None
    term = match.group(1).strip(" ?.!")
    term = re.sub(
        r"\s+(?:hôm nay|hom nay|trong\s+\d+\s+(?:ngày|ngay)(?:\s+qua)?)$",
        "",
        term,
        flags=re.IGNORECASE,
    )
    return term[:120] or None


def _where(request: ChatRequest, time_range: str, *, title_query: str | None = None):
    conditions = [f"a.publish_time >= now() - INTERVAL {_TIME_WINDOWS[time_range]}"]
    params = {}
    if request.source:
        conditions.append("a.source = {source:String}")
        params["source"] = request.source.strip()
    if request.category:
        conditions.append("a.category = {category:String}")
        params["category"] = request.category.strip()
    if title_query:
        conditions.append("a.title ILIKE {title_query:String}")
        params["title_query"] = f"%{title_query}%"
    return " AND ".join(conditions), params


def _articles(request: ChatRequest, time_range: str) -> ToolResult:
    term = _search_term(request)
    where, params = _where(request, time_range, title_query=term)
    rows = _query(
        "SELECT a.url_hash AS article_id, a.title, a.url, a.source, "
        "a.publish_time AS published_at "
        "FROM newspulse.raw_articles FINAL AS a "
        f"WHERE {where} ORDER BY a.publish_time DESC LIMIT 5",
        params,
    )
    sources = [
        {
            "article_id": str(row["article_id"]),
            "title": row["title"],
            "url": row["url"],
            "source": row["source"],
            "published_at": row.get("published_at"),
        }
        for row in rows if str(row.get("url", "")).startswith(("http://", "https://"))
    ]
    if not sources:
        answer = "Không tìm thấy bài viết phù hợp trong khoảng thời gian này."
    else:
        heading = f"Các bài viết mới nhất{f' về {term}' if term else ''} trong {_TIME_LABELS[time_range]}:"
        answer = heading + "\n" + "\n".join(
            f"{index}. {item['title']} ({item['source']})"
            for index, item in enumerate(sources, 1)
        )
        if "tom tat" in _normalized(request.message):
            answer += "\nHiện mình mới liệt kê bài phù hợp; chưa tóm tắt nội dung toàn văn."
    return ToolResult(answer=answer, tool="search_articles", sources=sources, time_range=time_range)


def _trending(request: ChatRequest, time_range: str) -> ToolResult:
    where, params = _where(request, time_range)
    keyword_query = _search_term(request)
    if keyword_query:
        where += " AND k.keyword ILIKE {keyword_query:String}"
        params["keyword_query"] = f"%{keyword_query}%"
    rows = _query(
        "SELECT k.keyword, countDistinct(a.url_hash) AS count "
        "FROM newspulse.raw_article_keywords AS k "
        "INNER JOIN newspulse.raw_articles FINAL AS a ON k.url_hash = a.url_hash "
        f"WHERE {where} GROUP BY k.keyword ORDER BY count DESC LIMIT 10",
        params,
    )
    if rows:
        answer = f"Từ khóa xuất hiện nhiều trong bài viết trong {_TIME_LABELS[time_range]}:\n" + "\n".join(
            f"{index}. {row['keyword']}: {row['count']} bài"
            for index, row in enumerate(rows, 1)
        )
        answer += "\nĐây là tần suất trong khoảng chọn, chưa phải tốc độ tăng so với kỳ trước."
    else:
        answer = "Chưa có dữ liệu từ khóa trong khoảng thời gian này."
    return ToolResult(answer=answer, tool="get_trending_keywords", time_range=time_range)


def _sentiment(request: ChatRequest, time_range: str) -> ToolResult:
    where, params = _where(request, time_range, title_query=_search_term(request))
    rows = _query(
        "SELECT lowerUTF8(s.sentiment_label) AS sentiment_label, "
        "countDistinct(a.url_hash) AS count "
        "FROM newspulse.raw_articles FINAL AS a "
        "INNER JOIN newspulse.raw_article_sentiment FINAL AS s "
        "ON a.url_hash = s.url_hash "
        f"WHERE {where} GROUP BY sentiment_label ORDER BY count DESC",
        params,
    )
    if rows:
        total = sum(int(row["count"]) for row in rows)
        answer = f"Phân bố cảm xúc trên {total} bài đã được phân tích trong {_TIME_LABELS[time_range]}:\n" + "\n".join(
            f"- {row['sentiment_label']}: {row['count']} bài"
            for row in rows
        )
    else:
        answer = "Chưa có bài viết đã phân tích cảm xúc phù hợp với bộ lọc này."
    return ToolResult(answer=answer, tool="get_sentiment_distribution", time_range=time_range)


def _alerts(request: ChatRequest, time_range: str) -> ToolResult:
    if request.source or request.category or request.query or time_range != "7d":
        raise HTTPException(status_code=422, detail="Alert tool does not support these filters")
    rows = get_alerts(threshold=2.0, limit=5)
    if rows:
        answer = "Cảnh báo tăng đột biến số bài theo giờ trong 7 ngày qua:\n" + "\n".join(
            f"- {row['hour_slot']}: {row['article_count']} bài, z-score {row['z_score']}"
            for row in rows
        )
    else:
        answer = "Không có cảnh báo tăng đột biến số bài trong dữ liệu hiện tại."
    return ToolResult(answer=answer, tool="get_volume_alerts", time_range="7d")


def answer_question(request: ChatRequest, actor: dict) -> ToolResult:
    intent = _intent(request.message)
    if intent == "alerts" and "alerts.read" not in actor["permissions"]:
        raise HTTPException(status_code=403, detail="Forbidden: Missing permission 'alerts.read'")
    if intent in ("articles", "trending", "sentiment") and "dashboard.read" not in actor["permissions"]:
        raise HTTPException(status_code=403, detail="Forbidden: Missing permission 'dashboard.read'")
    if intent is None:
        return ToolResult(answer=(
            "Mình hỗ trợ tìm bài viết, xem từ khóa thịnh hành, phân bố cảm xúc "
            "và cảnh báo tăng đột biến. Hãy hỏi rõ một trong các nội dung này."
        ))
    time_range = _time_range(request)
    result = {
        "articles": _articles,
        "trending": _trending,
        "sentiment": _sentiment,
        "alerts": _alerts,
    }[intent](request, time_range)
    result.queried_at = datetime.now(timezone.utc)
    return result
