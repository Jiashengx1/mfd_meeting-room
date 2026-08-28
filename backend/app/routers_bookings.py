from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.campuses import Campus, DEFAULT_CAMPUS
from app.models import Booking, BookingStatus, Room, User, UserRole
from app.schemas import BookingCreate, BookingOut, BookingUpdate, DaySchedule, RecurringBookingRequest, RecurringBookingResult, RecurringSeriesCancelResult, RecurringSeriesOut, RoomSchedule
from app.services import active_bookings_for_day, booking_scope, cancel_booking, cancel_recurring_series, create_booking, create_recurring_bookings, get_booking_or_404, list_recurring_series, preview_recurring_bookings, update_booking
from app.time_utils import SHANGHAI, day_bounds

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.get("/schedule", response_model=DaySchedule)
def schedule(
    target_date: date = Query(default_factory=lambda: datetime.now(SHANGHAI).date()),
    campus: Campus = Query(default=DEFAULT_CAMPUS),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DaySchedule:
    rooms = db.query(Room).filter(Room.is_active.is_(True), Room.campus == campus.value).order_by(Room.name.asc()).all()
    bookings = active_bookings_for_day(db, target_date, [room.id for room in rooms])
    by_room: dict[int, list[Booking]] = {room.id: [] for room in rooms}
    for booking in bookings:
        by_room.setdefault(booking.room_id, []).append(booking)
    return DaySchedule(
        date=target_date,
        campus=campus,
        rooms=[RoomSchedule(room=room, bookings=by_room.get(room.id, [])) for room in rooms],
    )


@router.get("", response_model=list[BookingOut])
def list_bookings(
    status: str | None = None,
    target_date: date | None = None,
    campus: Campus | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Booking]:
    query = booking_scope(db, user)
    if status:
        query = query.filter(Booking.status == status)
    if campus:
        query = query.filter(Booking.campus == campus.value)
    if target_date:
        start_at, end_at = day_bounds(target_date)
        query = query.filter(Booking.start_at < end_at, Booking.end_at > start_at)
    return query.limit(300).all()


@router.get("/mine", response_model=list[BookingOut])
def my_bookings(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Booking]:
    return booking_scope(db, user).filter(Booking.applicant_id == user.id).limit(300).all()


@router.post("", response_model=BookingOut)
def create(payload: BookingCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Booking:
    return create_booking(db, user, payload)


@router.post("/recurring/preview", response_model=RecurringBookingResult)
def recurring_preview(payload: RecurringBookingRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> RecurringBookingResult:
    return preview_recurring_bookings(db, user, payload)


@router.post("/recurring", response_model=RecurringBookingResult)
def recurring_create(payload: RecurringBookingRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> RecurringBookingResult:
    return create_recurring_bookings(db, user, payload)


@router.get("/recurring", response_model=list[RecurringSeriesOut])
def recurring_list(status: str | None = None, mine: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    return list_recurring_series(db, user, status, mine_only=mine)


@router.post("/recurring/{series_id}/cancel", response_model=RecurringSeriesCancelResult)
def recurring_cancel(series_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> RecurringSeriesCancelResult:
    return cancel_recurring_series(db, user, series_id)


@router.patch("/{booking_id}", response_model=BookingOut)
def update(booking_id: int, payload: BookingUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Booking:
    booking = get_booking_or_404(db, booking_id)
    return update_booking(db, user, booking, payload)


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel(booking_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Booking:
    booking = get_booking_or_404(db, booking_id)
    return cancel_booking(db, user, booking)


@router.get("/stats")
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, int]:
    if user.role != UserRole.admin.value:
        return {}
    today = datetime.now(SHANGHAI).date()
    today_count = len(active_bookings_for_day(db, today))
    week_count = sum(len(active_bookings_for_day(db, today.fromordinal(today.toordinal() + offset))) for offset in range(7))
    room_count = db.query(Room).filter(Room.is_active.is_(True)).count()
    return {"today_bookings": today_count, "week_bookings": week_count, "active_rooms": room_count}
