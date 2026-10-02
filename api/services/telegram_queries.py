import asyncio
from dataclasses import dataclass
from datetime import datetime

from api.models.telegram import TelegramQueryRequest
from api.services.analytics import (
    get_alerts,
    get_overview,
    get_source_comparison,
    get_trending_keywords,
)
from api.services.health import dependency_health

TIME_RANGE_ALIASES = {
    "today": "today",
    "24h": "today",
    "1d": "today",
    "7d": "7d",
    "week": "7d",
    "30d": "30d",
    "month": "30d",
    "all": "all",
}


@dataclass(frozen=True)
class TelegramQueryResponse:
    text: str
    command: str


class TelegramQueryService:
    async def execute(
        self,
        request: TelegramQueryRequest,
    ) -> TelegramQueryResponse:
        handlers = {
            "start": self._help,
            "help": self._help,
            "alerts": self._alerts,
            "trend": self._trend,
            "source": self._source,
            "report": self._report,
            "status": self._status,
        }
        if request.command == "query":
            return TelegramQueryResponse(
                "Mình chưa hiểu câu hỏi này. Gửi /help để xem các truy vấn hỗ trợ.",
                "query",
            )
        handler = handlers.get(request.command)
        if handler is None:
            return TelegramQueryResponse(
                f"Lệnh /{request.command} chưa được hỗ trợ. Gửi /help để xem danh sách lệnh.",
                request.command,
            )
        return await handler(request)

    async def _help(self, _request: TelegramQueryRequest) -> TelegramQueryResponse:
        return TelegramQueryResponse(
            "🤖 NewsPulse tra cứu read-only\n\n"
            "/alerts [số_lượng] — cảnh báo volume spike\n"
            "/trend [24h|7d|30d] [số_lượng] — từ khóa nổi bật\n"
            "/source <tên_nguồn> [24h|7d|30d] — thống kê một nguồn\n"
            "/report [24h|7d|30d] — tổng quan dữ liệu\n"
            "/status — trạng thái ClickHouse và MongoDB\n"
            "/help — hướng dẫn này",
            "help",
        )

    async def _alerts(self, request: TelegramQueryRequest) -> TelegramQueryResponse:
        limit = _parse_limit(request.args[0] if request.args else None, default=5)
        rows = await asyncio.to_thread(get_alerts, threshold=2.0, limit=limit)
        if not rows:
            return TelegramQueryResponse(
                "✅ Không phát hiện volume spike trong baseline 7 ngày.",
                "alerts",
            )

        lines = ["🚨 Volume spike gần đây:"]
        for row in rows:
            hour = _format_datetime(row.get("hour_slot"))
            lines.append(
                f"• {hour}: {int(row.get('article_count') or 0):,} bài "
                f"(z={float(row.get('z_score') or 0):.1f})"
            )
        return TelegramQueryResponse("\n".join(lines), "alerts")

    async def _trend(self, request: TelegramQueryRequest) -> TelegramQueryResponse:
        time_range = _parse_time_range(request.args[0] if request.args else None)
        limit_arg = request.args[1] if len(request.args) > 1 else None
        limit = _parse_limit(limit_arg, default=10)
        rows = await asyncio.to_thread(
            get_trending_keywords,
            time_range=time_range,
            limit=limit,
        )
        if not rows:
            return TelegramQueryResponse(
                f"Chưa có từ khóa nổi bật trong khoảng {time_range}.",
                "trend",
            )

        lines = [f"🔥 Top từ khóa ({time_range}):"]
        for index, row in enumerate(rows, start=1):
            lines.append(
                f"{index}. {row.get('keyword', 'N/A')} — "
                f"{int(row.get('count') or 0):,} lần"
            )
        return TelegramQueryResponse("\n".join(lines), "trend")

    async def _source(self, request: TelegramQueryRequest) -> TelegramQueryResponse:
        if not request.args:
            return TelegramQueryResponse(
                "Thiếu tên nguồn. Ví dụ: /source vnexpress 7d",
                "source",
            )
        source = request.args[0].lower()
        time_range = _parse_time_range(
            request.args[1] if len(request.args) > 1 else None
        )
        rows = await asyncio.to_thread(
            get_source_comparison,
            time_range=time_range,
            source=source,
        )
        if not rows:
            return TelegramQueryResponse(
                f"Không có dữ liệu cho nguồn {source} trong khoảng {time_range}.",
                "source",
            )

        total = sum(int(row.get("total_articles") or 0) for row in rows)
        weighted_words = sum(
            float(row.get("avg_word_count") or 0)
            * int(row.get("total_articles") or 0)
            for row in rows
        )
        avg_words = weighted_words / total if total else 0
        categories = sorted(
            {
                str(row.get("top_category"))
                for row in rows
                if row.get("top_category")
            }
        )
        return TelegramQueryResponse(
            f"📰 Nguồn {source} ({time_range})\n"
            f"• Số bài: {total:,}\n"
            f"• Độ dài trung bình: {avg_words:.0f} từ\n"
            f"• Chủ đề ghi nhận: {', '.join(categories) or 'N/A'}",
            "source",
        )

    async def _report(self, request: TelegramQueryRequest) -> TelegramQueryResponse:
        time_range = _parse_time_range(request.args[0] if request.args else None)
        rows = await asyncio.to_thread(get_overview, time_range=time_range)
        if not rows:
            return TelegramQueryResponse(
                f"Chưa có dữ liệu tổng quan trong khoảng {time_range}.",
                "report",
            )

        total = sum(int(row.get("article_count") or 0) for row in rows)
        sources = {row.get("source") for row in rows if row.get("source")}
        category_counts: dict[str, int] = {}
        latency_sum = 0.0
        latency_count = 0
        for row in rows:
            count = int(row.get("article_count") or 0)
            category = str(row.get("category") or "unknown")
            category_counts[category] = category_counts.get(category, 0) + count
            latency = row.get("avg_crawl_latency")
            if latency is not None:
                latency_sum += float(latency) * count
                latency_count += count
        top_category = max(category_counts, key=category_counts.get)
        avg_latency = latency_sum / latency_count if latency_count else 0
        return TelegramQueryResponse(
            f"📊 Tổng quan ({time_range})\n"
            f"• Bài báo: {total:,}\n"
            f"• Nguồn hoạt động: {len(sources)}\n"
            f"• Chủ đề nhiều nhất: {top_category}\n"
            f"• Độ trễ crawl trung bình: {avg_latency:.1f} phút",
            "report",
        )

    async def _status(self, _request: TelegramQueryRequest) -> TelegramQueryResponse:
        result = await dependency_health()
        lines = [f"🩺 Hệ thống: {result['status']}"]
        for name, service in result.get("services", {}).items():
            icon = "✅" if service.get("status") == "healthy" else "❌"
            latency = service.get("latency_ms")
            suffix = f" — {latency:.1f} ms" if latency is not None else ""
            lines.append(f"• {icon} {name}: {service.get('status')}{suffix}")
        return TelegramQueryResponse("\n".join(lines), "status")


def _parse_time_range(value: str | None, default: str = "7d") -> str:
    if value is None:
        return default
    return TIME_RANGE_ALIASES.get(value.lower(), default)


def _parse_limit(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return max(1, min(int(value), 10))
    except ValueError:
        return default


def _format_datetime(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%H:%M %d/%m")
    return str(value or "N/A")
