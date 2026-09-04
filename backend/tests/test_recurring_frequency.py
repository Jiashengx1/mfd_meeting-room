from datetime import date

import pytest
from pydantic import ValidationError

from app.models import RecurringFrequency
from app.schemas import RecurringBookingRequest
from app.services import recurring_dates


def recurring_payload(**overrides) -> RecurringBookingRequest:
    values = {
        "room_id": 1,
        "start_date": date(2026, 9, 10),
        "end_date": date(2026, 10, 8),
        "weekdays": [0, 3],
        "start_time": "09:00",
        "end_time": "10:00",
        "title": "周期频率测试",
        "attendee_count": 2,
    }
    values.update(overrides)
    return RecurringBookingRequest(**values)


def test_recurring_frequency_defaults_to_weekly() -> None:
    payload = recurring_payload(end_date=date(2026, 9, 24))

    assert payload.frequency == RecurringFrequency.weekly
    assert recurring_dates(payload) == [
        date(2026, 9, 10),
        date(2026, 9, 14),
        date(2026, 9, 17),
        date(2026, 9, 21),
        date(2026, 9, 24),
    ]


def test_fortnightly_recurrence_uses_start_date_week_as_anchor() -> None:
    payload = recurring_payload(frequency=RecurringFrequency.fortnightly)

    assert recurring_dates(payload) == [
        date(2026, 9, 10),
        date(2026, 9, 21),
        date(2026, 9, 24),
        date(2026, 10, 5),
        date(2026, 10, 8),
    ]


def test_recurring_frequency_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        recurring_payload(frequency="monthly")
