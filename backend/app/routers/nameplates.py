from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.nameplate import NameplateCreate, NameplateOut, NameplateUpdate
from app.services.nameplate_service import NameplateService

router = APIRouter(prefix="/api/v1/nameplates", tags=["nameplates"])


@router.get("")
def list_nameplates(user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    return {"items": NameplateService(db).list_nameplates(user)}


# 注意：必须声明在 /{nameplate_id} 之前
@router.get("/by-device/{device_no}")
def get_by_device(device_no: str, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    return {"items": NameplateService(db).get_by_device(device_no, user)}


@router.post("", response_model=NameplateOut)
def create_nameplate(body: NameplateCreate, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    return NameplateService(db).create(body, user)


@router.get("/{nameplate_id}", response_model=NameplateOut)
def get_nameplate(nameplate_id: str, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    return NameplateService(db).get(nameplate_id, user)


@router.put("/{nameplate_id}", response_model=NameplateOut)
def update_nameplate(nameplate_id: str, body: NameplateUpdate,
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    return NameplateService(db).update(nameplate_id, body, user)


@router.delete("/{nameplate_id}")
def delete_nameplate(nameplate_id: str, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    NameplateService(db).delete(nameplate_id, user)
    return {"status": "ok"}
