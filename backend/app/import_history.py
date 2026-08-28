import csv
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.campuses import CAMPUS_VALUES
from app.database import SessionLocal, init_db
from app.models import Booking, BookingStatus, Room, User, UserRole
from app.security import hash_password

IMPORT_STAFF_ID = "IMPORT"
IMPORT_USER_NAME = "历史数据导入"
IMPORT_DEPARTMENT = "医务科"


def bool_value(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "是", "启用"}


def campus_value(value: str, row_number: int) -> str:
    campus = value.strip()
    if campus not in CAMPUS_VALUES:
        raise ValueError(f"第 {row_number} 行院区无效：{campus or '空值'}")
    return campus


def get_or_create_import_user(db: Session) -> User:
    user = db.query(User).filter(User.staff_id == IMPORT_STAFF_ID).one_or_none()
    if user:
        user.name = IMPORT_USER_NAME
        user.department = IMPORT_DEPARTMENT
        user.role = UserRole.user.value
        user.is_active = False
        return user
    user = User(
        staff_id=IMPORT_STAFF_ID,
        name=IMPORT_USER_NAME,
        department=IMPORT_DEPARTMENT,
        role=UserRole.user.value,
        password_hash=hash_password("disabled-import-account"),
        is_active=False,
    )
    db.add(user)
    db.flush()
    return user


def import_rooms(path: Path, db: Session) -> tuple[int, int]:
    created = 0
    updated = 0
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"campus", "name", "location", "capacity", "description", "is_active"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("rooms.csv 必须包含表头：campus,name,location,capacity,description,is_active")
        for row_number, row in enumerate(reader, start=2):
            campus = campus_value(row.get("campus") or "", row_number)
            name = (row.get("name") or "").strip()
            if not name:
                continue
            payload = {
                "location": (row.get("location") or "暂无").strip() or "暂无",
                "capacity": int(row.get("capacity") or 1),
                "description": (row.get("description") or "").strip() or None,
                "is_active": bool_value(row.get("is_active") or "true"),
            }
            room = db.query(Room).filter(Room.campus == campus, Room.name == name).one_or_none()
            if room:
                room.location = payload["location"]
                room.capacity = payload["capacity"]
                room.description = payload["description"]
                room.is_active = payload["is_active"]
                updated += 1
            else:
                db.add(Room(campus=campus, name=name, **payload))
                created += 1
    db.flush()
    return created, updated


def active_overlap(db: Session, room_id: int, start_at: datetime, end_at: datetime) -> Booking | None:
    return (
        db.query(Booking)
        .filter(
            Booking.room_id == room_id,
            Booking.status == BookingStatus.active.value,
            Booking.start_at < end_at,
            Booking.end_at > start_at,
        )
        .order_by(Booking.start_at.asc())
        .first()
    )


def exact_duplicate(db: Session, room_id: int, start_at: datetime, end_at: datetime, department: str, user_name: str) -> Booking | None:
    return (
        db.query(Booking)
        .filter(
            Booking.room_id == room_id,
            Booking.status == BookingStatus.active.value,
            Booking.start_at == start_at,
            Booking.end_at == end_at,
            Booking.department == department,
            Booking.user_name == user_name,
        )
        .one_or_none()
    )


def import_bookings(path: Path, db: Session, import_user: User) -> dict[str, int]:
    stats = {"created": 0, "duplicates": 0, "conflicts": 0, "missing_rooms": 0}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"campus", "room_name", "title", "department", "user_name", "attendee_count", "note", "start_at", "end_at", "status"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("bookings.csv 表头不完整")
        for row_number, row in enumerate(reader, start=2):
            campus = campus_value(row.get("campus") or "", row_number)
            room_name = (row.get("room_name") or "").strip()
            room = db.query(Room).filter(Room.campus == campus, Room.name == room_name).one_or_none()
            if not room:
                stats["missing_rooms"] += 1
                print(f"跳过：会议室不存在 {campus} · {room_name}")
                continue
            start_at = datetime.fromisoformat((row.get("start_at") or "").strip())
            end_at = datetime.fromisoformat((row.get("end_at") or "").strip())
            department = (row.get("department") or "未知部门").strip() or "未知部门"
            user_name = (row.get("user_name") or "未知使用人").strip() or "未知使用人"
            if exact_duplicate(db, room.id, start_at, end_at, department, user_name):
                stats["duplicates"] += 1
                continue
            conflict = active_overlap(db, room.id, start_at, end_at)
            if conflict:
                stats["conflicts"] += 1
                print(f"冲突跳过：{room.name} {start_at.isoformat()}-{end_at.isoformat()} 与 booking_id={conflict.id} 冲突")
                continue
            db.add(
                Booking(
                    room_id=room.id,
                    applicant_id=import_user.id,
                    campus=campus,
                    title=(row.get("title") or "历史会议室使用记录").strip() or "历史会议室使用记录",
                    department=department,
                    user_name=user_name,
                    attendee_count=int(row.get("attendee_count") or 1),
                    note=(row.get("note") or "").strip() or None,
                    start_at=start_at,
                    end_at=end_at,
                    status=(row.get("status") or BookingStatus.active.value).strip() or BookingStatus.active.value,
                )
            )
            stats["created"] += 1
    db.flush()
    return stats


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("用法：python -m app.import_history /app/data/cleaned/rooms.csv /app/data/cleaned/bookings.csv")
    rooms_path = Path(sys.argv[1])
    bookings_path = Path(sys.argv[2])
    if not rooms_path.exists():
        raise FileNotFoundError(rooms_path)
    if not bookings_path.exists():
        raise FileNotFoundError(bookings_path)

    init_db()
    db = SessionLocal()
    try:
        import_user = get_or_create_import_user(db)
        room_created, room_updated = import_rooms(rooms_path, db)
        booking_stats = import_bookings(bookings_path, db, import_user)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"会议室导入完成：新增 {room_created}，更新 {room_updated}")
    print(
        "预约导入完成："
        f"新增 {booking_stats['created']}，"
        f"重复跳过 {booking_stats['duplicates']}，"
        f"冲突跳过 {booking_stats['conflicts']}，"
        f"会议室缺失 {booking_stats['missing_rooms']}"
    )


if __name__ == "__main__":
    main()
