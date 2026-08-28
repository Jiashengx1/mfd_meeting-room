from datetime import date

import pytest
from fastapi import HTTPException

from app.time_utils import validate_range


def test_booking_range_accepts_business_hours_boundaries() -> None:
    start_at, end_at = validate_range(date(2026, 8, 28), "07:00", "18:00")

    assert start_at.strftime("%H:%M") == "07:00"
    assert end_at.strftime("%H:%M") == "18:00"


@pytest.mark.parametrize(
    ("start_time", "end_time"),
    [
        ("06:30", "07:30"),
        ("17:30", "18:30"),
        ("18:00", "18:30"),
        ("17:30", "24:00"),
    ],
)
def test_booking_range_rejects_times_outside_business_hours(start_time: str, end_time: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_range(date(2026, 8, 28), start_time, end_time)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "预约时间必须在 07:00-18:00 之间"
