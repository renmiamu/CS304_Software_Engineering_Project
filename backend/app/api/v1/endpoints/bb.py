from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user_id
from app.core.database import get_db_sync
from app.db.CRUD import add_ddl_by_user_id, delete_ddl_by_id, list_deadlines_by_user_id, update_deadline
from app.schemas.bb import (
    BBCalendarQueryRequest,
    BBCalendarCreateRequest,
    BBCalendarItem,
    BBCalendarItemsResponse,
    BBCalendarResponse,
    BBCalendarUpdateRequest,
    BBCoursesResponse,
    BBFilesResponse,
    BBGradesResponse,
    BBQueryRequest,
)
from app.services.bb_service import (
    get_bb_calendar_service,
    get_bb_courses_service,
    get_bb_files_service,
    get_bb_grades_service,
)

router = APIRouter(prefix="/bb", tags=["bb"])


def _to_calendar_item(row: object) -> BBCalendarItem:
    return BBCalendarItem(
        id=int(getattr(row, "id")),
        completed=bool(getattr(row, "is_completed", 0)),
        color=getattr(row, "color"),
        userCreated=bool(getattr(row, "is_user_created")),
        calendarName=getattr(row, "calendar_name"),
        end=getattr(row, "end_time"),
        title=getattr(row, "title"),
        eventType=getattr(row, "event_type"),
    )


@router.post("/courses", response_model=BBCoursesResponse)
async def courses_endpoint(
    request: BBQueryRequest,
    cookies_file: str = Query(default="clients/resources/cookies.json"),
) -> BBCoursesResponse:
    data = get_bb_courses_service(cookies_file=cookies_file, term_filter=request.term_filter)
    return BBCoursesResponse(**data)


@router.post("/calendar", response_model=BBCalendarResponse)
async def calendar_endpoint(
    request: BBCalendarQueryRequest | None = None,
    cookies_file: str = Query(default="clients/resources/cookies.json"),
    user_id: int = Depends(get_current_user_id),
) -> BBCalendarResponse:
    try:
        payload = request or BBCalendarQueryRequest()
        data = get_bb_calendar_service(
            cookies_file=cookies_file,
            start_timestamp=payload.start_timestamp,
            end_timestamp=payload.end_timestamp,
            user_id=user_id,
        )
        return BBCalendarResponse(**data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"BB calendar failed: {exc}") from exc


@router.get("/calendar/items", response_model=BBCalendarItemsResponse)
async def list_calendar_items_endpoint(
    user_id: int = Depends(get_current_user_id),
) -> BBCalendarItemsResponse:
    db = get_db_sync()
    try:
        rows = list_deadlines_by_user_id(db, user_id)
        return BBCalendarItemsResponse(events=[_to_calendar_item(row) for row in rows])
    finally:
        db.close()


@router.post("/calendar/items", response_model=BBCalendarItem)
async def create_calendar_item_endpoint(
    request: BBCalendarCreateRequest,
    user_id: int = Depends(get_current_user_id),
) -> BBCalendarItem:
    db = get_db_sync()
    try:
        created = add_ddl_by_user_id(
            db,
            user_id,
            {
                "title": request.title,
                "end_time": request.end,
                "completed": request.completed,
                "calendar_name": request.calendarName,
                "event_type": request.eventType,
                "color": request.color,
            },
        )
        if request.userCreated is False and created.is_user_created != 0:
            updated = update_deadline(db, created.id, is_user_created=0)
            if updated is not None:
                created = updated
        return _to_calendar_item(created)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        db.close()


@router.patch("/calendar/items/{ddl_id}", response_model=BBCalendarItem)
async def update_calendar_item_endpoint(
    ddl_id: int,
    request: BBCalendarUpdateRequest,
    user_id: int = Depends(get_current_user_id),
) -> BBCalendarItem:
    db = get_db_sync()
    try:
        rows = list_deadlines_by_user_id(db, user_id)
        target = next((row for row in rows if int(getattr(row, "id")) == ddl_id), None)
        if target is None:
            raise HTTPException(status_code=404, detail="Calendar item not found")

        updates = {}
        if request.title is not None:
            updates["title"] = request.title
        if request.end is not None:
            updates["end_time"] = request.end
        if request.completed is not None:
            updates["is_completed"] = 1 if request.completed else 0
        if request.color is not None:
            updates["color"] = request.color
        if request.calendarName is not None:
            updates["calendar_name"] = request.calendarName
        if request.eventType is not None:
            updates["event_type"] = request.eventType
        if request.userCreated is not None:
            updates["is_user_created"] = 1 if request.userCreated else 0

        if not updates:
            return _to_calendar_item(target)

        updated = update_deadline(db, ddl_id, **updates)
        if updated is None:
            raise HTTPException(status_code=404, detail="Calendar item not found")
        return _to_calendar_item(updated)
    finally:
        db.close()


@router.delete("/calendar/items/{ddl_id}")
async def delete_calendar_item_endpoint(
    ddl_id: int,
    user_id: int = Depends(get_current_user_id),
) -> dict[str, object]:
    db = get_db_sync()
    try:
        deleted = delete_ddl_by_id(db, user_id=user_id, ddl_id=ddl_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Calendar item not found")
        return {"deleted": True, "id": ddl_id}
    finally:
        db.close()


@router.post("/grades", response_model=BBGradesResponse)
async def grades_endpoint(
    request: BBQueryRequest,
    cookies_file: str = Query(default="clients/resources/cookies.json"),
    user_id: int = Depends(get_current_user_id),
) -> BBGradesResponse:
    data = get_bb_grades_service(cookies_file=cookies_file, term_filter=request.term_filter, user_id=user_id)
    return BBGradesResponse(**data)


@router.post("/files", response_model=BBFilesResponse)
async def files_endpoint(
    request: BBQueryRequest,
    cookies_file: str = Query(default="clients/resources/cookies.json"),
    user_id: int = Depends(get_current_user_id),
) -> BBFilesResponse:
    data = get_bb_files_service(cookies_file=cookies_file, term_filter=request.term_filter, user_id=user_id)
    return BBFilesResponse(**data)
