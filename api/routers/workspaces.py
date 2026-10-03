from fastapi import APIRouter, Depends, Response, status

from api.models.workspaces import SharedWatchlistCreate, WorkspaceCreate, WorkspaceMemberUpsert
from api.security import require_permission
from api.services import workspace_store


router = APIRouter(prefix="/workspaces", tags=["Team Workspaces"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_workspace(payload: WorkspaceCreate, actor: dict = Depends(require_permission("dashboard.read"))):
    return await workspace_store.create(actor, payload.name)


@router.get("")
async def list_workspaces(actor: dict = Depends(require_permission("dashboard.read"))):
    return await workspace_store.list_accessible(actor)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(workspace_id: str, actor: dict = Depends(require_permission("dashboard.read"))):
    await workspace_store.delete_workspace(workspace_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{workspace_id}/members")
async def upsert_member(workspace_id: str, payload: WorkspaceMemberUpsert, actor: dict = Depends(require_permission("dashboard.read"))):
    return await workspace_store.upsert_member(workspace_id, actor, str(payload.email), payload.role)


@router.delete("/{workspace_id}/members/{email}")
async def remove_member(workspace_id: str, email: str, actor: dict = Depends(require_permission("dashboard.read"))):
    return await workspace_store.remove_member(workspace_id, actor, email)


@router.post("/{workspace_id}/watchlists", status_code=status.HTTP_201_CREATED)
async def create_shared_watchlist(workspace_id: str, payload: SharedWatchlistCreate, actor: dict = Depends(require_permission("dashboard.read"))):
    return await workspace_store.create_watchlist(workspace_id, actor, payload.model_dump())


@router.get("/{workspace_id}/watchlists")
async def list_shared_watchlists(workspace_id: str, actor: dict = Depends(require_permission("dashboard.read"))):
    return await workspace_store.list_watchlists(workspace_id, actor)
