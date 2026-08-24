import csv
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import User, UserRole
from app.security import hash_password

ROLE_VALUES = {UserRole.admin.value, UserRole.user.value}


def import_staff(csv_path: Path, db: Session) -> tuple[int, int]:
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    created = 0
    updated = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"id", "姓名", "科室", "角色"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("staff.csv 必须包含表头：id,姓名,科室,角色")
        for row in reader:
            staff_id = (row.get("id") or "").strip()
            name = (row.get("姓名") or "").strip()
            department = (row.get("科室") or "").strip()
            role = (row.get("角色") or "").strip()
            if not any((staff_id, name, department, role)):
                continue
            if not staff_id or not name or not department or role not in ROLE_VALUES:
                raise ValueError(f"无效员工行：{row}")
            user = db.query(User).filter(User.staff_id == staff_id).one_or_none()
            if user:
                user.name = name
                user.department = department
                user.role = role
                user.password_hash = hash_password(staff_id)
                user.is_active = True
                updated += 1
            else:
                db.add(
                    User(
                        staff_id=staff_id,
                        name=name,
                        department=department,
                        role=role,
                        password_hash=hash_password(staff_id),
                        is_active=True,
                    )
                )
                created += 1
    db.commit()
    return created, updated


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("用法：python -m app.import_staff /app/staff.csv")
    init_db()
    db = SessionLocal()
    try:
        created, updated = import_staff(Path(sys.argv[1]), db)
    finally:
        db.close()
    print(f"导入完成：新增 {created}，更新 {updated}")


if __name__ == "__main__":
    main()
