"""Read-only, bounded data tools available to the chatbot."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import HTTPException

from api.models.chat import ChatRequest
from api.services.analytics import _query, get_alerts
from api.services.rag_retrieval import retrieve


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
    chart: dict | None = None
    context: dict | None = None


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn").replace("đ", "d")


def _intent(message: str) -> str | None:
    normalized = _normalized(message)
    if any(word in normalized for word in ("canh bao", "alert", "khung hoang", "bat thuong")):
        return "alerts"
    if any(word in normalized for word in ("so sanh nguon", "so sanh bao", "nguon nao", "bao nao", "compare sources")):
        return "sources"
    if any(word in normalized for word in ("sentiment", "cam xuc", "tich cuc", "tieu cuc")):
        return "sentiment"
    if any(word in normalized for word in ("trending", "xu huong", "thinh hanh", "tu khoa", "chu de nao")):
        return "trending"
    if any(word in normalized for word in ("tom tat", "noi dung", "noi gi ve", "giai thich ve", "semantic", "tuong tu", "summarize")):
        return "rag"
    if any(word in normalized for word in ("bai viet", "bai bao", "tin moi", "tim tin", "tim bai", "tom tat", "articles")):
        return "articles"
    if any(word in normalized for word in ("entity", "thuc the", "nhan vat", "to chuc nao", "dia danh", "lien quan den")):
        return "entities"
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


def _has_time_hint(message: str) -> bool:
    normalized = _normalized(message)
    return any(value in normalized for value in (
        "hom nay", "today", "24 gio", "7 ngay", "7d", "30 ngay", "30d", "thang qua"
    ))


def _is_followup(message: str) -> bool:
    normalized = _normalized(message).strip()
    return normalized.startswith(("con ", "the ", "vay ", "neu ", "so voi "))


_SOURCE_NAMES = {
    "vnexpress": "vnexpress",
    "tuoi tre": "tuoitre",
    "tuoitre": "tuoitre",
    "thanh nien": "thanhnien",
    "thanhnien": "thanhnien",
    "dan tri": "dantri",
    "dantri": "dantri",
    "lao dong": "laodong",
    "laodong": "laodong",
    "tien phong": "tienphong",
    "tienphong": "tienphong",
}


def _mentioned_sources(message: str) -> list[str]:
    normalized = _normalized(message)
    return list(dict.fromkeys(
        canonical for alias, canonical in _SOURCE_NAMES.items()
        if re.search(rf"\b{re.escape(alias)}\b", normalized)
    ))


def _chart(title: str, unit: str, rows: list[dict], label_key: str, value_key: str) -> dict | None:
    if not rows:
        return None
    return {
        "type": "bar",
        "title": title,
        "unit": unit,
        "points": [
            {"label": str(row[label_key]), "value": float(row[value_key])}
            for row in rows[:10]
        ],
    }


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
    return ToolResult(
        answer=answer, tool="get_trending_keywords", time_range=time_range,
        chart=_chart("Tần suất từ khóa", "bài viết", rows, "keyword", "count"),
    )


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
    return ToolResult(
        answer=answer, tool="get_sentiment_distribution", time_range=time_range,
        chart=_chart("Phân bố cảm xúc", "bài viết", rows, "sentiment_label", "count"),
    )


def _sources(request: ChatRequest, time_range: str) -> ToolResult:
    if request.source:
        raise HTTPException(status_code=422, detail="Clear the single-source filter to compare sources")
    selected = request.compare_sources or _mentioned_sources(request.message)
    if request.query:
        title_query = request.query
    else:
        title_query = _search_term(request)
    where, params = _where(request, time_range, title_query=title_query)
    if selected:
        where += " AND has({source_names:Array(String)}, a.source)"
        params["source_names"] = selected
    rows = _query(
        "SELECT a.source, countDistinct(a.url_hash) AS article_count, "
        "round(avg(a.word_count), 1) AS avg_word_count "
        "FROM newspulse.raw_articles FINAL AS a "
        f"WHERE {where} GROUP BY a.source ORDER BY article_count DESC LIMIT 6",
        params,
    )
    if rows:
        answer = f"Số bài theo nguồn trong {_TIME_LABELS[time_range]}:\n" + "\n".join(
            f"- {row['source']}: {row['article_count']} bài, trung bình {row['avg_word_count']} từ/bài"
            for row in rows
        )
        answer += "\nĐây là số bài trong kỳ, chưa đo tốc độ đưa tin hay mức độ trùng lặp."
    else:
        answer = "Chưa có bài viết phù hợp để so sánh các nguồn."
    return ToolResult(
        answer=answer, tool="compare_sources", time_range=time_range,
        chart=_chart("Số bài theo nguồn", "bài viết", rows, "source", "article_count"),
    )


def _entities(request: ChatRequest, time_range: str) -> ToolResult:
    subject = _search_term(request)
    if not subject:
        match = re.search(r"(?:liên quan đến|lien quan den)\s+(.+)", request.message, re.IGNORECASE)
        subject = match.group(1).strip(" ?.!")[:120] if match else None
    where, params = _where(request, time_range)
    if subject:
        where += " AND target.entity ILIKE {entity_query:String} AND e.entity != target.entity"
        params["entity_query"] = f"%{subject}%"
        rows = _query(
            "SELECT e.entity AS entity_name, e.entity_type, "
            "countDistinct(a.url_hash) AS article_count "
            "FROM newspulse.raw_article_entities AS e "
            "INNER JOIN newspulse.raw_article_entities AS target ON e.url_hash = target.url_hash "
            "INNER JOIN newspulse.raw_articles FINAL AS a ON e.url_hash = a.url_hash "
            f"WHERE {where} GROUP BY e.entity, e.entity_type "
            "ORDER BY article_count DESC LIMIT 10",
            params,
        )
        heading = f"Thực thể cùng xuất hiện với {subject} trong {_TIME_LABELS[time_range]}"
    else:
        rows = _query(
            "SELECT e.entity AS entity_name, e.entity_type, "
            "countDistinct(a.url_hash) AS article_count "
            "FROM newspulse.raw_article_entities AS e "
            "INNER JOIN newspulse.raw_articles FINAL AS a ON e.url_hash = a.url_hash "
            f"WHERE {where} GROUP BY e.entity, e.entity_type "
            "ORDER BY article_count DESC LIMIT 10",
            params,
        )
        heading = f"Thực thể xuất hiện nhiều trong {_TIME_LABELS[time_range]}"
    if rows:
        answer = heading + ":\n" + "\n".join(
            f"- {row['entity_name']} ({row['entity_type']}): {row['article_count']} bài"
            for row in rows
        )
        if subject:
            answer += "\nCùng xuất hiện trong bài không chứng minh quan hệ trực tiếp."
    else:
        answer = "Chưa có dữ liệu thực thể phù hợp trong khoảng thời gian này."
    return ToolResult(
        answer=answer, tool="get_entities", time_range=time_range,
        chart=_chart("Số bài nhắc tới thực thể", "bài viết", rows, "entity_name", "article_count"),
    )


def _alerts(request: ChatRequest, time_range: str) -> ToolResult:
    if request.source or request.category or request.query or time_range != "7d":
        raise HTTPException(status_code=422, detail="Alert tool does not support these filters")
    rows = get_alerts(threshold=2.0, limit=5)
    if rows:
        answer = "Cảnh báo tăng đột biến số bài theo giờ trong 7 ngày qua:\n" + "\n".join(
            f"- {row['hour_slot']} (ID: {row.get('alert_id', 'n/a')}): "
            f"{row['article_count']} bài, z-score {row['z_score']}"
            for row in rows
        )
    else:
        answer = "Không có cảnh báo tăng đột biến số bài trong dữ liệu hiện tại."
    return ToolResult(answer=answer, tool="get_volume_alerts", time_range="7d")


def _rag(request: ChatRequest, time_range: str) -> ToolResult:
    query = request.query or request.message
    answer, sources = retrieve(
        query, time_range=time_range, source=request.source, category=request.category
    )
    return ToolResult(answer=answer, tool="search_article_content", sources=sources, time_range=time_range)


def answer_question(
    request: ChatRequest, actor: dict, previous_context: dict | None = None
) -> ToolResult:
    intent = _intent(request.message)
    followup = _is_followup(request.message) and previous_context is not None
    if followup and intent is None:
        intent = previous_context.get("intent")
    if followup and intent != "alerts":
        previous_time = previous_context.get("time_range", "7d")
        mentioned = _mentioned_sources(request.message)
        request = request.model_copy(update={
            "time_range": request.time_range or (
                _time_range(request) if _has_time_hint(request.message) else previous_time
            ),
            "source": request.source or (
                None if intent == "sources" else
                (mentioned[0] if mentioned else previous_context.get("source"))
            ),
            "category": request.category or previous_context.get("category"),
            "query": request.query or _search_term(request) or previous_context.get("query"),
        })
    if intent == "alerts" and "alerts.read" not in actor["permissions"]:
        raise HTTPException(status_code=403, detail="Forbidden: Missing permission 'alerts.read'")
    if intent in ("articles", "trending", "sentiment", "sources", "entities", "rag") and "dashboard.read" not in actor["permissions"]:
        raise HTTPException(status_code=403, detail="Forbidden: Missing permission 'dashboard.read'")
    if intent is None:
        return ToolResult(answer=(
            "Mình hỗ trợ tìm bài viết, từ khóa, cảm xúc, thực thể, so sánh nguồn, "
            "nội dung bài viết và cảnh báo tăng đột biến. Hãy hỏi rõ một trong các nội dung này."
        ))
    time_range = _time_range(request)
    result = {
        "articles": _articles,
        "trending": _trending,
        "sentiment": _sentiment,
        "sources": _sources,
        "entities": _entities,
        "alerts": _alerts,
        "rag": _rag,
    }[intent](request, time_range)
    result.queried_at = datetime.now(timezone.utc)
    result.context = {
        "intent": intent,
        "time_range": time_range,
        "source": request.source,
        "category": request.category,
        "query": _search_term(request),
    }
    return result
