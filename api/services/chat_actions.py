"""Two-step, owner-bound actions. Chat text never calls these methods."""

import asyncio
import csv
import hashlib
import io
import re
import secrets
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument
import httpx

from api.database import get_mongo_db
from api.middleware import request_id_context
from api.models.chat_actions import ActionPreviewRequest, ActionConfirmRequest
from api.routers import crawler_admin
from api.services.alert_state import update_alert_state
from api.services.analytics import _query, get_alerts


PERMISSIONS = {
    "acknowledge_alert": "alerts.manage",
    "trigger_crawler": "crawler.run",
    "generate_report": "reports.export",
}
REPORT_WINDOWS = {"today": "24 HOUR", "7d": "7 DAY", "30d": "30 DAY"}


def _require_permission(action: str, actor: dict) -> None:
    permission = PERMISSIONS[action]
    if permission not in actor["permissions"]:
        raise HTTPException(status_code=403, detail=f"Forbidden: Missing permission '{permission}'")


def _oid(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=404, detail="Action not found")
    return ObjectId(value)


async def ensure_indexes() -> None:
    db = get_mongo_db()
    await db.chat_action_requests.create_index("expires_at", expireAfterSeconds=0)
    await db.chat_reports.create_index("expires_at", expireAfterSeconds=0)
    await db.chat_reports.create_index([("owner_id", 1), ("created_at", -1)])


async def _audit(event: str, actor: dict, action_id: str, action: str) -> None:
    await get_mongo_db().audit_logs.insert_one({
        "action": event,
        "actor_id": actor["sub"],
        "actor_email": actor.get("email", ""),
        "target_id": action_id,
        "action_type": action,
        "request_id": request_id_context.get(),
        "created_at": datetime.now(timezone.utc),
    })


async def preview(request: ActionPreviewRequest, actor: dict) -> dict:
    _require_permission(request.action, actor)
    parameters = request.model_dump(exclude_none=True, exclude={"action"})
    if request.action == "acknowledge_alert":
        if not re.fullmatch(r"volume:\d{10}", request.alert_id or ""):
            raise HTTPException(status_code=422, detail="Expected a volume alert ID")
        alerts = await asyncio.to_thread(get_alerts, threshold=2.0, limit=100)
        if request.alert_id not in {item.get("alert_id") for item in alerts}:
            raise HTTPException(status_code=404, detail="Active alert not found")
        summary = f"Đánh dấu cảnh báo {request.alert_id} là đã xem cho riêng tài khoản của bạn."
    elif request.action == "trigger_crawler":
        if request.spider_name not in crawler_admin.SPIDER_REGISTRY:
            raise HTTPException(status_code=422, detail="Crawler is not in the allowlist")
        summary = f"Chạy một lần crawler {request.spider_name} qua Airflow; có thể tạo dữ liệu mới."
    else:
        summary = f"Tạo báo cáo tổng hợp theo nguồn và danh mục trong {request.time_range}, tối đa 50 dòng."
        if request.source:
            summary += f" Chỉ nguồn {request.source}."
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    oid = ObjectId()
    await get_mongo_db().chat_action_requests.insert_one({
        "_id": oid,
        "owner_id": actor["sub"],
        "action": request.action,
        "parameters": parameters,
        "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "status": "pending",
        "created_at": now,
        "expires_at": now + timedelta(minutes=5),
    })
    await _audit("chat.action_previewed", actor, str(oid), request.action)
    return {
        "action_id": str(oid),
        "confirmation_token": token,
        "action": request.action,
        "summary": summary,
        "expires_at": now + timedelta(minutes=5),
    }


def _report_rows(time_range: str, source: str | None) -> list[dict]:
    conditions = [f"publish_time >= now() - INTERVAL {REPORT_WINDOWS[time_range]}"]
    params = {}
    if source:
        conditions.append("source = {source:String}")
        params["source"] = source
    rows = _query(
        "SELECT source, category, countDistinct(url_hash) AS article_count "
        "FROM newspulse.raw_articles FINAL WHERE " + " AND ".join(conditions) +
        " GROUP BY source, category ORDER BY article_count DESC LIMIT 50",
        params,
    )
    return [{"source": str(row["source"]), "category": str(row["category"]),
             "article_count": int(row["article_count"])} for row in rows]


async def _execute(document: dict, actor: dict) -> dict:
    action = document["action"]
    params = document["parameters"]
    if action == "acknowledge_alert":
        alert_id = params["alert_id"]
        active = await asyncio.to_thread(get_alerts, threshold=2.0, limit=100)
        if alert_id not in {item.get("alert_id") for item in active}:
            raise HTTPException(status_code=409, detail="Alert is no longer active")
        state = await update_alert_state(actor["sub"], alert_id, acknowledged=True)
        return {"alert_id": alert_id, "acknowledged": state["acknowledged"]}
    if action == "trigger_crawler":
        spider = params["spider_name"]
        if spider not in crawler_admin.SPIDER_REGISTRY:
            raise HTTPException(status_code=422, detail="Crawler is not in the allowlist")
        run_id = f"chat__{document['_id']}"
        try:
            response = await crawler_admin._airflow_post(
                "/dags/newspulse_crawl/dagRuns",
                json_body={
                    "dag_run_id": run_id,
                    "conf": {"spider": spider},
                    "note": f"Confirmed chatbot action {document['_id']}",
                },
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Airflow timed out; check run {run_id} before retrying",
            ) from exc
        return {"spider_name": spider, "dag_run_id": response.get("dag_run_id", run_id),
                "state": response.get("state")}
    rows = await asyncio.to_thread(_report_rows, params["time_range"], params.get("source"))
    report = {
        "owner_id": actor["sub"],
        "action_id": str(document["_id"]),
        "time_range": params["time_range"],
        "source": params.get("source"),
        "rows": rows,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    }
    inserted = await get_mongo_db().chat_reports.insert_one(report)
    report_id = str(inserted.inserted_id)
    return {"report_id": report_id, "row_count": len(rows),
            "download_url": f"/api/v1/chat/actions/reports/{report_id}"}


async def confirm(request: ActionConfirmRequest, actor: dict) -> dict:
    oid = _oid(request.action_id)
    db = get_mongo_db()
    document = await db.chat_action_requests.find_one({"_id": oid, "owner_id": actor["sub"]})
    if not document:
        raise HTTPException(status_code=404, detail="Action not found")
    token_hash = hashlib.sha256(request.confirmation_token.encode()).hexdigest()
    if not secrets.compare_digest(token_hash, document["token_hash"]):
        raise HTTPException(status_code=404, detail="Action not found")
    _require_permission(document["action"], actor)
    if document["status"] != "pending":
        raise HTTPException(status_code=409, detail="Action has already been confirmed")
    now = datetime.now(timezone.utc)
    expires_at = document["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(status_code=410, detail="Confirmation expired")
    claimed = await db.chat_action_requests.find_one_and_update(
        {"_id": oid, "owner_id": actor["sub"], "status": "pending",
         "token_hash": token_hash, "expires_at": {"$gt": now}},
        {"$set": {"status": "executing", "started_at": now,
                  "expires_at": now + timedelta(days=7)}},
        return_document=ReturnDocument.AFTER,
    )
    if not claimed:
        raise HTTPException(status_code=409, detail="Action is no longer available")
    try:
        await _audit("chat.action_started", actor, str(oid), claimed["action"])
        result = await _execute(claimed, actor)
    except Exception:
        await db.chat_action_requests.update_one(
            {"_id": oid, "status": "executing"},
            {"$set": {"status": "failed", "completed_at": datetime.now(timezone.utc)}},
        )
        await _audit("chat.action_failed", actor, str(oid), claimed["action"])
        raise
    await db.chat_action_requests.update_one(
        {"_id": oid, "status": "executing"},
        {"$set": {"status": "succeeded", "result": result,
                  "completed_at": datetime.now(timezone.utc)}},
    )
    await _audit("chat.action_succeeded", actor, str(oid), claimed["action"])
    return {"action_id": str(oid), "action": claimed["action"], "status": "succeeded", "result": result}


async def report_csv(report_id: str, actor: dict) -> str:
    _require_permission("generate_report", actor)
    report = await get_mongo_db().chat_reports.find_one({
        "_id": _oid(report_id), "owner_id": actor["sub"],
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["source", "category", "article_count"])
    for row in report["rows"]:
        def safe(value: str) -> str:
            return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
        writer.writerow([safe(row["source"]), safe(row["category"]), row["article_count"]])
    return "\ufeff" + output.getvalue()


async def action_status(action_id: str, actor: dict) -> dict:
    document = await get_mongo_db().chat_action_requests.find_one({
        "_id": _oid(action_id), "owner_id": actor["sub"],
    })
    if not document:
        raise HTTPException(status_code=404, detail="Action not found")
    _require_permission(document["action"], actor)
    expires_at = document["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    status = "expired" if document["status"] == "pending" and expires_at <= datetime.now(timezone.utc) else document["status"]
    return {
        "action_id": action_id,
        "action": document["action"],
        "status": status,
        "result": document.get("result"),
        "expires_at": expires_at,
    }
