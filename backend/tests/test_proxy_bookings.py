from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.campuses import Campus
from app.database import Base
from app.models import User, UserRole
from app.schemas import BookingCreate, BookingUpdate, RecurringBookingRequest
from app.services import create_booking, create_recurring_bookings, update_booking
from app.time_utils import now_shanghai


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def add_user(db: Session, staff_id: str, name: str, department: str, role: UserRole = UserRole.user) -> User:
    user = User(
        staff_id=staff_id,
        name=name,
        department=department,
        role=role.value,
        password_hash="unused",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def add_room(db: Session):
    from app.models import Room

    room = Room(
        campus=Campus.qingchun.value,
        name="代约测试会议室",
        location="测试位置",
        capacity=20,
        is_active=True,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def booking_payload(room_id: int, **overrides) -> BookingCreate:
    values = {
        "room_id": room_id,
        "booking_date": (now_shanghai() + timedelta(days=7)).date(),
        "start_time": "09:00",
        "end_time": "10:00",
        "title": "代约测试",
        "attendee_count": 2,
    }
    values.update(overrides)
    return BookingCreate(**values)


def test_regular_booking_forces_owner_identity(db: Session) -> None:
    owner = add_user(db, "owner-1", "张三", "医务科")
    room = add_room(db)

    booking = create_booking(
        db,
        owner,
        booking_payload(room.id, department="其他科室", user_name="李四", is_proxy_booking=False),
    )

    assert booking.applicant_id == owner.id
    assert booking.department == owner.department
    assert booking.user_name == owner.name
    assert booking.is_proxy_booking is False


def test_proxy_booking_saves_actual_user_and_keeps_owner(db: Session) -> None:
    owner = add_user(db, "owner-2", "张三", "医务科")
    room = add_room(db)

    booking = create_booking(
        db,
        owner,
        booking_payload(room.id, department="心内科", user_name="李四", is_proxy_booking=True),
    )

    assert booking.applicant_id == owner.id
    assert booking.department == "心内科"
    assert booking.user_name == "李四"
    assert booking.is_proxy_booking is True


@pytest.mark.parametrize("user_name", ["", "李四、王五"])
def test_proxy_booking_requires_one_actual_user(db: Session, user_name: str) -> None:
    owner = add_user(db, f"owner-{user_name or 'empty'}", "张三", "医务科")
    room = add_room(db)

    with pytest.raises(HTTPException) as exc_info:
        create_booking(
            db,
            owner,
            booking_payload(room.id, department="心内科", user_name=user_name, is_proxy_booking=True),
        )

    assert exc_info.value.status_code == 422


def test_booking_owner_can_edit_proxy_identity_and_restore_self(db: Session) -> None:
    owner = add_user(db, "owner-3", "张三", "医务科")
    room = add_room(db)
    booking = create_booking(
        db,
        owner,
        booking_payload(room.id, department="心内科", user_name="李四", is_proxy_booking=True),
    )

    booking_date = booking_payload(room.id).booking_date
    booking = update_booking(
        db,
        owner,
        booking,
        BookingUpdate(
            booking_date=booking_date,
            start_time="09:00",
            end_time="10:00",
            department="神经内科",
            user_name="王五",
            is_proxy_booking=True,
        ),
    )
    assert booking.department == "神经内科"
    assert booking.user_name == "王五"
    assert booking.is_proxy_booking is True

    booking = update_booking(
        db,
        owner,
        booking,
        BookingUpdate(booking_date=booking_date, start_time="09:00", end_time="10:00", is_proxy_booking=False),
    )
    assert booking.department == owner.department
    assert booking.user_name == owner.name
    assert booking.is_proxy_booking is False


def test_admin_restore_uses_booking_owner_identity(db: Session) -> None:
    owner = add_user(db, "owner-4", "张三", "医务科")
    admin = add_user(db, "admin-1", "管理员", "院办", UserRole.admin)
    room = add_room(db)
    booking = create_booking(
        db,
        owner,
        booking_payload(room.id, department="心内科", user_name="李四", is_proxy_booking=True),
    )

    booking = update_booking(db, admin, booking, BookingUpdate(is_proxy_booking=False))

    assert booking.applicant_id == owner.id
    assert booking.department == owner.department
    assert booking.user_name == owner.name


def test_actual_user_does_not_gain_booking_permissions(db: Session) -> None:
    owner = add_user(db, "owner-5", "张三", "医务科")
    actual_user = add_user(db, "actual-1", "李四", "心内科")
    room = add_room(db)
    booking = create_booking(
        db,
        owner,
        booking_payload(room.id, department=actual_user.department, user_name=actual_user.name, is_proxy_booking=True),
    )

    with pytest.raises(HTTPException) as exc_info:
        update_booking(db, actual_user, booking, BookingUpdate(title="越权修改"))

    assert exc_info.value.status_code == 403


def test_recurring_proxy_booking_copies_usage_identity(db: Session) -> None:
    admin = add_user(db, "admin-2", "管理员", "医务科", UserRole.admin)
    room = add_room(db)
    target_date = (now_shanghai() + timedelta(days=7)).date()
    payload = RecurringBookingRequest(
        room_id=room.id,
        start_date=target_date,
        end_date=target_date,
        weekdays=[target_date.weekday()],
        start_time="09:00",
        end_time="10:00",
        title="代约周期会议",
        attendee_count=2,
        department="心内科",
        user_name="李四",
        is_proxy_booking=True,
    )

    result = create_recurring_bookings(db, admin, payload)

    assert result.series is not None
    assert result.series.is_proxy_booking is True
    assert result.series.department == "心内科"
    assert result.series.user_name == "李四"
    assert len(result.success) == 1
    assert result.success[0].booking is not None
    assert result.success[0].booking.applicant.id == admin.id
    assert result.success[0].booking.is_proxy_booking is True
    assert result.success[0].booking.department == "心内科"
    assert result.success[0].booking.user_name == "李四"
