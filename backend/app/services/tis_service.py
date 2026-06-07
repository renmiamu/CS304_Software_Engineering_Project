import base64
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.clients.tis.credit import query_credits
from app.clients.tis.grade import query_grades
from app.clients.tis.infor import query_tis_data
from app.clients.tis.photo import download_student_photo, get_tis_id
from app.clients.tis.schedule import fetch_and_process_schedule
from app.core.database import get_db_sync
from app.db.models.entities import Schedule
from app.db.CRUD import get_credits_by_user_id, upsert_credits
from app.db.CRUD.user import get_user_by_id, update_user
from app.schemas.tis import TisScheduleQueryRequest


RESOURCE_DIR = Path(__file__).resolve().parents[1] / "clients" / "resources"
DEFAULT_COOKIES_FILE = str(RESOURCE_DIR / "cookies.json")

WEEKDAY_TO_INT = {
    "星期一": 1,
    "星期二": 2,
    "星期三": 3,
    "星期四": 4,
    "星期五": 5,
    "星期六": 6,
    "星期日": 7,
}

INT_TO_WEEKDAY = {value: key for key, value in WEEKDAY_TO_INT.items()}


def _ensure_user_exists(user_id: int) -> None:
    db = get_db_sync()
    try:
        if get_user_by_id(db, user_id) is None:
            raise HTTPException(status_code=400, detail=f"User not found: user_id={user_id}")
    finally:
        db.close()


def _build_profile_updates(data: dict[str, Any]) -> dict[str, Any]:
    updates = {
        "name": data.get("name"),
        "pinyin_name": data.get("pinyin_name"),
        "gender": data.get("gender"),
        "birth_date": data.get("birth_date"),
        "college": data.get("college"),
        "dormitory": data.get("dormitory"),
        "phone": data.get("phone"),
        "email": data.get("email"),
        "department": data.get("department"),
    }
    return {key: value for key, value in updates.items() if value is not None}


def get_schedule_service(
    request: TisScheduleQueryRequest,
    cookies_file: str = DEFAULT_COOKIES_FILE,
    user_id: int = 0,
) -> list[dict[str, str]]:
    _ensure_user_exists(user_id)

    db = get_db_sync()
    try:
        user = get_user_by_id(db, user_id)
        if user is None:
            raise HTTPException(status_code=400, detail=f"User not found: user_id={user_id}")

        courses: list[dict[str, str]] = []
        for item in user.schedules:
            description = str(item.description or "")
            weeks = ""
            time_slots = ""
            if " | " in description:
                parts = description.split(" | ", 1)
                weeks = parts[0]
                time_slots = parts[1]
            elif description:
                weeks = description

            courses.append(
                {
                    "course_name": str(item.name or ""),
                    "teacher": str(item.teacher or ""),
                    "weekday": INT_TO_WEEKDAY.get(item.weekday, ""),
                    "weeks": weeks,
                    "location": str(item.location or ""),
                    "time_slots": time_slots,
                }
            )

        return courses
    finally:
        db.close()


def sync_schedule_service(
    request: TisScheduleQueryRequest,
    cookies_file: str = DEFAULT_COOKIES_FILE,
    user_id: int = 0,
) -> dict[str, Any]:
    _ensure_user_exists(user_id)

    form = {"xn": request.xn, "xq": request.xq, "bs": request.bs}
    courses = fetch_and_process_schedule(cookies_file=cookies_file, form=form, debug=False)

    db = get_db_sync()
    try:
        user = get_user_by_id(db, user_id)
        if user is None:
            raise HTTPException(status_code=400, detail=f"User not found: user_id={user_id}")

        for item in courses:
            name = str(item.get("course_name") or "").strip()
            if not name:
                continue

            teacher = str(item.get("teacher") or "").strip() or None
            location = str(item.get("location") or "").strip() or None
            weekday_raw = str(item.get("weekday") or "").strip()
            weekday = WEEKDAY_TO_INT.get(weekday_raw)
            weeks = str(item.get("weeks") or "").strip()
            time_slots = str(item.get("time_slots") or "").strip()
            description = " | ".join(x for x in [weeks, time_slots] if x) or None

            schedule = (
                db.query(Schedule)
                .filter(
                    Schedule.name == name,
                    Schedule.teacher == teacher,
                    Schedule.location == location,
                    Schedule.weekday == weekday,
                    Schedule.description == description,
                    Schedule.schedule_type == "course",
                )
                .first()
            )

            if schedule is None:
                schedule = Schedule(
                    name=name,
                    location=location,
                    teacher=teacher,
                    weekday=weekday,
                    description=description,
                    schedule_type="course",
                )
                db.add(schedule)
                db.flush()

            if schedule not in user.schedules:
                user.schedules.append(schedule)

        db.commit()
    finally:
        db.close()

    return {"fetched": len(courses), "synced": True}


def get_grade_service(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    user_id: int = 0,
) -> dict[str, Any]:
    _ensure_user_exists(user_id)

    db = get_db_sync()
    try:
        user = get_user_by_id(db, user_id)
        if user is None:
            raise HTTPException(status_code=400, detail=f"User not found: user_id={user_id}")

        if user.gpa is None and user.rank is None:
            raise HTTPException(status_code=404, detail="No TIS GPA/Rank found in database, please sync first")

        return {"GPA": user.gpa, "Rank": user.rank}
    finally:
        db.close()


def sync_grade_service(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    user_id: int = 0,
) -> dict[str, Any]:
    _ensure_user_exists(user_id)

    result = query_grades(cookies_file=cookies_file)
    if not result:
        raise HTTPException(status_code=502, detail="Failed to fetch TIS GPA/Rank")

    gpa_raw = result.get("GPA")
    gpa_value: float | None = None
    if gpa_raw is not None:
        try:
            gpa_value = float(gpa_raw)
        except (TypeError, ValueError):
            gpa_value = None

    rank_raw = result.get("Rank")
    rank_value = None if rank_raw is None else str(rank_raw)

    db = get_db_sync()
    try:
        update_user(
            db,
            user_id=user_id,
            gpa=gpa_value,
            rank=rank_value,
        )
    finally:
        db.close()

    return {"synced": True}


def get_credit_service(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    user_id: int = 0,
) -> dict[str, Any]:
    _ensure_user_exists(user_id)

    db = get_db_sync()
    try:
        credits = get_credits_by_user_id(db, user_id)
        if credits is None:
            raise HTTPException(status_code=404, detail="No TIS credits found in database, please sync first")

        return {
            "total_credit": float(credits.total_credit or 0.0),
            "category_credit": credits.category_credit or {},
        }
    finally:
        db.close()


def sync_credit_service(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    user_id: int = 0,
) -> dict[str, Any]:
    _ensure_user_exists(user_id)

    result = query_credits(cookies_file=cookies_file)
    if not result:
        raise HTTPException(status_code=502, detail="Failed to fetch TIS credits")

    db = get_db_sync()
    try:
        # Credits table columns: user_id/total_credit/category_credit.
        upsert_credits(
            db,
            user_id=user_id,
            total_credit=result.get("total_credit"),
            category_credit=result.get("category_credit"),
        )
    finally:
        db.close()

    return {"synced": True}


def get_info_service(
    query_params: dict[str, Any] | None = None,
    cookies_file: str = DEFAULT_COOKIES_FILE,
) -> dict[str, Any]:
    result = query_tis_data(query_params=query_params, cookies_file=cookies_file, output_file=None, debug=False)
    if result is None:
        raise HTTPException(status_code=502, detail="Failed to fetch TIS info")
    return {"data": result}


def sync_info_service(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    user_id: int = 0,
) -> dict[str, Any]:
    _ensure_user_exists(user_id)

    result = query_tis_data(cookies_file=cookies_file, output_file=None, debug=False)
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="Failed to fetch TIS info")

    updates = _build_profile_updates(result)
    if not updates:
        raise HTTPException(status_code=502, detail="No TIS profile fields available to sync")

    db = get_db_sync()
    try:
        user = update_user(db, user_id=user_id, **updates)
        if user is None:
            raise HTTPException(status_code=400, detail=f"User not found: user_id={user_id}")
    finally:
        db.close()

    return {"synced": True, "updated_fields": sorted(updates.keys())}


def get_tis_id_service(cookies_file: str = DEFAULT_COOKIES_FILE) -> dict[str, Any]:
    return {"tis_id": get_tis_id(cookies_file=cookies_file)}


def get_photo_service(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    user_id: int = 0,
) -> dict[str, Any]:
    _ensure_user_exists(user_id)

    db = get_db_sync()
    try:
        user = get_user_by_id(db, user_id)
        if user is None:
            raise HTTPException(status_code=400, detail=f"User not found: user_id={user_id}")

        photo_base64 = str(user.photo or "").strip()
        if not photo_base64:
            raise HTTPException(status_code=404, detail="No TIS photo found in database, please sync first")
    finally:
        db.close()

    size = 0
    try:
        size = len(base64.b64decode(photo_base64, validate=False))
    except Exception:
        size = 0

    return {
        "base64": photo_base64,
        "filename": f"{user_id}_photo.jpg",
        "size": size,
        "type": "jpg",
        "saved_path": None,
    }


def sync_photo_service(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    user_id: int = 0,
) -> dict[str, Any]:
    _ensure_user_exists(user_id)

    photo = download_student_photo(
        cookies_file=cookies_file,
    )
    if not photo:
        raise HTTPException(status_code=502, detail="Failed to download TIS photo")

    db = get_db_sync()
    try:
        update_user(db, user_id=user_id, photo=photo.get("base64"))
    finally:
        db.close()

    return {"synced": True}
