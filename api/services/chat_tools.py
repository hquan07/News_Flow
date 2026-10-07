"""Read-only, bounded data tools available to the chatbot."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import HTTPException

from api.models.chat import ChatRequest
from api.services.analytics import _query, get_alerts
from api.services.rag_retrieval import retrieve
from api.services.event_clustering import event_detail
from api.services.briefing_service import citation_summary


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


@dataclass
class ChatPlan:
    request: ChatRequest
    intent: str | None
    time_range: str | None
    compare_sources: list[str] | None = None
    clarification: str | None = None


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn").replace("đ", "d")


def _intent(message: str) -> str | None:
    normalized = _normalized(message)
    if "tac gia" in normalized or "author" in normalized:
        if any(word in normalized for word in ("bai dang", "post", "binh luan")):
            return "social_authors"
        if any(word in normalized for word in ("bai bao", "bai viet", "tin")):
            return "article_authors"
        return "authors_unspecified"
    if any(word in normalized for word in ("canh bao", "alert", "khung hoang", "bat thuong")):
        return "alerts"
    if _asks_source_categories(normalized):
        return "source_categories"
    if any(word in normalized for word in (
        "so sanh nguon", "so sanh bao", "doi chieu nguon", "doi chieu bao",
        "doi chieu ", "khac nhau giua", "nguon nao", "bao nao", "compare sources",
    )):
        return "sources"
    if any(word in normalized for word in ("sentiment", "cam xuc", "tich cuc", "tieu cuc")):
        return "sentiment"
    if any(word in normalized for word in ("trending", "xu huong", "thinh hanh", "tu khoa", "chu de nao")):
        return "trending"
    count_cue = re.search(
        r"\b(?:tong so|tong cong|bao nhieu|so luong|so bai|dem|thong ke so|thong ke luong|count)\b",
        normalized,
    )
    if count_cue:
        if re.search(r"\b(?:bai dang|binh luan|post|social)\b", normalized):
            return "social_count"
        if re.search(r"\b(?:bai|tin|article|news)\b", normalized):
            return "article_count"
    if any(word in normalized for word in ("tom tat", "noi dung", "noi gi ve", "giai thich ve", "semantic", "tuong tu", "summarize")):
        return "rag"
    if any(word in normalized for word in (
        "bai viet", "bai bao", "tin moi", "tin tuc", "tim tin", "tim bai",
        "xem tin", "xem bai", "doc tin", "bai ve", "nhung tin", "articles",
    )):
        return "articles"
    if any(word in normalized for word in ("entity", "thuc the", "nhan vat", "to chuc nao", "dia danh", "lien quan den")):
        return "entities"
    return None


def _asks_source_categories(normalized: str) -> bool:
    return (
        any(term in normalized for term in ("category", "categories", "danh muc", "chuyen muc"))
        and any(term in normalized for term in ("so sanh", "doi chieu", "giua", "theo tung nguon"))
    )


def _event(request: ChatRequest, _time_range: str | None) -> ToolResult:
    event = event_detail(request.event_id or "", days=30)
    sources = [
        {
            "article_id": str(item["article_id"]), "title": item["title"],
            "url": item["url"], "source": item["source"],
            "published_at": item.get("published_at"),
        }
        for item in event["articles"][:8]
        if str(item.get("url", "")).startswith(("http://", "https://"))
    ]
    answer = (
        f"Sự kiện “{event['title']}” có {event['article_count']} bài từ "
        f"{len(event['sources'])} nguồn; phát hiện {event['duplicate_count']} bài gần trùng.\n"
        + "\n".join(f"{index}. {item['title']} ({item['source']})" for index, item in enumerate(sources, 1))
    )
    return ToolResult(answer=answer, tool="event_context", sources=sources)


def _time_hint(message: str) -> str | None:
    normalized = _normalized(message)
    if "hom nay" in normalized or "today" in normalized or "24 gio" in normalized:
        return "today"
    if "30 ngay" in normalized or "30d" in normalized or "thang qua" in normalized:
        return "30d"
    if "7 ngay" in normalized or "7d" in normalized or "tuan qua" in normalized or "tuan nay" in normalized:
        return "7d"
    return None


def _time_range(request: ChatRequest) -> str:
    return request.time_range or _time_hint(request.message) or "7d"


def _has_time_hint(message: str) -> bool:
    return _time_hint(message) is not None


def _is_followup(message: str) -> bool:
    normalized = _normalized(message).strip()
    return normalized.startswith(("con ", "the ", "vay ", "neu ", "so voi ", "tu nguon ", "nguon "))


def _asks_chart(message: str) -> bool:
    return "bieu do" in _normalized(message)


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

_SOURCE_LABELS = {
    "vnexpress": "VnExpress", "tuoitre": "Tuổi Trẻ", "thanhnien": "Thanh Niên",
    "dantri": "Dân Trí", "laodong": "Lao Động", "tienphong": "Tiền Phong",
}

_SOCIAL_SOURCE_GROUPS = {
    "voz": ("voz", "voz_forum"),
    "youtube": ("youtube", "youtube_comments"),
}
_SOCIAL_SOURCE_ALIASES = {
    "voz": "voz", "voz_forum": "voz",
    "youtube": "youtube", "you tube": "youtube", "youtube_comments": "youtube",
}


def _social_group(source: str | None) -> str | None:
    return _SOCIAL_SOURCE_ALIASES.get(_normalized(source).strip()) if source else None


def _mentioned_social_sources(message: str) -> list[str]:
    normalized = _normalized(message)
    return list(dict.fromkeys(
        group for alias, group in _SOCIAL_SOURCE_ALIASES.items()
        if re.search(rf"\b{re.escape(alias)}\b", normalized)
    ))


def _mentioned_sources(message: str) -> list[str]:
    normalized = _normalized(message)
    matches = [
        (match.start(), canonical)
        for alias, canonical in _SOURCE_NAMES.items()
        if (match := re.search(rf"\b{re.escape(alias)}\b", normalized))
    ]
    return list(dict.fromkeys(canonical for _, canonical in sorted(matches)))


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
    match = re.search(
        r"\b(?:về|ve|about|liên quan đến|lien quan den|đề cập đến|de cap den|nhắc đến|nhac den)\s+(.+)",
        request.message, re.IGNORECASE,
    )
    if not match:
        return None
    term = match.group(1).strip(" ?.!")
    term = re.sub(
        r"\s+(?:hôm nay|hom nay|tuần qua|tuan qua|tuần này|tuan nay|tháng qua|thang qua|trong\s+\d+\s+(?:ngày|ngay)(?:\s+qua)?)$",
        "",
        term,
        flags=re.IGNORECASE,
    )
    term = re.sub(
        r"\s+(?:từ|của|from)\s+(?:báo\s+)?(?:vnexpress|tuổi trẻ|tuoitre|thanh niên|thanhnien|dân trí|dantri|lao động|laodong|tiền phong|tienphong)$",
        "", term, flags=re.IGNORECASE,
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
    where, params = _where(request, time_range)
    if term:
        where += (
            " AND (a.title ILIKE {title_query:String} "
            "OR a.url_hash IN (SELECT url_hash FROM newspulse.raw_article_keywords "
            "WHERE lowerUTF8(keyword) = lowerUTF8({related_term:String})) "
            "OR a.url_hash IN (SELECT url_hash FROM newspulse.raw_article_entities "
            "WHERE lowerUTF8(entity) = lowerUTF8({related_term:String})))"
        )
        params.update(title_query=f"%{term}%", related_term=term)
    rows = _query(
        "SELECT a.url_hash AS article_id, a.title, a.url, a.source, "
        "a.publish_time AS published_at "
        "FROM newspulse.raw_articles AS a FINAL "
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
        heading = (
            f"Các bài viết mới nhất liên quan đến {term} trong {_TIME_LABELS[time_range]} "
            "(khớp tiêu đề, từ khóa hoặc thực thể):"
            if term else f"Các bài viết mới nhất trong {_TIME_LABELS[time_range]}:"
        )
        answer = heading + "\n" + "\n".join(
            f"{index}. {item['title']} ({item['source']})"
            for index, item in enumerate(sources, 1)
        )
        if "tom tat" in _normalized(request.message):
            answer += "\nHiện mình mới liệt kê bài phù hợp; chưa tóm tắt nội dung toàn văn."
    return ToolResult(answer=answer, tool="search_articles", sources=sources, time_range=time_range)


def _count_term(request: ChatRequest) -> str | None:
    term = _search_term(request)
    if term and request.source:
        term = re.sub(
            r"\s+(?:từ|của|from)\s+.+$",
            "", term, flags=re.IGNORECASE,
        ).strip()
    return term or None


def _article_count(request: ChatRequest, time_range: str) -> ToolResult:
    conditions = []
    params = {}
    if time_range != "all":
        conditions.append(f"a.publish_time >= now() - INTERVAL {_TIME_WINDOWS[time_range]}")
    if request.source:
        conditions.append("a.source = {source:String}")
        params["source"] = request.source.strip()
    if request.category:
        conditions.append("a.category = {category:String}")
        params["category"] = request.category.strip()
    term = _count_term(request)
    if term:
        conditions.append("a.title ILIKE {title_query:String}")
        params["title_query"] = f"%{term}%"
    where = " AND ".join(conditions) if conditions else "1 = 1"
    rows = _query(
        "SELECT count() AS article_count FROM newspulse.raw_articles AS a FINAL "
        f"WHERE {where}",
        params,
    )
    count = int(rows[0]["article_count"]) if rows else 0
    scope = f" từ {request.source}" if request.source else " từ tất cả nguồn"
    period = "từ trước đến nay" if time_range == "all" else f"trong {_TIME_LABELS[time_range]}"
    topic = f" có tiêu đề chứa '{term}'" if term else ""
    formatted_count = f"{count:,}".replace(",", ".")
    answer = f"Đã thu thập {formatted_count} bài báo{scope}{topic} {period}."
    if request.category:
        answer += f" Danh mục: {request.category}."
    return ToolResult(answer=answer, tool="count_articles", time_range=time_range)


def _social_count(request: ChatRequest, time_range: str) -> ToolResult:
    group = _social_group(request.source)
    if group is None:
        raise HTTPException(status_code=422, detail="Choose a supported social source")
    where = "source IN {source_names:Array(String)}"
    params = {"source_names": list(_SOCIAL_SOURCE_GROUPS[group])}
    if time_range != "all":
        where += f" AND publish_time >= now() - INTERVAL {_TIME_WINDOWS[time_range]}"
    rows = _query(
        "SELECT uniqExact(source, post_id) AS post_count, count() AS record_count "
        f"FROM newspulse.social_sentiment_metrics WHERE {where}",
        params,
    )
    count = int(rows[0]["post_count"]) if rows else 0
    formatted_count = f"{count:,}".replace(",", ".")
    record_count = int(rows[0].get("record_count", count)) if rows else 0
    formatted_records = f"{record_count:,}".replace(",", ".")
    period = "từ trước đến nay" if time_range == "all" else f"trong {_TIME_LABELS[time_range]}"
    answer = (
        f"Có {formatted_count} bài đăng/bình luận social duy nhất từ nhóm nguồn "
        f"{group.upper() if group == 'voz' else 'YouTube'} {period} "
        f"(gồm {', '.join(_SOCIAL_SOURCE_GROUPS[group])}). "
        f"Bảng lưu {formatted_records} bản ghi thu thập; số duy nhất được tính theo nguồn và post_id. "
        "Đây không phải số bài báo."
    )
    return ToolResult(answer=answer, tool="count_social_posts", time_range=time_range)


def _author_answer(rows: list[dict], *, kind: str, time_range: str, source_label: str) -> ToolResult:
    tool = "rank_social_authors" if kind == "social" else "rank_article_authors"
    visible = rows[:10]
    if not visible:
        data_label = "bài đăng/bình luận social" if kind == "social" else "bài báo"
        return ToolResult(
            answer=f"Chưa có dữ liệu tác giả {data_label} phù hợp trong {_TIME_LABELS[time_range]}.",
            tool=tool, time_range=time_range,
        )
    unit = "bài đăng/bình luận duy nhất" if kind == "social" else "bài báo duy nhất"
    headline_unit = "bài đăng/bình luận" if kind == "social" else "bài báo"
    answer = (
        f"Tác giả có nhiều {headline_unit} nhất từ {source_label} trong {_TIME_LABELS[time_range]} "
        f"(tối đa 10 tác giả):\n"
        + "\n".join(
            f"{index}. {row['author']}: {row['post_count']} {unit}"
            for index, row in enumerate(visible, 1)
        )
    )
    if len(visible) > 1 and visible[0]["post_count"] == visible[1]["post_count"]:
        answer += "\nCó tác giả đồng hạng ở vị trí đầu."
    if len(rows) > 10:
        answer += "\nDanh sách được giới hạn 10 người."
        if rows[10]["post_count"] == visible[-1]["post_count"]:
            answer += " Còn tác giả đồng hạng ngoài danh sách."
    if kind == "social":
        answer += "\nDữ liệu social có thể gồm dữ liệu thử nghiệm; một post_id được tính một lần trong mỗi nguồn."
    return ToolResult(
        answer=answer, tool=tool, time_range=time_range,
        chart=_chart("Tác giả theo số bài đăng" if kind == "social" else "Tác giả theo số bài báo", unit, visible, "author", "post_count"),
    )


def _social_authors(request: ChatRequest, time_range: str) -> ToolResult:
    where = ["length(trimBoth(author)) > 0", f"publish_time >= now() - INTERVAL {_TIME_WINDOWS[time_range]}"]
    params = {}
    if request.source:
        group = _social_group(request.source)
        if group is None:
            raise HTTPException(status_code=422, detail="Choose a supported social source")
        where.append("source IN {source_names:Array(String)}")
        params["source_names"] = list(_SOCIAL_SOURCE_GROUPS[group])
    rows = _query(
        "SELECT trimBoth(author) AS author, uniqExact(source, post_id) AS post_count "
        "FROM newspulse.social_sentiment_metrics WHERE " + " AND ".join(where) +
        " GROUP BY author ORDER BY post_count DESC, author ASC LIMIT 11",
        params,
    )
    label = f"nhóm nguồn {request.source}" if request.source else "tất cả nguồn social"
    return _author_answer(rows, kind="social", time_range=time_range, source_label=label)


def _article_authors(request: ChatRequest, time_range: str) -> ToolResult:
    where, params = _where(request, time_range, title_query=_search_term(request))
    where += " AND length(trimBoth(a.author)) > 0"
    rows = _query(
        "SELECT trimBoth(a.author) AS author, countDistinct(a.url_hash) AS post_count "
        "FROM newspulse.raw_articles AS a FINAL "
        f"WHERE {where} GROUP BY author ORDER BY post_count DESC, author ASC LIMIT 11",
        params,
    )
    label = request.source or "tất cả nguồn báo"
    return _author_answer(rows, kind="báo", time_range=time_range, source_label=label)


def _trending(request: ChatRequest, time_range: str) -> ToolResult:
    where, params = _where(request, time_range)
    keyword_query = _search_term(request)
    if keyword_query:
        where += " AND k.keyword ILIKE {keyword_query:String}"
        params["keyword_query"] = f"%{keyword_query}%"
    rows = _query(
        "SELECT k.keyword, countDistinct(a.url_hash) AS count "
        "FROM newspulse.raw_article_keywords AS k "
        "INNER JOIN newspulse.raw_articles AS a FINAL ON k.url_hash = a.url_hash "
        f"WHERE {where} GROUP BY k.keyword ORDER BY count DESC LIMIT 10",
        params,
    )
    title_fallback = not rows
    if title_fallback:
        # NLP enrichment is optional. Use a bounded, explicitly labeled title
        # frequency when there are no indexed keywords for the requested period.
        title_where, title_params = _where(request, time_range)
        title_params.update({
            "title_pattern": r"[\p{L}]{2,}",
            "excluded_phrases": [
                "báo dân", "dân trí", "báo lao", "lao động", "tuổi trẻ",
                "thanh niên", "tin tức", "hôm nay", "tuyển việt",
            ],
        })
        phrase_filter = "keyword NOT IN {excluded_phrases:Array(String)}"
        if keyword_query:
            phrase_filter += " AND keyword ILIKE {keyword_query:String}"
            title_params["keyword_query"] = f"%{keyword_query}%"
        rows = _query(
            "SELECT keyword, countDistinct(article_id) AS count FROM ("
            "SELECT a.url_hash AS article_id, "
            "arrayJoin(arrayMap(pair -> concat(pair.1, char(32), pair.2), "
            "arrayZip(arrayPopBack(extractAll(lowerUTF8(a.title), {title_pattern:String})), "
            "arrayPopFront(extractAll(lowerUTF8(a.title), {title_pattern:String}))))) AS keyword "
            "FROM (SELECT a.url_hash, a.title FROM newspulse.raw_articles AS a FINAL "
            f"WHERE {title_where} ORDER BY a.publish_time DESC LIMIT 3000) AS a) "
            f"WHERE {phrase_filter} GROUP BY keyword ORDER BY count DESC LIMIT 10",
            title_params,
        )
    if rows:
        heading = (
            f"Các cụm từ xuất hiện nhiều trong tiêu đề của tối đa 3.000 bài mới nhất trong {_TIME_LABELS[time_range]} "
            "(chưa có dữ liệu từ khóa NLP):"
            if title_fallback else
            f"Từ khóa xuất hiện nhiều trong bài viết trong {_TIME_LABELS[time_range]}:"
        )
        answer = heading + "\n" + "\n".join(
            f"{index}. {row['keyword']}: {row['count']} bài"
            for index, row in enumerate(rows, 1)
        )
        answer += (
            "\nĐây là tần suất cụm từ trong tiêu đề, không phải tốc độ tăng so với kỳ trước."
            if title_fallback else
            "\nĐây là tần suất trong khoảng chọn, chưa phải tốc độ tăng so với kỳ trước."
        )
    else:
        answer = "Chưa có dữ liệu từ khóa hoặc cụm từ tiêu đề phù hợp trong khoảng thời gian này."
    return ToolResult(
        answer=answer, tool="get_trending_keywords", time_range=time_range,
        chart=_chart("Tần suất cụm từ tiêu đề" if title_fallback else "Tần suất từ khóa", "bài viết", rows, "keyword", "count"),
    )


def _sentiment(request: ChatRequest, time_range: str) -> ToolResult:
    where, params = _where(request, time_range, title_query=_search_term(request))
    rows = _query(
        "SELECT lowerUTF8(s.sentiment_label) AS sentiment_label, "
        "countDistinct(a.url_hash) AS count "
        "FROM newspulse.raw_articles AS a FINAL "
        "INNER JOIN newspulse.raw_article_sentiment AS s FINAL "
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
        "FROM newspulse.raw_articles AS a FINAL "
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


def _source_categories(request: ChatRequest, time_range: str) -> ToolResult:
    selected = request.compare_sources or _mentioned_sources(request.message)
    where = f"a.publish_time >= now() - INTERVAL {_TIME_WINDOWS[time_range]}"
    rows = _query(
        "SELECT a.source, a.category, countDistinct(a.url_hash) AS article_count "
        "FROM newspulse.raw_articles AS a FINAL "
        f"WHERE {where} AND a.source IN {{source_names:Array(String)}} "
        "GROUP BY a.source, a.category ORDER BY article_count DESC LIMIT 101",
        {"source_names": selected},
    )
    if not rows:
        return ToolResult(
            answer="Chưa có bài báo thuộc hai nguồn này trong khoảng thời gian đã chọn.",
            tool="compare_source_categories", time_range=time_range,
        )
    if len(rows) > 100:
        return ToolResult(
            answer="Có quá nhiều nhóm danh mục để so sánh đầy đủ. Hãy chọn khoảng thời gian ngắn hơn.",
            tool="compare_source_categories", time_range=time_range,
        )
    by_category: dict[str, dict[str, int]] = {}
    for row in rows:
        category = str(row["category"]).strip() or "(trống)"
        by_category.setdefault(category, {})[str(row["source"])] = int(row["article_count"])
    ranked = sorted(by_category, key=lambda category: (-sum(by_category[category].values()), category))
    lines = [
        f"- {category}: " + "; ".join(
            f"{_SOURCE_LABELS.get(source, source)} {by_category[category].get(source, 0):,}".replace(",", ".")
            for source in selected
        )
        for category in ranked[:12]
    ]
    answer = (
        f"Số bài báo theo danh mục của {_SOURCE_LABELS.get(selected[0], selected[0])} và "
        f"{_SOURCE_LABELS.get(selected[1], selected[1])} trong {_TIME_LABELS[time_range]} "
        "(đếm bài duy nhất theo nguồn và category):\n" + "\n".join(lines)
    )
    if len(ranked) > 12:
        answer += "\nChỉ hiển thị tối đa 12 danh mục có nhiều bài nhất."
    if "general" in by_category:
        answer += "\n‘general’ là nhãn category trong dữ liệu, không phải một chủ đề cụ thể."
    specific_categories = [category for category in ranked if category != "general"]
    chart_categories = (specific_categories or ranked)[:10]
    chart = {
        "type": "grouped_bar",
        "title": "So sánh danh mục" + (" (không gồm general)" if specific_categories and "general" in by_category else ""),
        "unit": "bài báo",
        "series": [{"key": source, "label": _SOURCE_LABELS.get(source, source)} for source in selected],
        "points": [
            {"label": category, "values": {source: by_category[category].get(source, 0) for source in selected}}
            for category in chart_categories
        ],
    }
    return ToolResult(answer=answer, tool="compare_source_categories", time_range=time_range, chart=chart)


def _entity_subject(request: ChatRequest) -> str | None:
    subject = _search_term(request)
    if not subject:
        match = re.search(r"(?:liên quan đến|lien quan den)\s+(.+)", request.message, re.IGNORECASE)
        subject = match.group(1).strip(" ?.!")[:120] if match else None
    return subject


def _entities(request: ChatRequest, time_range: str) -> ToolResult:
    subject = _entity_subject(request)
    where, params = _where(request, time_range)
    if subject:
        where += " AND target.entity ILIKE {entity_query:String} AND e.entity != target.entity"
        params["entity_query"] = f"%{subject}%"
        rows = _query(
            "SELECT e.entity AS entity_name, e.entity_type, "
            "countDistinct(a.url_hash) AS article_count "
            "FROM newspulse.raw_article_entities AS e "
            "INNER JOIN newspulse.raw_article_entities AS target ON e.url_hash = target.url_hash "
            "INNER JOIN newspulse.raw_articles AS a FINAL ON e.url_hash = a.url_hash "
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
            "INNER JOIN newspulse.raw_articles AS a FINAL ON e.url_hash = a.url_hash "
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
    return ToolResult(answer=citation_summary(answer, sources), tool="search_article_content", sources=sources, time_range=time_range)


def plan_question(request: ChatRequest, previous_context: dict | None = None) -> ChatPlan:
    """Resolve intent and scope without touching a data service."""
    intent = _intent(request.message)
    social_mentioned = _mentioned_social_sources(request.message)
    pending = bool(previous_context and previous_context.get("clarification"))
    followup = previous_context is not None and (
        _is_followup(request.message) or pending
        or (previous_context.get("intent") == "source_categories" and _asks_chart(request.message))
    )
    if followup and intent is None:
        intent = previous_context.get("intent")
    if followup and previous_context.get("intent") in ("sources", "source_categories") and _asks_source_categories(
        _normalized(request.message)
    ):
        intent = "source_categories"
    if followup and previous_context.get("intent") == "authors_unspecified":
        normalized_reply = _normalized(request.message)
        if "bai dang" in normalized_reply or "binh luan" in normalized_reply or "social" in normalized_reply:
            intent = "social_authors"
        elif "bai bao" in normalized_reply or "bai viet" in normalized_reply:
            intent = "article_authors"
    if followup and intent != "alerts":
        previous_time = previous_context.get("time_range")
        mentioned = _mentioned_sources(request.message)
        previous_source = previous_context.get("source")
        if intent in ("articles", "article_count", "article_authors", "trending", "sentiment", "entities", "rag") and _social_group(previous_source):
            previous_source = None
        if intent in ("social_count", "social_authors") and previous_source and not _social_group(previous_source):
            previous_source = None
        inherited_time = previous_time if previous_time in ("today", "7d", "30d") or (
            previous_time == "all" and intent in ("article_count", "social_count")
        ) else None
        request = request.model_copy(update={
            "time_range": request.time_range or _time_hint(request.message) or inherited_time,
            "source": request.source or (
                None if intent in ("sources", "source_categories") else
                (social_mentioned[0] if len(social_mentioned) == 1 else
                 mentioned[0] if len(mentioned) == 1 else previous_source)
            ),
            "category": request.category or previous_context.get("category"),
            "query": request.query or _search_term(request) or previous_context.get("query"),
            "compare_sources": request.compare_sources or (
                None if mentioned else previous_context.get("compare_sources")
            ),
        })
    mentioned = _mentioned_sources(request.message)
    if intent in ("article_count", "social_count") and (social_mentioned or _social_group(request.source)):
        intent = "social_count"
    clarification = None
    if intent == "authors_unspecified":
        clarification = "Bạn muốn xếp hạng tác giả bài báo hay tác giả bài đăng/bình luận social?"
    elif intent == "social_authors":
        if not request.source and len(social_mentioned) == 1:
            request = request.model_copy(update={"source": social_mentioned[0]})
        if len(social_mentioned) > 1 or mentioned:
            clarification = "Hãy chọn một nguồn social (VOZ hoặc YouTube), hoặc hỏi tất cả nguồn social."
        elif request.source and _social_group(request.source) is None:
            clarification = "Nguồn này không thuộc dữ liệu social đang hỗ trợ. Hãy chọn VOZ hoặc YouTube."
        elif request.source and social_mentioned and _social_group(request.source) not in social_mentioned:
            clarification = "Nguồn trong câu hỏi khác bộ lọc đang chọn. Hãy chọn lại nguồn hoặc sửa câu hỏi."
        elif request.category or request.query or _search_term(request):
            clarification = "Hiện thống kê tác giả social chỉ hỗ trợ lọc theo nguồn và thời gian, chưa lọc danh mục hoặc chủ đề."
        elif request.source:
            request = request.model_copy(update={"source": _social_group(request.source)})
    elif intent == "social_count":
        if not request.source and len(social_mentioned) == 1:
            request = request.model_copy(update={"source": social_mentioned[0]})
        if len(social_mentioned) > 1 or (mentioned and social_mentioned):
            clarification = "Bạn muốn đếm nguồn social nào? Hãy chọn riêng VOZ hoặc YouTube."
        elif request.source and social_mentioned and _social_group(request.source) not in social_mentioned:
            clarification = "Nguồn trong câu hỏi khác bộ lọc đang chọn. Hãy chọn lại nguồn hoặc sửa câu hỏi."
        elif not _social_group(request.source):
            clarification = "VOZ và YouTube là nguồn social. Bạn muốn đếm nguồn nào?"
        elif request.category or request.query or _search_term(request):
            clarification = "Hiện chỉ hỗ trợ đếm toàn bộ dữ liệu social theo nguồn và thời gian, chưa lọc danh mục hoặc chủ đề."
        else:
            request = request.model_copy(update={"source": _social_group(request.source)})
    elif intent not in ("sources", "source_categories", "alerts") and not request.source:
        if len(mentioned) == 1:
            request = request.model_copy(update={"source": mentioned[0]})
        elif len(mentioned) > 1 and intent == "article_count":
            clarification = "Bạn muốn đếm gộp hai nguồn hay so sánh từng nguồn? Hãy nêu rõ yêu cầu."

    if intent not in ("sources", "source_categories", "alerts", "social_count", "social_authors") and request.source and mentioned and request.source not in mentioned:
        clarification = "Nguồn trong câu hỏi khác bộ lọc đang chọn. Hãy chọn lại nguồn hoặc sửa câu hỏi."
    explicit_time = _time_hint(request.message)
    if request.time_range and explicit_time and request.time_range != explicit_time:
        clarification = "Khoảng thời gian trong câu hỏi khác bộ lọc đang chọn. Hãy chọn lại khoảng thời gian hoặc sửa câu hỏi."

    selected_sources = None
    if intent in ("sources", "source_categories"):
        selected_sources = request.compare_sources or mentioned or None
        if request.source:
            clarification = "Hãy bỏ bộ lọc một nguồn khi muốn so sánh nhiều nguồn."
        elif intent == "source_categories" and (request.category or request.query or _search_term(request)):
            clarification = "Hãy bỏ bộ lọc danh mục hoặc chủ đề để so sánh toàn bộ danh mục giữa hai nguồn."
        elif intent == "source_categories" and (not selected_sources or len(selected_sources) != 2):
            clarification = "Bạn muốn so sánh danh mục của hai nguồn báo nào? Ví dụ: Thanh Niên và Tuổi Trẻ."
        elif not selected_sources or len(selected_sources) < 2:
            clarification = "Bạn muốn so sánh hai nguồn nào? Ví dụ: So sánh VnExpress và Tuổi Trẻ trong 7 ngày qua."
    elif intent == "article_count" and not clarification:
        normalized = _normalized(request.message)
        explicit_all = any(phrase in normalized for phrase in ("tat ca nguon", "toan bo", "tat ca bai"))
        if not request.source and not request.category and not request.time_range and not explicit_time and not explicit_all:
            clarification = "Bạn muốn đếm bài từ nguồn nào, trong khoảng thời gian nào? Có thể nói 'tất cả nguồn từ trước đến nay'."
    elif intent == "rag" and not (request.query or _search_term(request)):
        clarification = "Bạn muốn tìm nội dung về chủ đề nào? Ví dụ: Tóm tắt nội dung về lãi suất trong 7 ngày qua."

    if clarification:
        return ChatPlan(request, intent, None, selected_sources, clarification)
    time_range = None if intent is None else (
        "all" if intent in ("article_count", "social_count") and not request.time_range
        and not explicit_time else _time_range(request)
    )
    return ChatPlan(request, intent, time_range, selected_sources)


def answer_question(
    request: ChatRequest, actor: dict, previous_context: dict | None = None
) -> ToolResult:
    if request.event_id:
        result = _event(request, None)
        result.queried_at = datetime.now(timezone.utc)
        result.context = {
            "intent": "event", "time_range": None, "source": None,
            "compare_sources": None, "category": None, "query": None,
            "clarification": False, "event_id": request.event_id,
            "watchlist_id": request.watchlist_id,
        }
        return result
    plan = plan_question(request, previous_context)
    request, intent, time_range = plan.request, plan.intent, plan.time_range
    if intent == "alerts" and "alerts.read" not in actor["permissions"]:
        raise HTTPException(status_code=403, detail="Forbidden: Missing permission 'alerts.read'")
    if intent in ("articles", "article_count", "social_count", "social_authors", "article_authors", "authors_unspecified", "trending", "sentiment", "sources", "source_categories", "entities", "rag") and "dashboard.read" not in actor["permissions"]:
        raise HTTPException(status_code=403, detail="Forbidden: Missing permission 'dashboard.read'")
    if intent is None:
        return ToolResult(answer=(
            "Mình hỗ trợ tìm bài viết, từ khóa, cảm xúc, thực thể, so sánh nguồn, "
            "nội dung bài viết và cảnh báo tăng đột biến. Hãy hỏi rõ một trong các nội dung này."
        ))
    if plan.clarification:
        return ToolResult(
            answer=plan.clarification,
            tool="clarify_scope",
            context={
                "intent": intent, "time_range": request.time_range,
                "source": request.source, "compare_sources": plan.compare_sources,
                "category": request.category, "query": request.query or _search_term(request),
                "clarification": True,
            },
        )
    result = {
        "articles": _articles,
        "article_count": _article_count,
        "social_count": _social_count,
        "social_authors": _social_authors,
        "article_authors": _article_authors,
        "trending": _trending,
        "sentiment": _sentiment,
        "sources": _sources,
        "source_categories": _source_categories,
        "entities": _entities,
        "alerts": _alerts,
        "rag": _rag,
    }[intent](request, time_range)
    result.queried_at = datetime.now(timezone.utc)
    result.context = {
        "intent": intent,
        "time_range": time_range,
        "source": request.source,
        "compare_sources": plan.compare_sources,
        "category": request.category,
        "query": (
            _count_term(request) if intent == "article_count" else
            _entity_subject(request) if intent == "entities" else
            _search_term(request)
        ),
        "clarification": False,
        "event_id": request.event_id,
        "watchlist_id": request.watchlist_id,
    }
    return result
