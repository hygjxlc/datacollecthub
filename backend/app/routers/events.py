from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.event import EventCreate, EventOut, EventUpdate
from app.services.event_service import EventService

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("")
def list_events(device_no: str | None = None, start: str | None = None,
                end: str | None = None, severity: str | None = None,
                user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    return {"items": EventService(db).list_events(device_no, start, end, severity, user)}


@router.post("", response_model=EventOut)
def create_event(body: EventCreate, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    return EventService(db).create(body, user)


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: str, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    return EventService(db).get(event_id, user)


@router.put("/{event_id}", response_model=EventOut)
def update_event(event_id: str, body: EventUpdate,
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    return EventService(db).update(event_id, body, user)


@router.delete("/{event_id}")
def delete_event(event_id: str, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    EventService(db).delete(event_id, user)
    return {"status": "ok"}
