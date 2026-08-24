from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

INPUT = Path("data/医务科会议室使用登记.xlsx")
OUTPUT_DIR = Path("data/cleaned")
ROOMS_CSV = OUTPUT_DIR / "rooms.csv"
BOOKINGS_CSV = OUTPUT_DIR / "bookings.csv"
REPORT_CSV = OUTPUT_DIR / "cleaning_report.csv"

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
REL_NS = {"pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
SHANGHAI = timezone(timedelta(hours=8))
TITLE = "历史会议室使用记录"
IMPORT_APPLICANT_STAFF_ID = "IMPORT"
FORCE_YEAR = 2026
ROOM_OVERRIDES = {
    "2号楼2楼第三会议室": {"name": "第三会议室", "location": "3号楼2楼", "capacity": "20", "description": ""},
    "谈话室二": {"name": "医务科谈话室2", "location": "5号楼2楼", "capacity": "10", "description": ""},
}


@dataclass(frozen=True)
class BookingRow:
    room_name: str
    applicant_staff_id: str
    title: str
    department: str
    user_name: str
    attendee_count: int
    note: str
    start_at: str
    end_at: str
    status: str


def col_to_idx(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    total = 0
    for ch in letters:
        total = total * 26 + ord(ch.upper()) - 64
    return total - 1


def excel_serial_to_date(value: str) -> date | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    # Excel 1900 date system, including Excel's leap-year bug offset.
    parsed = (datetime(1899, 12, 30) + timedelta(days=number)).date()
    return parsed.replace(year=FORCE_YEAR) if FORCE_YEAR else parsed


def cell_text(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    value = cell.find("a:v", NS)
    inline = cell.find("a:is", NS)
    if cell_type == "s" and value is not None:
        return shared[int(value.text or "0")].strip()
    if cell_type == "inlineStr" and inline is not None:
        return "".join(t.text or "" for t in inline.findall(".//a:t", NS)).strip()
    if value is not None:
        return (value.text or "").strip()
    return ""


def read_workbook(path: Path) -> dict[str, list[list[str]]]:
    with ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("a:si", NS):
                shared.append("".join(t.text or "" for t in item.findall(".//a:t", NS)))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall("pr:Relationship", REL_NS)}
        sheets: dict[str, list[list[str]]] = {}

        for sheet in workbook.findall("a:sheets/a:sheet", NS):
            name = sheet.attrib["name"].strip()
            rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rel_map[rid]
            sheet_path = "xl/" + target.lstrip("/")
            root = ET.fromstring(archive.read(sheet_path))
            rows: list[list[str]] = []
            for row in root.findall(".//a:sheetData/a:row", NS):
                values: list[str] = []
                last_idx = -1
                for cell in row.findall("a:c", NS):
                    idx = col_to_idx(cell.attrib.get("r", "A1"))
                    values.extend([""] * (idx - last_idx - 1))
                    values.append(cell_text(cell, shared))
                    last_idx = idx
                rows.append(values)
            sheets[name] = rows
        return sheets


def parse_time_range(value: str) -> tuple[time, time] | None:
    text = value.strip().replace("：", ":").replace(" ", "")
    if not text:
        return None
    text = text.replace("—", "-").replace("–", "-")
    match = re.match(r"^(\d{1,2})(?::?(\d{2}))?-(\d{1,2})(?::?(\d{2}))?$", text)
    if not match:
        return None
    sh, sm, eh, em = match.groups()
    start_hour = int(sh)
    start_minute = int(sm or 0)
    end_hour = int(eh)
    end_minute = int(em or 0)
    if not (0 <= start_hour <= 23 and 0 <= start_minute <= 59 and 1 <= end_hour <= 24 and 0 <= end_minute <= 59):
        return None
    if end_hour == 24 and end_minute != 0:
        return None
    return time(start_hour, start_minute), time(0, 0) if end_hour == 24 else time(end_hour, end_minute)


def as_minutes(value: time, *, end_is_24: bool = False) -> int:
    if end_is_24:
        return 24 * 60
    return value.hour * 60 + value.minute


def clean_room_name(sheet_name: str, rows: list[list[str]]) -> str:
    first = rows[0][0].strip() if rows and rows[0] else ""
    raw = first or sheet_name
    raw = re.sub(r"使用登记.*$", "", raw).strip()
    return raw or sheet_name


def room_location(room_name: str) -> str:
    match = re.search(r"（(.+?)）", room_name)
    return match.group(1).strip() if match else "暂无"


def normalize_room_name(room_name: str) -> str:
    return room_name.replace("（", "(").replace("）", ")")


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def row_get(row: list[str], idx: int) -> str:
    return row[idx].strip() if idx < len(row) else ""


def build_bookings(sheet_name: str, rows: list[list[str]]) -> tuple[dict[str, Any], list[BookingRow], list[dict[str, str]]]:
    room_raw = clean_room_name(sheet_name, rows)
    override = ROOM_OVERRIDES.get(sheet_name, {})
    room = {
        "name": override.get("name", normalize_room_name(room_raw)),
        "location": override.get("location", room_location(room_raw)),
        "capacity": override.get("capacity", "1"),
        "description": override.get("description", f"从 Excel sheet《{sheet_name}》清洗生成；容量待补充"),
        "is_active": "true",
    }

    report: list[dict[str, str]] = []
    bookings: list[BookingRow] = []
    if len(rows) < 5:
        report.append({"sheet": sheet_name, "level": "error", "message": "行数不足，无法解析"})
        return room, bookings, report

    date_row = rows[2]
    header_row = rows[3]
    date_by_col: dict[int, date] = {}
    for col_idx, value in enumerate(date_row):
        parsed = excel_serial_to_date(value)
        if not parsed:
            continue
        if row_get(header_row, col_idx) == "部门" and row_get(header_row, col_idx + 1) == "使用人":
            date_by_col[col_idx] = parsed

    if not date_by_col:
        report.append({"sheet": sheet_name, "level": "error", "message": "未识别到日期列"})
        return room, bookings, report

    raw_entries: list[dict[str, Any]] = []
    skipped_rows = 0
    for row_idx, row in enumerate(rows[4:], start=5):
        time_range = parse_time_range(row_get(row, 0))
        if not time_range:
            if any(compact_text(cell) for cell in row):
                skipped_rows += 1
            continue
        start_t, end_t = time_range
        start_minutes = as_minutes(start_t)
        end_is_24 = row_get(row, 0).strip().endswith("2400") or row_get(row, 0).strip().endswith("24:00")
        end_minutes = as_minutes(end_t, end_is_24=end_is_24)
        if end_minutes <= start_minutes:
            report.append({"sheet": sheet_name, "level": "warning", "message": f"跳过异常时间段 {row_get(row, 0)} 第{row_idx}行"})
            continue

        for dept_col, booking_date in date_by_col.items():
            department = compact_text(row_get(row, dept_col))
            user_name = compact_text(row_get(row, dept_col + 1))
            if not department and not user_name:
                continue
            if not department:
                department = "未知部门"
            if not user_name:
                user_name = "未知使用人"
            raw_entries.append({
                "date": booking_date,
                "start_minutes": start_minutes,
                "end_minutes": end_minutes,
                "department": department,
                "user_name": user_name,
            })

    raw_entries.sort(key=lambda item: (item["date"], item["department"], item["user_name"], item["start_minutes"], item["end_minutes"]))

    merged: list[dict[str, Any]] = []
    for item in raw_entries:
        previous = merged[-1] if merged else None
        if (
            previous
            and previous["date"] == item["date"]
            and previous["department"] == item["department"]
            and previous["user_name"] == item["user_name"]
            and previous["end_minutes"] == item["start_minutes"]
        ):
            previous["end_minutes"] = item["end_minutes"]
        else:
            merged.append(dict(item))

    for item in merged:
        start_at = datetime.combine(item["date"], time(item["start_minutes"] // 60, item["start_minutes"] % 60), SHANGHAI)
        if item["end_minutes"] == 24 * 60:
            end_at = datetime.combine(item["date"] + timedelta(days=1), time(0, 0), SHANGHAI)
        else:
            end_at = datetime.combine(item["date"], time(item["end_minutes"] // 60, item["end_minutes"] % 60), SHANGHAI)
        bookings.append(BookingRow(
            room_name=room["name"],
            applicant_staff_id=IMPORT_APPLICANT_STAFF_ID,
            title=TITLE,
            department=item["department"],
            user_name=item["user_name"],
            attendee_count=1,
            note=f"来源：{INPUT.name} / sheet《{sheet_name}》；由历史登记表清洗导入",
            start_at=start_at.isoformat(),
            end_at=end_at.isoformat(),
            status="active",
        ))

    year_note = f"，年份强制设为 {FORCE_YEAR}" if FORCE_YEAR else ""
    report.append({"sheet": sheet_name, "level": "info", "message": f"识别日期列 {len(date_by_col)} 个，原始占用 {len(raw_entries)} 条，合并后 {len(bookings)} 条，跳过非时间行 {skipped_rows} 行{year_note}"})
    return room, bookings, report


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sheets = read_workbook(INPUT)
    rooms: list[dict[str, Any]] = []
    bookings: list[BookingRow] = []
    report: list[dict[str, str]] = []

    for sheet_name, rows in sheets.items():
        room, room_bookings, room_report = build_bookings(sheet_name, rows)
        rooms.append(room)
        bookings.extend(room_bookings)
        report.extend(room_report)

    write_csv(ROOMS_CSV, ["name", "location", "capacity", "description", "is_active"], rooms)
    write_csv(BOOKINGS_CSV, [
        "room_name",
        "applicant_staff_id",
        "title",
        "department",
        "user_name",
        "attendee_count",
        "note",
        "start_at",
        "end_at",
        "status",
    ], [booking.__dict__ for booking in bookings])
    write_csv(REPORT_CSV, ["sheet", "level", "message"], report)

    print(f"rooms: {len(rooms)} -> {ROOMS_CSV}")
    print(f"bookings: {len(bookings)} -> {BOOKINGS_CSV}")
    print(f"report: {len(report)} -> {REPORT_CSV}")


if __name__ == "__main__":
    main()
