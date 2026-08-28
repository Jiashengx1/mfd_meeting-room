from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

SHANGHAI = ZoneInfo("Asia/Shanghai")
ALLOWED_MINUTES = {0, 30}
OPEN_HOUR = 7
CLOSE_HOUR = 18


def now_shanghai() -> datetime:
    return datetime.now(SHANGHAI)


def parse_hhmm(value: str, *, allow_2400: bool = False) -> tuple[int, int]:
    try:
        hour_s, minute_s = value.split(":", 1)
        hour = int(hour_s)
        minute = int(minute_s)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="时间格式必须为 HH:MM") from exc
    max_hour = 24 if allow_2400 else 23
    if hour < 0 or hour > max_hour or minute not in ALLOWED_MINUTES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="时间必须为 30 分钟粒度")
    if hour == 24 and minute != 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="24:00 只能作为结束时间")
    return hour, minute


def combine_local(day: date, value: str, *, is_end: bool = False) -> datetime:
    hour, minute = parse_hhmm(value, allow_2400=is_end)
    if hour == 24:
        return datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=SHANGHAI)
    return datetime.combine(day, time(hour, minute), tzinfo=SHANGHAI)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    return datetime.combine(day, time(0, 0), tzinfo=SHANGHAI), datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=SHANGHAI)


def validate_range(day: date, start_time: str, end_time: str) -> tuple[datetime, datetime]:
    start_at = combine_local(day, start_time, is_end=False)
    end_at = combine_local(day, end_time, is_end=True)
    if end_at <= start_at:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="结束时间必须晚于开始时间")
    if start_at.date() != day or (end_at.date() not in {day, day + timedelta(days=1)}):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="预约不允许跨日期")
    if end_at.date() == day + timedelta(days=1) and end_at.time() != time(0, 0):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="预约不允许跨日期")
    open_at = datetime.combine(day, time(OPEN_HOUR, 0), tzinfo=SHANGHAI)
    close_at = datetime.combine(day, time(CLOSE_HOUR, 0), tzinfo=SHANGHAI)
    if start_at < open_at or end_at > close_at:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="预约时间必须在 07:00-18:00 之间")
    return start_at, end_at


def assert_not_past(end_at: datetime) -> None:
    if end_at <= now_shanghai():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="不能预约过去时间")
