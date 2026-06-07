from datetime import time
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db, get_db_sync
from app.core.security import get_current_user_id
from app.db.CRUD.schedule import (
    assign_schedule_to_user,
    create_schedule,
    get_schedule_by_id,
    remove_schedule_from_user,
)
from app.db.CRUD.user import get_user_by_id
from app.db.models.entities import Schedule
from app.schemas.tis import (
    ScheduleEventCreate,
    ScheduleEventResponse,
    ScheduleEventUpdate,
)

router = APIRouter(prefix="/schedule", tags=["schedule"])

INT_TO_WEEKDAY: dict = {
    1: "星期一", 2: "星期二", 3: "星期三", 4: "星期四",
    5: "星期五", 6: "星期六", 7: "星期日",
}


def _schedule_to_response(item: Schedule) -> ScheduleEventResponse:
    description = str(item.description or "")
    return ScheduleEventResponse(
        schedule_id=item.schedule_id,
        name=item.name,
        location=item.location or "",
        start_time=item.start_time.strftime("%H:%M") if item.start_time else "",
        end_time=item.end_time.strftime("%H:%M") if item.end_time else "",
        teacher=item.teacher or "",
        weekday=item.weekday,
        description=description,
        schedule_type=item.schedule_type or "",
    )


def _time_from_str(value: str) -> time | None:
    v = value.strip()
    if not v:
        return None
    try:
        return time.fromisoformat(v)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid time: {v}")


@router.get("/events", response_model=List[ScheduleEventResponse])
def list_schedule_events(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return [_schedule_to_response(s) for s in user.schedules]


@router.post("/events", response_model=ScheduleEventResponse, status_code=201)
def create_schedule_event(
    body: ScheduleEventCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="name is required")

    payload: dict[str, Any] = {"name": body.name.strip()}
    if body.location:
        payload["location"] = body.location.strip()
    if body.weekday is not None:
        if not 1 <= body.weekday <= 7:
            raise HTTPException(status_code=400, detail="weekday must be 1-7")
        payload["weekday"] = body.weekday
    if body.start_time:
        payload["start_time"] = _time_from_str(body.start_time)
    if body.end_time:
        payload["end_time"] = _time_from_str(body.end_time)
    if body.teacher:
        payload["teacher"] = body.teacher.strip()
    if body.description:
        payload["description"] = body.description.strip()
    if body.schedule_type:
        payload["schedule_type"] = body.schedule_type.strip()

    schedule = create_schedule(db, **payload)
    assign_schedule_to_user(db, user_id, schedule.schedule_id)
    db.refresh(schedule)
    return _schedule_to_response(schedule)


@router.patch("/events/{event_id}", response_model=ScheduleEventResponse)
def update_schedule_event(
    event_id: int,
    body: ScheduleEventUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    schedule = get_schedule_by_id(db, event_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if schedule not in user.schedules:
        raise HTTPException(status_code=403, detail="Event does not belong to current user")

    updates: dict[str, Any] = {}
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(status_code=400, detail="name must not be empty")
        updates["name"] = body.name.strip()
    if body.location is not None:
        updates["location"] = body.location.strip() if body.location else None
    if body.weekday is not None:
        if not 1 <= body.weekday <= 7:
            raise HTTPException(status_code=400, detail="weekday must be 1-7")
        updates["weekday"] = body.weekday
    if body.start_time is not None:
        updates["start_time"] = _time_from_str(body.start_time) if body.start_time else None
    if body.end_time is not None:
        updates["end_time"] = _time_from_str(body.end_time) if body.end_time else None
    if body.teacher is not None:
        updates["teacher"] = body.teacher.strip() if body.teacher else None
    if body.description is not None:
        updates["description"] = body.description.strip() if body.description else None
    if body.schedule_type is not None:
        updates["schedule_type"] = body.schedule_type.strip() if body.schedule_type else None

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    for key, value in updates.items():
        setattr(schedule, key, value)
    db.commit()
    db.refresh(schedule)
    return _schedule_to_response(schedule)


@router.delete("/events/{event_id}")
def delete_schedule_event(
    event_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    schedule = get_schedule_by_id(db, event_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if schedule not in user.schedules:
        raise HTTPException(status_code=403, detail="Event does not belong to current user")

    if len(schedule.users) <= 1:
        db.delete(schedule)
    else:
        user.schedules.remove(schedule)
    db.commit()
    return {"detail": "Event deleted"}
