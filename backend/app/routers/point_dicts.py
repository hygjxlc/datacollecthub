from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.point_dict import PointDictCreate, PointDictOut, PointDictUpdate
from app.services.point_dict_service import PointDictService

router = APIRouter(prefix="/api/v1/point-dicts", tags=["point-dicts"])


# 注意：必须声明在 /{point_dict_id} 之前
@router.get("/device-nos")
def list_device_nos(user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    return {"items": PointDictService(db).list_device_nos(user)}


@router.get("")
def list_point_dicts(device_no: str | None = None,
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    return {"items": PointDictService(db).list_by_device(device_no, user)}


@router.post("", response_model=PointDictOut)
def create_point_dict(body: PointDictCreate, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    return PointDictService(db).create(body, user)


@router.get("/{point_dict_id}", response_model=PointDictOut)
def get_point_dict(point_dict_id: str, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    return PointDictService(db).get(point_dict_id, user)


@router.put("/{point_dict_id}", response_model=PointDictOut)
def update_point_dict(point_dict_id: str, body: PointDictUpdate,
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    return PointDictService(db).update(point_dict_id, body, user)


@router.delete("/{point_dict_id}")
def delete_point_dict(point_dict_id: str, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    PointDictService(db).delete(point_dict_id, user)
    return {"status": "ok"}
