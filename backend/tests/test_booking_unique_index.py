from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.campuses import DEFAULT_CAMPUS
from app.database import Base
from app.models import Booking, BookingStatus, Room, User, UserRole


def make_booking(room_id: int, applicant_id: int, status: BookingStatus) -> Booking:
    return Booking(
        room_id=room_id,
        applicant_id=applicant_id,
        campus=DEFAULT_CAMPUS.value,
        title="Index regression",
        department="Department",
        user_name="User",
        attendee_count=1,
        start_at=datetime.fromisoformat("2026-10-04T17:00:00+08:00"),
        end_at=datetime.fromisoformat("2026-10-04T18:00:00+08:00"),
        status=status.value,
    )


def test_exact_slot_uniqueness_only_applies_to_active_bookings() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user = User(
            staff_id="index-test",
            name="User",
            department="Department",
            role=UserRole.admin.value,
            password_hash="unused",
        )
        room = Room(
            campus=DEFAULT_CAMPUS.value,
            name="Index room",
            location="Location",
            capacity=10,
        )
        db.add_all([user, room])
        db.flush()

        db.add_all(
            [
                make_booking(room.id, user.id, BookingStatus.cancelled),
                make_booking(room.id, user.id, BookingStatus.cancelled),
                make_booking(room.id, user.id, BookingStatus.active),
            ]
        )
        db.commit()

        db.add(make_booking(room.id, user.id, BookingStatus.active))
        with pytest.raises(IntegrityError):
            db.commit()
