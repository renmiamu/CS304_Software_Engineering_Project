import json
from typing import Any

from fastapi import HTTPException

from app.core.database import get_db_sync
from app.db.CRUD import (
    create_bb_files_from_json,
    list_bb_files_by_user_id,
    list_bb_grades_by_user_id,
    list_deadlines_by_user_id,
    replace_bb_grades,
    save_ddl_to_db,
)
from app.db.CRUD.user import get_user_by_id
from app.clients.bb.calendar import get_bb_calendar
from app.clients.bb.course import get_bb_courses
from app.clients.bb.download import crawl_bb_files
from app.clients.bb.grade import crawl_bb_grades


DEFAULT_COOKIES_FILE = "clients/resources/cookies.json"


def _ensure_user_exists(user_id: int) -> None:
    db = get_db_sync()
    try:
        if get_user_by_id(db, user_id) is None:
            raise HTTPException(status_code=400, detail=f"User not found: user_id={user_id}")
    finally:
        db.close()


def get_bb_courses_service(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    term_filter: str | None = "2026春",
) -> dict[str, Any]:
    courses = get_bb_courses(cookies_file=cookies_file, term_filter=term_filter)
    return {"courses": courses}


def get_bb_calendar_service(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    start_timestamp: int | None = None,
    end_timestamp: int | None = None,
    user_id: int = 0,
) -> dict[str, Any]:
    _ensure_user_exists(user_id)

    db = get_db_sync()
    try:
        ddls = list_deadlines_by_user_id(db, user_id)
        if not ddls:
            raise HTTPException(status_code=404, detail="No BB calendar found in database, please sync first")

        events = [
            {
                "completed": bool(item.is_completed),
                "color": item.color,
                "userCreated": bool(item.is_user_created),
                "calendarName": item.calendar_name,
                "end": item.end_time,
                "title": item.title,
                "eventType": item.event_type,
            }
            for item in ddls
        ]
        return {"events": events}
    finally:
        db.close()


def sync_bb_calendar_service(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    start_timestamp: int | None = None,
    end_timestamp: int | None = None,
    user_id: int = 0,
) -> dict[str, Any]:
    _ensure_user_exists(user_id)

    events = get_bb_calendar(
        cookies_file=cookies_file,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
    )
    if events is None:
        raise HTTPException(status_code=502, detail="Failed to fetch BB calendar")

    db = get_db_sync()
    try:
        # Deadline only stores these event fields and user_id.
        created = save_ddl_to_db(db, user_id=user_id, schedule=events)
    finally:
        db.close()

    return {"fetched": len(events), "inserted": created}


def get_bb_grades_service(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    term_filter: str | None = "2026春",
    user_id: int = 0,
) -> dict[str, Any]:
    _ensure_user_exists(user_id)

    db = get_db_sync()
    try:
        rows = list_bb_grades_by_user_id(db, user_id)
        if not rows:
            raise HTTPException(status_code=404, detail="No BB grades found in database, please sync first")

        grades = [
            {
                "course_id": str(item.course_id or ""),
                "course_name": str(item.course_name or ""),
                "item_name": str(item.item_name or ""),
                "full_grade": str(item.full_grade or ""),
            }
            for item in rows
        ]
        return {"grades": grades}
    finally:
        db.close()


def sync_bb_grades_service(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    term_filter: str | None = "2026春",
    user_id: int = 0,
) -> dict[str, Any]:
    _ensure_user_exists(user_id)

    grades = crawl_bb_grades(cookies_file=cookies_file, term_filter=term_filter)

    db = get_db_sync()
    try:
        # BBGrade table columns: user_id/course_id/course_name/item_name/full_grade.
        replaced = replace_bb_grades(db, user_id=user_id, items=grades)
    finally:
        db.close()

    return {"fetched": len(grades), "replaced": replaced}


def get_bb_files_service(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    term_filter: str | None = "2026春",
    user_id: int = 0,
) -> dict[str, Any]:
    _ensure_user_exists(user_id)

    db = get_db_sync()
    try:
        rows = list_bb_files_by_user_id(db, user_id)
        if not rows:
            raise HTTPException(status_code=404, detail="No BB files found in database, please sync first")

        files = [
            {
                "course": str(item.course or ""),
                "content": str(item.content or ""),
                "file_url": str(item.file_url or ""),
                "file_name": str(item.file_name or ""),
            }
            for item in rows
        ]
        return {"files": files}
    finally:
        db.close()


def sync_bb_files_service(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    term_filter: str | None = "2026春",
    user_id: int = 0,
) -> dict[str, Any]:
    _ensure_user_exists(user_id)

    try:
        raw_json = crawl_bb_files(cookies_file=cookies_file, term_filter=term_filter)
        files = json.loads(raw_json)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch BB files: {exc}") from exc

    if not isinstance(files, list):
        raise HTTPException(status_code=502, detail="Unexpected BB files response format")

    db = get_db_sync()
    try:
        # BBFile table columns: user_id/course/content/file_url/file_name.
        inserted = create_bb_files_from_json(db, user_id=user_id, files_json=raw_json)
    finally:
        db.close()

    return {"fetched": len(files), "inserted": inserted}
