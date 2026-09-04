from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.audit import log_action
from app.models import Booking, BookingStatus, RecurringFrequency, RecurringSeries, RecurringSeriesStatus, Room, User, UserRole
from app.schemas import BookingCreate, BookingUpdate, RecurringBookingItem, RecurringBookingRequest, RecurringBookingResult, RecurringSeriesCancelResult
from app.time_utils import SHANGHAI, assert_not_past, day_bounds, now_shanghai, validate_range


def ensure_can_manage_booking(actor: User, booking: Booking) -> None:
    if actor.role == UserRole.admin.value:
        return
    if booking.applicant_id != actor.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="不能操作其他用户的预约")


def get_booking_or_404(db: Session, booking_id: int) -> Booking:
    booking = (
        db.query(Booking)
        .options(joinedload(Booking.room), joinedload(Booking.applicant))
        .filter(Booking.id == booking_id)
        .one_or_none()
    )
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约不存在")
    return booking


def check_room_available(db: Session, room_id: int) -> Room:
    room = db.query(Room).filter(Room.id == room_id).one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会议室不存在")
    if not room.is_active:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="会议室已停用")
    return room


def assert_no_conflict(db: Session, room_id: int, start_at, end_at, exclude_booking_id: int | None = None) -> None:
    query = db.query(Booking).filter(
        Booking.room_id == room_id,
        Booking.status == BookingStatus.active.value,
        Booking.start_at < end_at,
        Booking.end_at > start_at,
    )
    if exclude_booking_id:
        query = query.filter(Booking.id != exclude_booking_id)
    if query.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该时间段已被预约")


def ensure_admin(actor: User) -> None:
    if actor.role != UserRole.admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可操作")


def resolve_usage_identity(
    owner: User,
    is_proxy_booking: bool,
    department: str | None,
    user_name: str | None,
) -> tuple[str, str, bool]:
    if not is_proxy_booking:
        return owner.department, owner.name, False

    resolved_department = (department or "").strip()
    resolved_user_name = (user_name or "").strip()
    if not resolved_department or not resolved_user_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="代约时部门和使用人为必填项")
    if any(separator in resolved_user_name for separator in ("、", ",", "，", "/", ";", "；", "\n")):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="使用人只能填写一名主要负责人")
    return resolved_department, resolved_user_name, True


def find_conflict(db: Session, room_id: int, start_at, end_at) -> Booking | None:
    return (
        db.query(Booking)
        .options(joinedload(Booking.room), joinedload(Booking.applicant))
        .filter(
            Booking.room_id == room_id,
            Booking.status == BookingStatus.active.value,
            Booking.start_at < end_at,
            Booking.end_at > start_at,
        )
        .order_by(Booking.start_at.asc())
        .first()
    )


def recurring_dates(payload: RecurringBookingRequest) -> list[date]:
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="结束日期不能早于开始日期")
    max_end_date = payload.start_date + timedelta(days=365)
    if payload.end_date > max_end_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="周期预约范围不能超过一年")
    weekdays = set(payload.weekdays)
    if any(day < 0 or day > 6 for day in weekdays):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="重复星期必须在 0-6 之间")
    interval_weeks = 2 if payload.frequency == RecurringFrequency.fortnightly else 1
    anchor_week_start = payload.start_date - timedelta(days=payload.start_date.weekday())
    result: list[date] = []
    current = payload.start_date
    while current <= payload.end_date:
        weeks_since_anchor = (current - anchor_week_start).days // 7
        if current.weekday() in weekdays and weeks_since_anchor % interval_weeks == 0:
            result.append(current)
        current += timedelta(days=1)
    return result


def recurring_weekdays_value(weekdays: list[int]) -> str:
    return ",".join(str(day) for day in sorted(set(weekdays)))


def recurring_weekdays_list(value: str) -> list[int]:
    return [int(item) for item in value.split(",") if item != ""]


def recurring_series_out(db: Session, series: RecurringSeries) -> dict:
    active_count = (
        db.query(Booking)
        .filter(Booking.recurring_series_id == series.id, Booking.status == BookingStatus.active.value)
        .count()
    )
    future_count = (
        db.query(Booking)
        .filter(
            Booking.recurring_series_id == series.id,
            Booking.status == BookingStatus.active.value,
            Booking.end_at > now_shanghai(),
        )
        .count()
    )
    return {
        "id": series.id,
        "room": series.room,
        "created_by": series.created_by,
        "campus": series.campus or series.room.campus,
        "title": series.title,
        "department": series.department,
        "user_name": series.user_name,
        "is_proxy_booking": series.is_proxy_booking,
        "attendee_count": series.attendee_count,
        "note": series.note,
        "start_date": series.start_date,
        "end_date": series.end_date,
        "frequency": series.frequency,
        "weekdays": recurring_weekdays_list(series.weekdays),
        "start_time": series.start_time,
        "end_time": series.end_time,
        "status": series.status,
        "cancelled_at": series.cancelled_at,
        "created_at": series.created_at,
        "active_booking_count": active_count,
        "future_active_booking_count": future_count,
    }


def build_recurring_result(db: Session, payload: RecurringBookingRequest, actor: User, *, create: bool) -> RecurringBookingResult:
    ensure_admin(actor)
    room = check_room_available(db, payload.room_id)
    department, user_name, is_proxy_booking = resolve_usage_identity(
        actor,
        payload.is_proxy_booking,
        payload.department,
        payload.user_name,
    )
    if payload.attendee_count > room.capacity:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="参会人数超过会议室容量")

    success: list[RecurringBookingItem] = []
    conflicts: list[RecurringBookingItem] = []
    expired: list[RecurringBookingItem] = []
    now = now_shanghai()
    series: RecurringSeries | None = None

    if create:
        series = RecurringSeries(
            room_id=payload.room_id,
            created_by_id=actor.id,
            campus=room.campus,
            title=payload.title,
            department=department,
            user_name=user_name,
            is_proxy_booking=is_proxy_booking,
            attendee_count=payload.attendee_count,
            note=payload.note,
            start_date=payload.start_date,
            end_date=payload.end_date,
            frequency=payload.frequency.value,
            weekdays=recurring_weekdays_value(payload.weekdays),
            start_time=payload.start_time,
            end_time=payload.end_time,
            status=RecurringSeriesStatus.active.value,
        )
        db.add(series)
        db.flush()
        detail = f"代约：{department} {user_name}" if is_proxy_booking else None
        log_action(db, actor, "create", "recurring_series", series.id, detail)

    for booking_date in recurring_dates(payload):
        start_at, end_at = validate_range(booking_date, payload.start_time, payload.end_time)
        if end_at <= now:
            expired.append(
                RecurringBookingItem(
                    booking_date=booking_date,
                    start_at=start_at,
                    end_at=end_at,
                    status="expired",
                    reason="已结束",
                )
            )
            continue
        conflict = find_conflict(db, payload.room_id, start_at, end_at)
        if conflict:
            conflicts.append(
                RecurringBookingItem(
                    booking_date=booking_date,
                    start_at=start_at,
                    end_at=end_at,
                    status="conflict",
                    reason="该时间段已被预约",
                    conflict_booking=conflict,
                )
            )
            continue
        booking = None
        if create:
            try:
                with db.begin_nested():
                    booking = Booking(
                        room_id=payload.room_id,
                        applicant_id=actor.id,
                        recurring_series_id=series.id if series else None,
                        campus=room.campus,
                        title=payload.title,
                        department=department,
                        user_name=user_name,
                        is_proxy_booking=is_proxy_booking,
                        attendee_count=payload.attendee_count,
                        note=payload.note,
                        start_at=start_at,
                        end_at=end_at,
                        status=BookingStatus.active.value,
                    )
                    db.add(booking)
                    db.flush()
                    detail = f"代约：{department} {user_name}" if is_proxy_booking else None
                    log_action(db, actor, "create", "booking", booking.id, detail)
            except IntegrityError:
                conflict = find_conflict(db, payload.room_id, start_at, end_at)
                conflicts.append(
                    RecurringBookingItem(
                        booking_date=booking_date,
                        start_at=start_at,
                        end_at=end_at,
                        status="conflict",
                        reason="该时间段已被预约",
                        conflict_booking=conflict,
                    )
                )
                continue
            booking = get_booking_or_404(db, booking.id)
        success.append(
            RecurringBookingItem(
                booking_date=booking_date,
                start_at=start_at,
                end_at=end_at,
                status="success",
                booking=booking,
            )
        )
    if create:
        db.commit()
        if series:
            series = get_recurring_series_or_404(db, series.id)
    return RecurringBookingResult(
        success=success,
        conflicts=conflicts,
        expired=expired,
        series=recurring_series_out(db, series) if series else None,
    )


def preview_recurring_bookings(db: Session, actor: User, payload: RecurringBookingRequest) -> RecurringBookingResult:
    return build_recurring_result(db, payload, actor, create=False)


def create_recurring_bookings(db: Session, actor: User, payload: RecurringBookingRequest) -> RecurringBookingResult:
    return build_recurring_result(db, payload, actor, create=True)


def recurring_series_scope(db: Session, actor: User, *, mine_only: bool = False):
    query = (
        db.query(RecurringSeries)
        .options(joinedload(RecurringSeries.room), joinedload(RecurringSeries.created_by))
        .order_by(RecurringSeries.created_at.desc())
    )
    if mine_only or actor.role != UserRole.admin.value:
        query = query.filter(RecurringSeries.created_by_id == actor.id)
    return query


def list_recurring_series(db: Session, actor: User, status_filter: str | None = None, mine_only: bool = False) -> list[dict]:
    query = recurring_series_scope(db, actor, mine_only=mine_only)
    if status_filter:
        query = query.filter(RecurringSeries.status == status_filter)
    return [recurring_series_out(db, series) for series in query.limit(200).all()]


def get_recurring_series_or_404(db: Session, series_id: int) -> RecurringSeries:
    series = (
        db.query(RecurringSeries)
        .options(joinedload(RecurringSeries.room), joinedload(RecurringSeries.created_by))
        .filter(RecurringSeries.id == series_id)
        .one_or_none()
    )
    if not series:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="周期预约组不存在")
    return series


def cancel_recurring_series(db: Session, actor: User, series_id: int) -> RecurringSeriesCancelResult:
    ensure_admin(actor)
    series = get_recurring_series_or_404(db, series_id)
    now = now_shanghai()
    future_bookings = (
        db.query(Booking)
        .options(joinedload(Booking.room), joinedload(Booking.applicant))
        .filter(
            Booking.recurring_series_id == series.id,
            Booking.status == BookingStatus.active.value,
            Booking.end_at > now,
        )
        .order_by(Booking.start_at.asc())
        .all()
    )
    skipped_expired_count = (
        db.query(Booking)
        .filter(
            Booking.recurring_series_id == series.id,
            Booking.status == BookingStatus.active.value,
            Booking.end_at <= now,
        )
        .count()
    )
    for booking in future_bookings:
        booking.status = BookingStatus.cancelled.value
        booking.cancelled_by_id = actor.id
        booking.cancelled_at = now
        log_action(db, actor, "cancel", "booking", booking.id)
    series.status = RecurringSeriesStatus.cancelled.value
    series.cancelled_by_id = actor.id
    series.cancelled_at = now
    log_action(db, actor, "cancel", "recurring_series", series.id)
    db.commit()
    series = get_recurring_series_or_404(db, series.id)
    return RecurringSeriesCancelResult(
        series=recurring_series_out(db, series),
        cancelled=future_bookings,
        skipped_expired_count=skipped_expired_count,
    )

def create_booking(db: Session, actor: User, payload: BookingCreate) -> Booking:
    room = check_room_available(db, payload.room_id)
    department, user_name, is_proxy_booking = resolve_usage_identity(
        actor,
        payload.is_proxy_booking,
        payload.department,
        payload.user_name,
    )
    start_at, end_at = validate_range(payload.booking_date, payload.start_time, payload.end_time)
    assert_not_past(end_at)
    if payload.attendee_count > room.capacity:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="参会人数超过会议室容量")
    assert_no_conflict(db, payload.room_id, start_at, end_at)
    booking = Booking(
        room_id=payload.room_id,
        applicant_id=actor.id,
        campus=room.campus,
        title=payload.title,
        department=department,
        user_name=user_name,
        is_proxy_booking=is_proxy_booking,
        attendee_count=payload.attendee_count,
        note=payload.note,
        start_at=start_at,
        end_at=end_at,
        status=BookingStatus.active.value,
    )
    db.add(booking)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该时间段已被预约") from exc
    detail = f"代约：{department} {user_name}" if is_proxy_booking else None
    log_action(db, actor, "create", "booking", booking.id, detail)
    db.commit()
    db.refresh(booking)
    return get_booking_or_404(db, booking.id)


def update_booking(db: Session, actor: User, booking: Booking, payload: BookingUpdate) -> Booking:
    ensure_can_manage_booking(actor, booking)
    if booking.status != BookingStatus.active.value:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="不能修改已取消预约")

    room_id = payload.room_id if payload.room_id is not None else booking.room_id
    room = check_room_available(db, room_id)
    booking_date = payload.booking_date or booking.start_at.astimezone(SHANGHAI).date()
    start_time = payload.start_time or booking.start_at.astimezone(SHANGHAI).strftime("%H:%M")
    end_local = booking.end_at.astimezone(SHANGHAI)
    end_time = payload.end_time or ("24:00" if end_local.date() == booking_date + timedelta(days=1) else end_local.strftime("%H:%M"))
    start_at, end_at = validate_range(booking_date, start_time, end_time)
    assert_not_past(end_at)

    attendee_count = payload.attendee_count if payload.attendee_count is not None else booking.attendee_count
    if attendee_count > room.capacity:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="参会人数超过会议室容量")
    assert_no_conflict(db, room_id, start_at, end_at, exclude_booking_id=booking.id)

    booking.room_id = room_id
    booking.campus = room.campus
    booking.start_at = start_at
    booking.end_at = end_at
    if payload.title is not None:
        booking.title = payload.title
    booking.attendee_count = attendee_count
    if "note" in payload.model_fields_set:
        booking.note = payload.note

    is_proxy_booking = payload.is_proxy_booking if "is_proxy_booking" in payload.model_fields_set else booking.is_proxy_booking
    department = payload.department if "department" in payload.model_fields_set else booking.department
    user_name = payload.user_name if "user_name" in payload.model_fields_set else booking.user_name
    booking.department, booking.user_name, booking.is_proxy_booking = resolve_usage_identity(
        booking.applicant,
        bool(is_proxy_booking),
        department,
        user_name,
    )

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该时间段已被预约") from exc
    detail = f"代约：{booking.department} {booking.user_name}" if booking.is_proxy_booking else None
    log_action(db, actor, "update", "booking", booking.id, detail)
    db.commit()
    return get_booking_or_404(db, booking.id)


def cancel_booking(db: Session, actor: User, booking: Booking) -> Booking:
    ensure_can_manage_booking(actor, booking)
    if booking.status == BookingStatus.cancelled.value:
        return booking
    from datetime import datetime

    if booking.end_at <= datetime.now(SHANGHAI):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="不能取消已结束预约")
    booking.status = BookingStatus.cancelled.value
    booking.cancelled_by_id = actor.id
    booking.cancelled_at = datetime.now(SHANGHAI)
    log_action(db, actor, "cancel", "booking", booking.id)
    db.commit()
    return get_booking_or_404(db, booking.id)


def active_bookings_for_day(db: Session, target: date, room_ids: list[int] | None = None) -> list[Booking]:
    start, end = day_bounds(target)
    return active_bookings_for_range(db, start, end, room_ids)


def active_bookings_for_range(db: Session, start, end, room_ids: list[int] | None = None) -> list[Booking]:
    query = (
        db.query(Booking)
        .options(joinedload(Booking.room), joinedload(Booking.applicant))
        .filter(Booking.status == BookingStatus.active.value, Booking.start_at < end, Booking.end_at > start)
        .order_by(Booking.start_at.asc())
    )
    if room_ids:
        query = query.filter(Booking.room_id.in_(room_ids))
    return query.all()


def booking_scope(db: Session, actor: User):
    query = db.query(Booking).options(joinedload(Booking.room), joinedload(Booking.applicant)).order_by(Booking.start_at.desc())
    if actor.role != UserRole.admin.value:
        query = query.filter(Booking.applicant_id == actor.id)
    return query
