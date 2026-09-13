from fastapi import APIRouter, Header, HTTPException, Depends
from typing import Optional, List
from api.services.analytics import _query
import jwt

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

SECRET_KEY = "newspulse_super_secret" 
ALGORITHM = "HS256"

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/")
def get_recommendations(user: dict = Depends(get_current_user)):
    user_id = user.get("sub")
    
    # 1. Fetch user's top categories based on interaction
    interacted_data = _query(
        f"SELECT article_hash FROM newspulse.user_interactions "
        f"WHERE user_id = '{user_id}' ORDER BY timestamp DESC LIMIT 50"
    )
    
    if not interacted_data:
        # Fallback: Just return trending articles
        articles = _query(
            "SELECT url_hash, url, title, content, author, source, category, publish_time "
            "FROM newspulse.raw_articles ORDER BY publish_time DESC LIMIT 20"
        )
    else:
        # In a real app, we would join with raw_articles to find categories and recommend
        # For simplicity, we just fetch random fresh articles the user hasn't seen
        hashes = [row['article_hash'] for row in interacted_data]
        hash_list_str = "','".join(hashes)
        
        articles = _query(
            f"SELECT url_hash, url, title, content, author, source, category, publish_time "
            f"FROM newspulse.raw_articles "
            f"WHERE url_hash NOT IN ('{hash_list_str}') "
            f"ORDER BY publish_time DESC LIMIT 20"
        )
        
    return {"articles": articles}

@router.post("/interact")
def track_interaction(
    article_hash: str, 
    interaction_type: str = "click", 
    user: dict = Depends(get_current_user)
):
    user_id = user.get("sub")
    
    # Write to ClickHouse user_interactions
    from api.config import get_ch_client
    from datetime import datetime
    
    client = get_ch_client()
    try:
        client.insert('newspulse.user_interactions', [[
            user_id,
            article_hash,
            interaction_type,
            1.0,
            datetime.now()
        ]], column_names=['user_id', 'article_hash', 'interaction_type', 'interaction_weight', 'timestamp'])
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if hasattr(client, 'close'):
            client.close()
