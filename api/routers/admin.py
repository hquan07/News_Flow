from fastapi import APIRouter, Header, HTTPException, Depends
from typing import Optional
from api.services.analytics import _query
from api.database import get_mongo_db
import jwt

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

SECRET_KEY = "newspulse_super_secret" 
ALGORITHM = "HS256"

def get_admin_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Forbidden: Admin access required")
        return payload
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/metrics/latency")
def get_crawl_latency(user: dict = Depends(get_admin_user)):
    """Lấy độ trễ trung bình khi cào dữ liệu (từ bài báo xuất bản đến lúc cào)."""
    query = """
        SELECT source, avg(crawl_latency_minutes) as avg_latency
        FROM raw_articles
        WHERE crawl_latency_minutes IS NOT NULL
        GROUP BY source
        ORDER BY avg_latency DESC
    """
    df = _query(query)
    if df is None or df.empty:
        return {"sources": [], "avg_latency": []}
        
    return {
        "sources": df['source'].tolist(),
        "avg_latency": [round(float(v), 2) for v in df['avg_latency']]
    }

@router.get("/metrics/clickbait")
def get_clickbait_scores(user: dict = Depends(get_admin_user)):
    """Lấy điểm số giật tít trung bình theo nguồn."""
    query = """
        SELECT source, avg(clickbait_score) as avg_score
        FROM raw_articles
        WHERE clickbait_score IS NOT NULL
        GROUP BY source
        ORDER BY avg_score DESC
    """
    df = _query(query)
    if df is None or df.empty:
        return {"sources": [], "avg_score": []}
        
    return {
        "sources": df['source'].tolist(),
        "avg_score": [round(float(v), 2) for v in df['avg_score']]
    }

@router.get("/metrics/users")
async def get_user_metrics(user: dict = Depends(get_admin_user)):
    """Lấy tổng số user từ MongoDB."""
    db = get_mongo_db()
    total_users = await db.users.count_documents({})
    admin_users = await db.users.count_documents({"role": "admin"})
    
    return {
        "total_users": total_users,
        "standard_users": total_users - admin_users,
        "admin_users": admin_users
    }
