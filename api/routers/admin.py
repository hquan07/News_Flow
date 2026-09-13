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
    if not df:
        return {"sources": [], "avg_latency": []}
        
    return {
        "sources": [row['source'] for row in df],
        "avg_latency": [round(float(row['avg_latency']), 2) for row in df]
    }

@router.get("/metrics/volume")
def get_article_volume(user: dict = Depends(get_admin_user)):
    """Lấy tổng số bài viết theo nguồn, bao gồm cả News và Social."""
    query_news = """
        SELECT source, count(*) as total_articles
        FROM raw_articles
        GROUP BY source
        ORDER BY total_articles DESC
    """
    df_news = _query(query_news)
    
    query_social = """
        SELECT source, count(*) as total_articles
        FROM social_sentiment_metrics
        GROUP BY source
        ORDER BY total_articles DESC
    """
    df_social = _query(query_social)
    
    return {
        "news": {
            "sources": [row['source'] for row in df_news] if df_news else [],
            "volumes": [int(row['total_articles']) for row in df_news] if df_news else []
        },
        "social": {
            "sources": [row['source'] for row in df_social] if df_social else [],
            "volumes": [int(row['total_articles']) for row in df_social] if df_social else []
        }
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
