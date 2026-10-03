"""Personal monitoring configuration endpoints."""

from fastapi import APIRouter, Depends, Response, status

from api.models.intelligence import (
    AlertRule, AlertRuleCreate, AlertRuleUpdate,
    SavedQuery, SavedQueryCreate, SavedQueryUpdate,
    Watchlist, WatchlistCreate, WatchlistUpdate,
)
from api.security import require_permission
from api.services import intelligence_store


router = APIRouter(prefix="/intelligence", tags=["Personal Intelligence"])


def _owner(actor: dict) -> str:
    return str(actor.get("sub", ""))


@router.post("/watchlists", response_model=Watchlist, status_code=status.HTTP_201_CREATED)
async def create_watchlist(payload: WatchlistCreate, actor: dict = Depends(require_permission("dashboard.read"))):
    return await intelligence_store.create("watchlists", _owner(actor), payload.model_dump())


@router.get("/watchlists", response_model=list[Watchlist])
async def list_watchlists(actor: dict = Depends(require_permission("dashboard.read"))):
    return await intelligence_store.list_items("watchlists", _owner(actor))


@router.patch("/watchlists/{item_id}", response_model=Watchlist)
async def update_watchlist(item_id: str, payload: WatchlistUpdate, actor: dict = Depends(require_permission("dashboard.read"))):
    return await intelligence_store.update("watchlists", _owner(actor), item_id, payload.model_dump())


@router.delete("/watchlists/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(item_id: str, actor: dict = Depends(require_permission("dashboard.read"))):
    await intelligence_store.delete("watchlists", _owner(actor), item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/alert-rules", response_model=AlertRule, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(payload: AlertRuleCreate, actor: dict = Depends(require_permission("dashboard.read"))):
    return await intelligence_store.create("alert_rules", _owner(actor), payload.model_dump())


@router.get("/alert-rules", response_model=list[AlertRule])
async def list_alert_rules(actor: dict = Depends(require_permission("dashboard.read"))):
    return await intelligence_store.list_items("alert_rules", _owner(actor))


@router.patch("/alert-rules/{item_id}", response_model=AlertRule)
async def update_alert_rule(item_id: str, payload: AlertRuleUpdate, actor: dict = Depends(require_permission("dashboard.read"))):
    return await intelligence_store.update("alert_rules", _owner(actor), item_id, payload.model_dump())


@router.delete("/alert-rules/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(item_id: str, actor: dict = Depends(require_permission("dashboard.read"))):
    await intelligence_store.delete("alert_rules", _owner(actor), item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/saved-queries", response_model=SavedQuery, status_code=status.HTTP_201_CREATED)
async def create_saved_query(payload: SavedQueryCreate, actor: dict = Depends(require_permission("dashboard.read"))):
    return await intelligence_store.create("saved_queries", _owner(actor), payload.model_dump())


@router.get("/saved-queries", response_model=list[SavedQuery])
async def list_saved_queries(actor: dict = Depends(require_permission("dashboard.read"))):
    return await intelligence_store.list_items("saved_queries", _owner(actor))


@router.patch("/saved-queries/{item_id}", response_model=SavedQuery)
async def update_saved_query(item_id: str, payload: SavedQueryUpdate, actor: dict = Depends(require_permission("dashboard.read"))):
    return await intelligence_store.update("saved_queries", _owner(actor), item_id, payload.model_dump())


@router.delete("/saved-queries/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_query(item_id: str, actor: dict = Depends(require_permission("dashboard.read"))):
    await intelligence_store.delete("saved_queries", _owner(actor), item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
