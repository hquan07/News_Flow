from fastapi import APIRouter, Depends, Query, Response, status

from api.models.events import CrisisRoom, CrisisRoomCreate, CrisisRoomUpdate
from api.security import require_permission
from api.services import crisis_store, event_clustering


router = APIRouter(prefix="/events", tags=["Events"])


@router.get("")
def list_events(days: int = Query(default=7, ge=1, le=30), limit: int = Query(default=300, ge=20, le=1000)):
    return {"events": event_clustering.cluster_events(days, limit), "days": days}


@router.post("/rooms", response_model=CrisisRoom, status_code=status.HTTP_201_CREATED)
async def create_room(payload: CrisisRoomCreate, actor: dict = Depends(require_permission("dashboard.read"))):
    snapshot = event_clustering.event_detail(payload.event_id, days=30)
    return await crisis_store.create(actor["sub"], payload.model_dump(), snapshot)


@router.get("/rooms/mine", response_model=list[CrisisRoom])
async def list_rooms(actor: dict = Depends(require_permission("dashboard.read"))):
    return await crisis_store.list_rooms(actor["sub"])


@router.patch("/rooms/{room_id}", response_model=CrisisRoom)
async def update_room(room_id: str, payload: CrisisRoomUpdate, actor: dict = Depends(require_permission("dashboard.read"))):
    return await crisis_store.update(actor["sub"], room_id, payload.model_dump())


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(room_id: str, actor: dict = Depends(require_permission("dashboard.read"))):
    await crisis_store.delete(actor["sub"], room_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{event_id}")
def get_event(event_id: str, days: int = Query(default=7, ge=1, le=30)):
    return event_clustering.event_detail(event_id, days)
