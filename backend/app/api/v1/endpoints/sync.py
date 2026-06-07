from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user_id
from app.schemas.bb import BBCalendarQueryRequest, BBQueryRequest
from app.schemas.tis import TisScheduleQueryRequest
from app.services.bb_service import (
    sync_bb_calendar_service,
    sync_bb_files_service,
    sync_bb_grades_service,
)
from app.services.tis_service import (
    DEFAULT_COOKIES_FILE,
    sync_credit_service,
    sync_grade_service,
    sync_info_service,
    sync_photo_service,
    sync_schedule_service,
)

router = APIRouter(prefix="/sync", tags=["sync"])


def _safe_sync_call(label: str, fn: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    print(f"[SYNC] {label}: start")
    try:
        data = fn(*args, **kwargs)
        print(f"[SYNC] {label}: success")
        return {"ok": True, "data": data}
    except HTTPException as exc:
        print(f"[SYNC] {label}: failed (status={exc.status_code}, detail={exc.detail})")
        return {
            "ok": False,
            "status_code": exc.status_code,
            "error": f"{label} failed: {exc.detail}",
        }
    except Exception as exc:
        print(f"[SYNC] {label}: failed (status=500, detail={exc})")
        return {"ok": False, "status_code": 500, "error": f"{label} failed: {exc}"}


@router.post("/all")
async def sync_all_endpoint(
    cookies_file: str = Query(default=DEFAULT_COOKIES_FILE),
    user_id: int = Depends(get_current_user_id),
) -> dict[str, Any]:
    tis_schedule_request = TisScheduleQueryRequest()
    bb_query_request = BBQueryRequest()
    bb_calendar_request = BBCalendarQueryRequest()

    tis_schedule = _safe_sync_call(
        "tis_schedule",
        sync_schedule_service,
        tis_schedule_request,
        cookies_file=cookies_file,
        user_id=user_id,
    )
    tis_info = _safe_sync_call("tis_info", sync_info_service, cookies_file=cookies_file, user_id=user_id)
    tis_grade = _safe_sync_call("tis_grade", sync_grade_service, cookies_file=cookies_file, user_id=user_id)
    tis_credit = _safe_sync_call("tis_credit", sync_credit_service, cookies_file=cookies_file, user_id=user_id)
    tis_photo = _safe_sync_call("tis_photo", sync_photo_service, cookies_file=cookies_file, user_id=user_id)

    bb_calendar = _safe_sync_call(
        "bb_calendar",
        sync_bb_calendar_service,
        cookies_file=cookies_file,
        start_timestamp=bb_calendar_request.start_timestamp,
        end_timestamp=bb_calendar_request.end_timestamp,
        user_id=user_id,
    )
    bb_grades = _safe_sync_call(
        "bb_grades",
        sync_bb_grades_service,
        cookies_file=cookies_file,
        term_filter=bb_query_request.term_filter,
        user_id=user_id,
    )
    bb_files = _safe_sync_call(
        "bb_files",
        sync_bb_files_service,
        cookies_file=cookies_file,
        term_filter=bb_query_request.term_filter,
        user_id=user_id,
    )

    result: dict[str, Any] = {
        "user_id": user_id,
        "sync_summary": {
            "tis": {
                "schedule": tis_schedule,
                "info": tis_info,
                "grade": tis_grade,
                "credit": tis_credit,
                "photo": tis_photo,
            },
            "bb": {
                "calendar": bb_calendar,
                "grades": bb_grades,
                "files": bb_files,
            },
        },
    }

    return result
