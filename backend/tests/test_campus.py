from datetime import timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.campuses import Campus
from app.database import Base
from app.models import Booking, RecurringSeries, RecurringSeriesStatus, Room, User, UserRole
from app.routers_rooms import update_room
from app.schemas import BookingCreate, BookingUpdate, RoomCreate, RoomUpdate
from app.services import create_booking, update_booking
from app.time_utils import now_shanghai


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def admin(db: Session) -> User:
    user = User(
        staff_id="campus-admin",
        name="测试管理员",
        department="医务科",
        role=UserRole.admin.value,
        password_hash="unused",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def add_room(db: Session, campus: Campus, name: str) -> Room:
    room = Room(campus=campus.value, name=name, location="测试位置", capacity=20, is_active=True)
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def future_booking_payload(room_id: int) -> BookingCreate:
    return BookingCreate(
        room_id=room_id,
        booking_date=(now_shanghai() + timedelta(days=7)).date(),
        start_time="09:00",
        end_time="10:00",
        title="院区测试会议",
        attendee_count=2,
    )


def test_room_schema_rejects_unknown_campus() -> None:
    with pytest.raises(ValidationError):
        RoomCreate(
            campus="未知院区",
            name="测试会议室",
            location="测试位置",
            capacity=10,
        )


def test_room_name_is_unique_within_campus(db: Session) -> None:
    add_room(db, Campus.qingchun, "同名会议室")
    add_room(db, Campus.qiantang, "同名会议室")

    db.add(Room(campus=Campus.qingchun.value, name="同名会议室", location="另一位置", capacity=10, is_active=True))
    with pytest.raises(IntegrityError):
        db.commit()


def test_booking_campus_snapshot_tracks_selected_room(db: Session, admin: User) -> None:
    qingchun_room = add_room(db, Campus.qingchun, "庆春会议室")
    qiantang_room = add_room(db, Campus.qiantang, "钱塘会议室")

    booking = create_booking(db, admin, future_booking_payload(qingchun_room.id))
    assert booking.campus == Campus.qingchun.value

    booking = update_booking(db, admin, booking, BookingUpdate(room_id=qiantang_room.id))
    assert booking.room_id == qiantang_room.id
    assert booking.campus == Campus.qiantang.value


def test_campus_cannot_change_after_room_has_booking(db: Session, admin: User) -> None:
    room = add_room(db, Campus.qingchun, "锁定院区会议室")
    booking = create_booking(db, admin, future_booking_payload(room.id))
    assert db.query(Booking).filter(Booking.id == booking.id).one()

    with pytest.raises(HTTPException) as exc_info:
        update_room(room.id, RoomUpdate(campus=Campus.shaoxing), db, admin)

    assert exc_info.value.status_code == 409
    assert "不能修改所属院区" in exc_info.value.detail


def test_campus_cannot_change_after_room_has_empty_recurring_series(db: Session, admin: User) -> None:
    room = add_room(db, Campus.qingchun, "周期组锁定院区会议室")
    start_date = (now_shanghai() + timedelta(days=7)).date()
    series = RecurringSeries(
        room_id=room.id,
        created_by_id=admin.id,
        campus=room.campus,
        title="空周期组",
        department=admin.department,
        user_name=admin.name,
        attendee_count=2,
        start_date=start_date,
        end_date=start_date,
        weekdays=str(start_date.weekday()),
        start_time="09:00",
        end_time="10:00",
        status=RecurringSeriesStatus.active.value,
    )
    db.add(series)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        update_room(room.id, RoomUpdate(campus=Campus.shaoxing), db, admin)

    assert exc_info.value.status_code == 409
    assert "周期记录" in exc_info.value.detail
