from fastapi import APIRouter, Depends
from api.services.analytics import _query
from api.services.clickhouse_resilience import execute_clickhouse
from api.security import get_current_user

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

@router.get("/")
def get_recommendations(user: dict = Depends(get_current_user)):
    user_id = user.get("sub")
    
    # 1. Fetch user's top categories based on interaction
    interacted_data = _query(
        "SELECT article_hash FROM newspulse.user_interactions "
        "WHERE user_id = {user_id:String} ORDER BY timestamp DESC LIMIT 50",
        {"user_id": user_id},
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
        hashes = [row["article_hash"] for row in interacted_data]
        
        articles = _query(
            "SELECT url_hash, url, title, content, author, source, category, publish_time "
            "FROM newspulse.raw_articles "
            "WHERE url_hash NOT IN {hashes:Array(String)} "
            "ORDER BY publish_time DESC LIMIT 20",
            {"hashes": hashes},
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
    from datetime import datetime

    execute_clickhouse(lambda client: client.insert('newspulse.user_interactions', [[
            user_id,
            article_hash,
            interaction_type,
            1.0,
            datetime.now()
        ]], column_names=['user_id', 'article_hash', 'interaction_type', 'interaction_weight', 'timestamp']))
    return {"status": "success"}
