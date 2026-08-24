from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Room, User
from app.schemas import RoomCreate, RoomOut, RoomUpdate

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


@router.get("", response_model=list[RoomOut])
def list_rooms(include_disabled: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Room]:
    query = db.query(Room).order_by(Room.name.asc())
    if not include_disabled:
        query = query.filter(Room.is_active.is_(True))
    return query.all()


@router.post("", response_model=RoomOut)
def create_room(payload: RoomCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> Room:
    room = Room(**payload.model_dump())
    db.add(room)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="会议室名称已存在") from exc
    log_action(db, admin, "create", "room", room.id)
    db.commit()
    db.refresh(room)
    return room


@router.patch("/{room_id}", response_model=RoomOut)
def update_room(room_id: int, payload: RoomUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> Room:
    room = db.query(Room).filter(Room.id == room_id).one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会议室不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(room, key, value)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="会议室名称已存在") from exc
    log_action(db, admin, "update", "room", room.id)
    db.commit()
    db.refresh(room)
    return room
