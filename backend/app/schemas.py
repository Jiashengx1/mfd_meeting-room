from datetime import date, datetime

from pydantic import BaseModel, Field

from app.campuses import Campus
from app.models import RecurringFrequency


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class LoginRequest(BaseModel):
    staff_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    staff_id: str = Field(min_length=1, max_length=64)
    confirm_staff_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    department: str = Field(min_length=1, max_length=100)


class UserOut(BaseModel):
    id: int
    staff_id: str
    name: str
    department: str
    role: str

    model_config = {"from_attributes": True}


class RoomBase(BaseModel):
    campus: Campus
    name: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=200)
    capacity: int = Field(gt=0, le=10000)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    campus: Campus | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    capacity: int | None = Field(default=None, gt=0, le=10000)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class RoomOut(RoomBase):
    id: int
    campus_locked: bool = False

    model_config = {"from_attributes": True}


class BookingBase(BaseModel):
    room_id: int
    booking_date: date
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    title: str = Field(min_length=1, max_length=200)
    attendee_count: int = Field(gt=0, le=10000)
    note: str | None = Field(default=None, max_length=2000)
    department: str | None = Field(default=None, max_length=100)
    user_name: str | None = Field(default=None, max_length=100)
    is_proxy_booking: bool = False


class BookingCreate(BookingBase):
    pass


class BookingUpdate(BaseModel):
    room_id: int | None = None
    booking_date: date | None = None
    start_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    attendee_count: int | None = Field(default=None, gt=0, le=10000)
    note: str | None = Field(default=None, max_length=2000)
    department: str | None = Field(default=None, max_length=100)
    user_name: str | None = Field(default=None, max_length=100)
    is_proxy_booking: bool | None = None


class BookingOut(BaseModel):
    id: int
    room: RoomOut
    applicant: UserOut
    recurring_series_id: int | None
    campus: Campus | None
    title: str
    department: str | None
    user_name: str | None
    is_proxy_booking: bool
    attendee_count: int
    note: str | None
    start_at: datetime
    end_at: datetime
    status: str
    cancelled_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecurringBookingRequest(BaseModel):
    room_id: int
    start_date: date
    end_date: date
    frequency: RecurringFrequency = RecurringFrequency.weekly
    weekdays: list[int] = Field(min_length=1, max_length=7)
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    title: str = Field(min_length=1, max_length=200)
    attendee_count: int = Field(gt=0, le=10000)
    note: str | None = Field(default=None, max_length=2000)
    department: str | None = Field(default=None, max_length=100)
    user_name: str | None = Field(default=None, max_length=100)
    is_proxy_booking: bool = False


class RecurringBookingItem(BaseModel):
    booking_date: date
    start_at: datetime
    end_at: datetime
    status: str
    reason: str | None = None
    conflict_booking: BookingOut | None = None
    booking: BookingOut | None = None


class RecurringSeriesOut(BaseModel):
    id: int
    room: RoomOut
    created_by: UserOut
    campus: Campus | None
    title: str
    department: str | None
    user_name: str | None
    is_proxy_booking: bool
    attendee_count: int
    note: str | None
    start_date: date
    end_date: date
    frequency: RecurringFrequency
    weekdays: list[int]
    start_time: str
    end_time: str
    status: str
    cancelled_at: datetime | None
    created_at: datetime
    active_booking_count: int = 0
    future_active_booking_count: int = 0


class RecurringBookingResult(BaseModel):
    success: list[RecurringBookingItem]
    conflicts: list[RecurringBookingItem]
    expired: list[RecurringBookingItem]
    series: RecurringSeriesOut | None = None


class RecurringSeriesCancelResult(BaseModel):
    series: RecurringSeriesOut
    cancelled: list[BookingOut]
    skipped_expired_count: int


class DaySchedule(BaseModel):
    date: date
    campus: Campus
    rooms: list["RoomSchedule"]


class RoomSchedule(BaseModel):
    room: RoomOut
    bookings: list[BookingOut]


class WeekSchedule(BaseModel):
    week_start: date
    week_end: date
    room: RoomOut
    bookings: list[BookingOut]


TokenResponse.model_rebuild()
