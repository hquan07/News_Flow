"""Hybrid article retrieval with ClickHouse as the final authority for citations."""

import re
from datetime import datetime, timedelta, timezone

from api.config import get_settings
from api.exceptions import DependencyUnavailableError
from api.services.analytics import _query
from api.services import chat_embed_cache, rag_client


_DAYS = {"today": 1, "7d": 7, "30d": 30}


def _keywords(query: str) -> list[str]:
    words = re.findall(r"[\wÀ-ỹ]+", query.casefold())
    ignored = {"cho", "toi", "tôi", "các", "bài", "viết", "tin", "tức", "về", "trong", "những", "hãy", "tóm", "tắt", "theo", "của", "là", "what", "about", "summarize"}
    return [word for word in words if len(word) >= 3 and word not in ignored][:6]


def _keyword_candidates(query: str, since: datetime, source: str | None, category: str | None) -> list[str]:
    terms = _keywords(query)
    if not terms:
        return []
    where = ["a.publish_time >= {since:DateTime}"]
    params = {"since": since}
    if source:
        where.append("a.source = {source:String}")
        params["source"] = source
    if category:
        where.append("a.category = {category:String}")
        params["category"] = category
    matches = []
    for index, term in enumerate(terms):
        params[f"term{index}"] = f"%{term}%"
        matches.append(f"(a.title ILIKE {{term{index}:String}} OR a.content ILIKE {{term{index}:String}})")
    where.append("(" + " OR ".join(matches) + ")")
    rows = _query(
        "SELECT a.url_hash AS article_id FROM newspulse.raw_articles FINAL AS a "
        "WHERE " + " AND ".join(where) + " ORDER BY a.publish_time DESC LIMIT 12",
        params,
    )
    return [str(row["article_id"]) for row in rows]


def _current_articles(ids: list[str], since: datetime, source: str | None, category: str | None) -> dict[str, dict]:
    if not ids:
        return {}
    where = ["a.url_hash IN {ids:Array(String)}", "a.publish_time >= {since:DateTime}"]
    params = {"ids": ids, "since": since}
    if source:
        where.append("a.source = {source:String}")
        params["source"] = source
    if category:
        where.append("a.category = {category:String}")
        params["category"] = category
    rows = _query(
        "SELECT a.url_hash AS article_id, a.title, a.content, a.url, a.source, "
        "a.category, a.publish_time AS published_at "
        "FROM newspulse.raw_articles FINAL AS a WHERE " + " AND ".join(where) +
        " LIMIT 32",
        params,
    )
    return {str(row["article_id"]): row for row in rows
            if str(row.get("url", "")).startswith(("https://", "http://"))}


def _excerpt(content: str, query: str) -> str:
    text = " ".join(content.split())
    if not text:
        return ""
    position = 0
    for term in _keywords(query):
        found = text.casefold().find(term)
        if found >= 0:
            position = found
            break
    start = max(0, position - 70)
    return ("…" if start else "") + text[start:start + 320].strip() + ("…" if start + 320 < len(text) else "")


def retrieve(query: str, *, time_range: str, source: str | None, category: str | None) -> tuple[str, list[dict]]:
    if not get_settings().RAG_ENABLED:
        return "Tìm kiếm ngữ nghĩa chưa được bật. Quản trị viên cần khởi động dịch vụ RAG và lập chỉ mục bài viết.", []
    since = datetime.now(timezone.utc) - timedelta(days=_DAYS[time_range])
    degraded = False
    try:
        vector = chat_embed_cache.query_vector(query[:2000])
        vector_hits = rag_client.query_chunks(vector, source=source, category=category, since=since)
    except DependencyUnavailableError:
        # Keyword search remains useful when optional embedding/vector services fail.
        degraded = True
        vector_hits = []
    keyword_ids = _keyword_candidates(query, since, source, category)
    scores: dict[str, float] = {}
    snippets: dict[str, str] = {}
    seen = set()
    for rank, hit in enumerate(vector_hits, 1):
        payload = hit.get("payload") or {}
        article_id = str(payload.get("article_id", ""))
        if not article_id or article_id in seen:
            continue
        seen.add(article_id)
        scores[article_id] = scores.get(article_id, 0) + 1 / (60 + rank)
        snippets[article_id] = str(payload.get("text", ""))
    for rank, article_id in enumerate(keyword_ids, 1):
        scores[article_id] = scores.get(article_id, 0) + 1 / (60 + rank)
    articles = _current_articles(list(scores), since, source, category)
    ranked = sorted(articles, key=lambda key: scores[key], reverse=True)[:5]
    sources = []
    lines = []
    for index, article_id in enumerate(ranked, 1):
        row = articles[article_id]
        content = " ".join((row.get("content") or "").split())
        if not content:
            continue
        vector_snippet = " ".join(snippets.get(article_id, "").split())
        excerpt = vector_snippet[:320] if vector_snippet and vector_snippet in content else _excerpt(content, query)
        if not excerpt:
            continue
        sources.append({
            "article_id": article_id, "title": row["title"], "url": row["url"],
            "source": row["source"], "published_at": row["published_at"],
        })
        lines.append(f"[{len(sources)}] {row['title']} ({row['source']}): {excerpt}")
    if not sources:
        message = "Chưa tìm thấy nội dung bài viết phù hợp trong phạm vi và thời gian đã chọn."
        if degraded:
            message += " Tìm kiếm ngữ nghĩa tạm thời không khả dụng; đã thử tìm theo từ khóa."
        return message, []
    prefix = "Tìm kiếm ngữ nghĩa tạm thời không khả dụng; chỉ tìm theo từ khóa.\n" if degraded else ""
    return prefix + "Các đoạn liên quan từ bài viết đã đối chiếu với dữ liệu gốc:\n" + "\n".join(lines) + "\nĐây là trích đoạn, chưa phải bản tóm tắt do AI suy luận.", sources
