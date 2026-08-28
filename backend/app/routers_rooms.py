from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.campuses import Campus
from app.models import Booking, RecurringSeries, Room, User
from app.schemas import RoomCreate, RoomOut, RoomUpdate

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


def room_out(room: Room, locked_room_ids: set[int] | None = None) -> RoomOut:
    locked = room.id in locked_room_ids if locked_room_ids is not None else False
    return RoomOut.model_validate(room).model_copy(update={"campus_locked": locked})


@router.get("", response_model=list[RoomOut])
def list_rooms(
    include_disabled: bool = False,
    campus: Campus | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[RoomOut]:
    query = db.query(Room).order_by(Room.campus.asc(), Room.name.asc())
    if not include_disabled:
        query = query.filter(Room.is_active.is_(True))
    if campus:
        query = query.filter(Room.campus == campus.value)
    room_list = query.all()
    room_ids = [room.id for room in room_list]
    booking_room_ids = {
        room_id
        for (room_id,) in db.query(Booking.room_id).filter(Booking.room_id.in_(room_ids)).distinct().all()
    } if room_ids else set()
    recurring_room_ids = {
        room_id
        for (room_id,) in db.query(RecurringSeries.room_id).filter(RecurringSeries.room_id.in_(room_ids)).distinct().all()
    } if room_ids else set()
    locked_room_ids = booking_room_ids | recurring_room_ids
    return [room_out(room, locked_room_ids) for room in room_list]


@router.post("", response_model=RoomOut)
def create_room(payload: RoomCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> RoomOut:
    room = Room(**payload.model_dump())
    db.add(room)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该院区已存在同名会议室") from exc
    log_action(db, admin, "create", "room", room.id)
    db.commit()
    db.refresh(room)
    return room_out(room)


@router.patch("/{room_id}", response_model=RoomOut)
def update_room(room_id: int, payload: RoomUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> RoomOut:
    room = db.query(Room).filter(Room.id == room_id).one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会议室不存在")
    changes = payload.model_dump(exclude_unset=True)
    requested_campus = changes.get("campus")
    if requested_campus and requested_campus.value != room.campus:
        has_booking = db.query(Booking.id).filter(Booking.room_id == room.id).first()
        has_recurring_series = db.query(RecurringSeries.id).filter(RecurringSeries.room_id == room.id).first()
        if has_booking or has_recurring_series:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该会议室已有预约或周期记录，不能修改所属院区")
    for key, value in changes.items():
        setattr(room, key, value)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该院区已存在同名会议室") from exc
    log_action(db, admin, "update", "room", room.id)
    db.commit()
    db.refresh(room)
    locked = (
        db.query(Booking.id).filter(Booking.room_id == room.id).first() is not None
        or db.query(RecurringSeries.id).filter(RecurringSeries.room_id == room.id).first() is not None
    )
    return room_out(room, {room.id} if locked else set())
