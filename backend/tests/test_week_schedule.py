from datetime import date, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.campuses import Campus
from app.database import Base
from app.models import Booking, BookingStatus, Room, User, UserRole
from app.routers_bookings import week_schedule
from app.time_utils import SHANGHAI


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def user_and_room(db: Session) -> tuple[User, Room]:
    user = User(
        staff_id="week-user",
        name="测试用户",
        department="医务科",
        role=UserRole.user.value,
        password_hash="unused",
        is_active=True,
    )
    room = Room(
        campus=Campus.qingchun.value,
        name="周视图会议室",
        location="测试位置",
        capacity=20,
        is_active=True,
    )
    db.add_all([user, room])
    db.commit()
    db.refresh(user)
    db.refresh(room)
    return user, room


def test_week_schedule_returns_only_selected_week(db: Session, user_and_room: tuple[User, Room]) -> None:
    user, room = user_and_room
    in_week = Booking(
        room_id=room.id,
        applicant_id=user.id,
        campus=room.campus,
        title="周内会议",
        department=user.department,
        user_name=user.name,
        attendee_count=2,
        start_at=datetime(2026, 9, 2, 9, 0, tzinfo=SHANGHAI),
        end_at=datetime(2026, 9, 2, 10, 0, tzinfo=SHANGHAI),
        status=BookingStatus.active.value,
    )
    outside_week = Booking(
        room_id=room.id,
        applicant_id=user.id,
        campus=room.campus,
        title="下周会议",
        department=user.department,
        user_name=user.name,
        attendee_count=2,
        start_at=datetime(2026, 9, 8, 9, 0, tzinfo=SHANGHAI),
        end_at=datetime(2026, 9, 8, 10, 0, tzinfo=SHANGHAI),
        status=BookingStatus.active.value,
    )
    db.add_all([in_week, outside_week])
    db.commit()

    result = week_schedule(room.id, date(2026, 8, 31), db, user)

    assert result.week_start == date(2026, 8, 31)
    assert result.week_end == date(2026, 9, 6)
    assert [booking.title for booking in result.bookings] == ["周内会议"]


def test_week_schedule_keeps_disabled_room_history(db: Session, user_and_room: tuple[User, Room]) -> None:
    user, room = user_and_room
    room.is_active = False
    db.commit()

    result = week_schedule(room.id, date(2026, 8, 31), db, user)

    assert result.room.id == room.id
    assert result.room.is_active is False


def test_week_schedule_requires_monday(db: Session, user_and_room: tuple[User, Room]) -> None:
    user, room = user_and_room

    with pytest.raises(HTTPException) as exc_info:
        week_schedule(room.id, date(2026, 9, 1), db, user)

    assert exc_info.value.status_code == 422
