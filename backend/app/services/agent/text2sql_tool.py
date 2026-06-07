from __future__ import annotations

from datetime import date, datetime, timedelta, time
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.models.entities import Credits, Deadline, Schedule, User, user_schedule_association
from app.schemas.text2sql import Text2SQLOperation, Text2SQLRequest, Text2SQLResponse


ALLOWED_ENTITY_TABLES: dict[str, list[str]] = {
    "users": [
        "user_id",
        "name",
        "pinyin_name",
        "gender",
        "birth_date",
        "college",
        "dormitory",
        "phone",
        "email",
        "gpa",
        "rank",
        "department",
        "interest",
        "created_at",
        "updated_at",
    ],
    "credits": ["id", "user_id", "total_credit", "category_credit", "updated_at"],
    "deadlines": [
        "id",
        "is_user_created",
        "is_completed",
        "calendar_name",
        "end_time",
        "title",
        "event_type",
        "color",
        "user_id",
    ],
    "schedules": [
        "schedule_id",
        "name",
        "location",
        "start_time",
        "end_time",
        "teacher",
        "weekday",
        "description",
        "schedule_type",
    ],
    "user_schedule_association": ["user_id", "schedule_id"],
}

ALLOWED_SCHEDULE_WRITE_FIELDS = {
    "name",
    "location",
    "start_time",
    "end_time",
    "teacher",
    "weekday",
    "description",
    "schedule_type",
}

_CONFIRMATION_TTL_SECONDS = 300
_PENDING_CONFIRMATIONS: dict[str, dict[str, Any]] = {}
_TABLE_ALIASES = {
    "user": "users",
    "users": "users",
    "用户": "users",
    "个人信息": "users",
    "credit": "credits",
    "credits": "credits",
    "学分": "credits",
    "deadline": "deadlines",
    "deadlines": "deadlines",
    "ddl": "deadlines",
    "todo": "deadlines",
    "calendar": "deadlines",
    "作业": "deadlines",
    "截止事项": "deadlines",
    "schedule": "schedules",
    "schedules": "schedules",
    "course": "schedules",
    "courses": "schedules",
    "class": "schedules",
    "classes": "schedules",
    "课表": "schedules",
    "课程": "schedules",
    "日程": "schedules",
    "课程表": "schedules",
    "user_schedule": "user_schedule_association",
    "user_schedule_association": "user_schedule_association",
}
_WEEKDAY_ALIASES = {
    "1": 1,
    "mon": 1,
    "monday": 1,
    "周一": 1,
    "星期一": 1,
    "2": 2,
    "tue": 2,
    "tues": 2,
    "tuesday": 2,
    "周二": 2,
    "星期二": 2,
    "3": 3,
    "wed": 3,
    "wednesday": 3,
    "周三": 3,
    "星期三": 3,
    "4": 4,
    "thu": 4,
    "thursday": 4,
    "周四": 4,
    "星期四": 4,
    "5": 5,
    "fri": 5,
    "friday": 5,
    "周五": 5,
    "星期五": 5,
    "6": 6,
    "sat": 6,
    "saturday": 6,
    "周六": 6,
    "星期六": 6,
    "7": 7,
    "sun": 7,
    "sunday": 7,
    "周日": 7,
    "周天": 7,
    "星期日": 7,
    "星期天": 7,
}
_BOOLEAN_TRUE_VALUES = {"1", "true", "yes", "y", "completed", "done", "已完成", "完成"}
_BOOLEAN_FALSE_VALUES = {"0", "false", "no", "n", "pending", "todo", "未完成", "待办"}


def _datetime_to_str(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    return value


def _normalize_time(value: Any) -> time | None:
    if value is None or value == "":
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time().replace(microsecond=0)
    if isinstance(value, str):
        normalized = value.strip().replace("：", ":")
        if not normalized:
            return None
        candidates = [normalized]
        if len(normalized) == 4 and normalized[1] == ":":
            candidates.append(f"0{normalized}:00")
        if len(normalized) == 5 and normalized[2] == ":":
            candidates.append(f"{normalized}:00")
        parsed_dt = _parse_datetime_like(normalized)
        if parsed_dt is not None and len(normalized) >= 10:
            return parsed_dt.time().replace(microsecond=0)
        for candidate in candidates:
            try:
                return time.fromisoformat(candidate)
            except ValueError:
                continue
        raise HTTPException(status_code=400, detail=f"Invalid time format: {value}")
    raise HTTPException(status_code=400, detail="start_time/end_time must be string HH:MM[:SS]")


def _schedule_to_dict(schedule: Schedule) -> dict[str, Any]:
    return {
        "schedule_id": schedule.schedule_id,
        "name": schedule.name,
        "location": schedule.location,
        "start_time": _datetime_to_str(schedule.start_time),
        "end_time": _datetime_to_str(schedule.end_time),
        "teacher": schedule.teacher,
        "weekday": schedule.weekday,
        "description": schedule.description,
        "schedule_type": schedule.schedule_type,
    }


def _normalize_table_name(value: Any) -> str:
    table_name = str(value or "users").strip().lower()
    return _TABLE_ALIASES.get(table_name, table_name)


def _parse_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in _BOOLEAN_TRUE_VALUES:
        return True
    if normalized in _BOOLEAN_FALSE_VALUES:
        return False
    return None


def _parse_weekday(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 7 else None
    if isinstance(value, float) and value.is_integer():
        normalized_int = int(value)
        return normalized_int if 1 <= normalized_int <= 7 else None
    normalized = str(value).strip().lower()
    return _WEEKDAY_ALIASES.get(normalized)


def _normalize_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value).strip()
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    return None


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_weekdays(value: Any) -> list[int]:
    if value is None or value == "":
        return []
    candidates = value if isinstance(value, list) else [value]

    weekdays: list[int] = []
    for candidate in candidates:
        parsed = _parse_weekday(candidate)
        if parsed is not None and parsed not in weekdays:
            weekdays.append(parsed)
    return weekdays


def _extract_weekdays_from_text(text: str) -> list[int]:
    normalized_text = text.lower()
    weekdays: list[int] = []
    for alias, value in _WEEKDAY_ALIASES.items():
        if len(alias) <= 1:
            continue
        if alias in normalized_text and value not in weekdays:
            weekdays.append(value)
    return weekdays


def _parse_date_value(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip().replace("/", "-")
    if not text:
        return None
    for candidate in (text, text[:10]):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _parse_datetime_like(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)

    text = str(value).strip().replace("/", "-").replace("T", " ")
    if not text:
        return None
    candidates = [text, text[:19], text[:16], text[:10]]
    for candidate in candidates:
        try:
            if len(candidate) == 10:
                return datetime.combine(date.fromisoformat(candidate), time.min)
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _resolve_relative_date_range(relative: Any) -> tuple[date | None, date | None]:
    if relative is None or relative == "":
        return None, None

    today = datetime.now().date()
    normalized = str(relative).strip().lower()
    if normalized in {"today", "今天"}:
        return today, today
    if normalized in {"tomorrow", "明天"}:
        target = today + timedelta(days=1)
        return target, target
    if normalized in {"day_after_tomorrow", "后天"}:
        target = today + timedelta(days=2)
        return target, target
    if normalized in {"this_week", "本周", "这周"}:
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if normalized in {"next_7_days", "未来7天", "接下来7天"}:
        return today, today + timedelta(days=7)
    if normalized in {"this_month", "本月"}:
        start = today.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return start, next_month - timedelta(days=1)
    return None, None


def _coalesce_date_bounds(filters: dict[str, Any]) -> tuple[date | None, date | None]:
    start = _parse_date_value(filters.get("date_from")) or _parse_date_value(filters.get("start_date"))
    end = _parse_date_value(filters.get("date_to")) or _parse_date_value(filters.get("end_date"))
    relative_start, relative_end = _resolve_relative_date_range(filters.get("relative_date") or filters.get("time_scope"))
    return start or relative_start, end or relative_end


def _resolve_schedule_relative_weekdays(relative: Any) -> list[int]:
    if relative is None or relative == "":
        return []

    today_weekday = datetime.now().isoweekday()
    normalized = str(relative).strip().lower()
    if normalized in {"today", "今天"}:
        return [today_weekday]
    if normalized in {"tomorrow", "明天"}:
        return [1 if today_weekday == 7 else today_weekday + 1]
    if normalized in {"day_after_tomorrow", "后天"}:
        target = today_weekday + 2
        return [((target - 1) % 7) + 1]
    return []


def _normalize_filters(filters: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(filters)
    normalized["table"] = _normalize_table_name(normalized.get("table", "users"))
    raw_query = str(normalized.get("raw_query") or "").strip()
    schedule_id = (
        _normalize_int(normalized.get("schedule_id"))
        or _normalize_int(normalized.get("id"))
        or _normalize_int(normalized.get("scheduleId"))
    )
    if schedule_id is not None:
        normalized["schedule_id"] = schedule_id

    weekdays = _parse_weekdays(normalized.get("weekdays"))
    single_weekday = _parse_weekday(normalized.get("weekday"))
    if single_weekday is not None and single_weekday not in weekdays:
        weekdays.append(single_weekday)
    for relative_weekday in _resolve_schedule_relative_weekdays(normalized.get("relative_date") or normalized.get("time_scope")):
        if relative_weekday not in weekdays:
            weekdays.append(relative_weekday)
    for inferred_weekday in _extract_weekdays_from_text(raw_query):
        if inferred_weekday not in weekdays:
            weekdays.append(inferred_weekday)
    if weekdays:
        normalized["weekdays"] = weekdays
        normalized["weekday"] = weekdays[0] if len(weekdays) == 1 else weekdays

    completed = _parse_bool(normalized.get("is_completed"))
    if completed is None and raw_query:
        if "未完成" in raw_query or "待完成" in raw_query:
            completed = False
        elif "已完成" in raw_query or "完成了" in raw_query:
            completed = True
    if completed is not None:
        normalized["is_completed"] = completed

    user_created = _parse_bool(normalized.get("is_user_created"))
    if user_created is not None:
        normalized["is_user_created"] = user_created

    start_date, end_date = _coalesce_date_bounds(normalized)
    if start_date is not None:
        normalized["date_from"] = start_date.isoformat()
    if end_date is not None:
        normalized["date_to"] = end_date.isoformat()

    return normalized


def _normalize_schedule_write_data(data: dict[str, Any], *, require_identifier: bool = False) -> dict[str, Any]:
    normalized = dict(data)

    schedule_id = (
        _normalize_int(normalized.get("schedule_id"))
        or _normalize_int(normalized.get("id"))
        or _normalize_int(normalized.get("scheduleId"))
    )
    if schedule_id is not None:
        normalized["schedule_id"] = schedule_id

    weekday = _parse_weekday(normalized.get("weekday"))
    if weekday is None and normalized.get("weekday") not in (None, ""):
        raise HTTPException(status_code=400, detail="weekday must be 1-7 or a valid weekday alias")
    if weekday is not None:
        normalized["weekday"] = weekday

    for field_name in ("name", "location", "teacher", "description", "schedule_type"):
        if field_name in normalized:
            normalized[field_name] = _normalize_text(normalized.get(field_name))

    if "start_time" in normalized:
        normalized["start_time"] = _normalize_time(normalized.get("start_time"))
    if "end_time" in normalized:
        normalized["end_time"] = _normalize_time(normalized.get("end_time"))

    start_time = normalized.get("start_time")
    end_time = normalized.get("end_time")
    if start_time is not None and end_time is not None and start_time >= end_time:
        raise HTTPException(status_code=400, detail="end_time must be later than start_time")

    if require_identifier and normalized.get("schedule_id") is None:
        raise HTTPException(status_code=400, detail="schedule_id is required for update/delete schedule")

    return normalized


def _canonicalize_schedule_request(request: Text2SQLRequest) -> Text2SQLRequest:
    require_identifier = request.operation in {
        Text2SQLOperation.UPDATE_SCHEDULE,
        Text2SQLOperation.DELETE_SCHEDULE,
    }
    merged = {**request.filters, **request.data}
    normalized_data = _normalize_schedule_write_data(merged, require_identifier=require_identifier)
    return request.model_copy(update={"data": normalized_data})


def _get_user_schedule(db: Session, user_id: int, schedule_id: int) -> Schedule | None:
    return (
        db.query(Schedule)
        .join(user_schedule_association, user_schedule_association.c.schedule_id == Schedule.schedule_id)
        .filter(
            and_(
                user_schedule_association.c.user_id == user_id,
                Schedule.schedule_id == schedule_id,
            )
        )
        .first()
    )


def _precheck_schedule_write_request(db: Session, user_id: int, request: Text2SQLRequest) -> None:
    if request.operation == Text2SQLOperation.CREATE_SCHEDULE:
        if not request.data.get("name"):
            raise HTTPException(status_code=400, detail="name is required")
        return

    schedule_id = _normalize_int(request.data.get("schedule_id"))
    if schedule_id is None:
        raise HTTPException(status_code=400, detail="schedule_id is required for update/delete schedule")

    schedule = _get_user_schedule(db=db, user_id=user_id, schedule_id=schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found for current user")

    if request.operation == Text2SQLOperation.UPDATE_SCHEDULE:
        updatable_fields = [field for field in ALLOWED_SCHEDULE_WRITE_FIELDS if field in request.data]
        if not updatable_fields:
            raise HTTPException(status_code=400, detail="No updatable fields provided")


def _build_empty_message(table_name: str, filters: dict[str, Any]) -> str:
    parts = [f"No matching rows found in {table_name}"]
    filter_bits: list[str] = []
    for key in ("query", "keyword", "title", "name", "teacher", "location", "weekday", "date_from", "date_to", "is_completed"):
        value = filters.get(key)
        if value not in (None, "", []):
            filter_bits.append(f"{key}={value}")
    if filter_bits:
        parts.append(f"with filters: {', '.join(filter_bits)}")
    return "; ".join(parts)


def _apply_schedule_filters(query, filters: dict[str, Any]):
    schedule_id = _normalize_int(filters.get("schedule_id"))
    if schedule_id is not None:
        query = query.filter(Schedule.schedule_id == schedule_id)

    text_query = str(filters.get("query") or filters.get("keyword") or "").strip()
    if text_query:
        like_pattern = f"%{text_query}%"
        query = query.filter(
            or_(
                Schedule.name.ilike(like_pattern),
                Schedule.location.ilike(like_pattern),
                Schedule.teacher.ilike(like_pattern),
                Schedule.description.ilike(like_pattern),
                Schedule.schedule_type.ilike(like_pattern),
            )
        )

    for field_name in ("name", "location", "teacher", "description", "schedule_type"):
        value = filters.get(field_name)
        if value in (None, ""):
            continue
        query = query.filter(getattr(Schedule, field_name).ilike(f"%{str(value).strip()}%"))

    weekdays = filters.get("weekdays") or []
    if weekdays:
        query = query.filter(Schedule.weekday.in_(weekdays))

    start_time = filters.get("start_time")
    if start_time not in (None, ""):
        query = query.filter(Schedule.start_time == _normalize_time(start_time))

    end_time = filters.get("end_time")
    if end_time not in (None, ""):
        query = query.filter(Schedule.end_time == _normalize_time(end_time))
    return query


def _apply_deadline_filters(query, filters: dict[str, Any]):
    text_query = str(filters.get("query") or filters.get("keyword") or "").strip()
    if text_query:
        like_pattern = f"%{text_query}%"
        query = query.filter(
            or_(
                Deadline.title.ilike(like_pattern),
                Deadline.calendar_name.ilike(like_pattern),
                Deadline.event_type.ilike(like_pattern),
            )
        )

    for field_name in ("title", "calendar_name", "event_type", "color"):
        value = filters.get(field_name)
        if value in (None, ""):
            continue
        query = query.filter(getattr(Deadline, field_name).ilike(f"%{str(value).strip()}%"))

    completed = filters.get("is_completed")
    if isinstance(completed, bool):
        query = query.filter(Deadline.is_completed == (1 if completed else 0))

    user_created = filters.get("is_user_created")
    if isinstance(user_created, bool):
        query = query.filter(Deadline.is_user_created == (1 if user_created else 0))
    return query


def _deadline_matches_date_filters(item: Deadline, filters: dict[str, Any]) -> bool:
    start_date = _parse_date_value(filters.get("date_from"))
    end_date = _parse_date_value(filters.get("date_to"))
    if start_date is None and end_date is None:
        return True

    deadline_dt = _parse_datetime_like(item.end_time)
    if deadline_dt is None:
        return False

    deadline_date = deadline_dt.date()
    if start_date is not None and deadline_date < start_date:
        return False
    if end_date is not None and deadline_date > end_date:
        return False
    return True


def _cleanup_confirmations() -> None:
    now = datetime.utcnow()
    expired = [k for k, v in _PENDING_CONFIRMATIONS.items() if v["expires_at"] <= now]
    for key in expired:
        _PENDING_CONFIRMATIONS.pop(key, None)


def _create_confirmation(user_id: int, request: Text2SQLRequest, sql_preview: str, params: dict[str, Any]) -> str:
    _cleanup_confirmations()
    confirmation_id = str(uuid4())
    _PENDING_CONFIRMATIONS[confirmation_id] = {
        "user_id": user_id,
        "operation": request.operation.value,
        "filters": request.filters,
        "data": request.data,
        "sql_preview": sql_preview,
        "params": params,
        "expires_at": datetime.utcnow() + timedelta(seconds=_CONFIRMATION_TTL_SECONDS),
    }
    return confirmation_id


def _validate_confirmation(user_id: int, request: Text2SQLRequest) -> None:
    _cleanup_confirmations()
    if not request.confirm:
        return
    if not request.confirmation_id:
        raise HTTPException(status_code=400, detail="confirmation_id is required when confirm=true")

    record = _PENDING_CONFIRMATIONS.get(request.confirmation_id)
    if not record:
        raise HTTPException(status_code=400, detail="confirmation_id is invalid or expired")
    if record["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Invalid confirmation scope")
    if record["operation"] != request.operation.value:
        raise HTTPException(status_code=400, detail="Operation does not match confirmation")
    if record["filters"] != request.filters or record["data"] != request.data:
        raise HTTPException(status_code=400, detail="Request content changed, please reconfirm")

    _PENDING_CONFIRMATIONS.pop(request.confirmation_id, None)


def _build_select_entities(user_id: int, request: Text2SQLRequest) -> Text2SQLResponse:
    normalized_filters = _normalize_filters(request.filters)
    table_name = normalized_filters["table"]
    if table_name not in ALLOWED_ENTITY_TABLES:
        raise HTTPException(status_code=400, detail=f"Unsupported table: {table_name}")

    allowed_fields = ALLOWED_ENTITY_TABLES[table_name]
    sql_preview = (
        f"SELECT {', '.join(allowed_fields)} FROM {table_name} WHERE user_id = :user_id LIMIT :limit"
        if table_name != "schedules"
        else (
            "SELECT s.schedule_id, s.name, s.location, s.start_time, s.end_time, "
            "s.teacher, s.weekday, s.description, s.schedule_type "
            "FROM schedules s "
            "JOIN user_schedule_association usa ON usa.schedule_id = s.schedule_id "
            "WHERE usa.user_id = :user_id LIMIT :limit"
        )
    )
    return Text2SQLResponse(
        success=True,
        message="SQL plan generated",
        table_name=table_name,
        allowed_fields=allowed_fields,
        sql_preview=sql_preview,
        params={"user_id": user_id, "limit": request.limit, "filters": normalized_filters},
    )


def _run_select_entities(db: Session, user_id: int, request: Text2SQLRequest, plan: Text2SQLResponse) -> Text2SQLResponse:
    table_name = plan.table_name
    limit = request.limit
    filters = _normalize_filters(request.filters)

    if table_name == "users":
        row = db.query(User).filter(User.user_id == user_id).first()
        rows = [] if row is None else [{field: _datetime_to_str(getattr(row, field)) for field in plan.allowed_fields}]
    elif table_name == "credits":
        row = db.query(Credits).filter(Credits.user_id == user_id).first()
        rows = [] if row is None else [{field: _datetime_to_str(getattr(row, field)) for field in plan.allowed_fields}]
    elif table_name == "deadlines":
        query = db.query(Deadline).filter(Deadline.user_id == user_id)
        query = _apply_deadline_filters(query, filters)
        records = query.order_by(Deadline.id.desc()).limit(max(limit * 3, limit)).all()
        filtered_records = [item for item in records if _deadline_matches_date_filters(item, filters)]
        rows = [
            {field: _datetime_to_str(getattr(item, field)) for field in plan.allowed_fields}
            for item in filtered_records[:limit]
        ]
    elif table_name == "schedules":
        query = (
            db.query(Schedule)
            .join(user_schedule_association, user_schedule_association.c.schedule_id == Schedule.schedule_id)
            .filter(user_schedule_association.c.user_id == user_id)
        )
        query = _apply_schedule_filters(query, filters)
        rows = [
            _schedule_to_dict(item)
            for item in query.order_by(Schedule.weekday.asc(), Schedule.start_time.asc(), Schedule.schedule_id.asc()).limit(limit).all()
        ]
    elif table_name == "user_schedule_association":
        records = (
            db.query(user_schedule_association)
            .filter(user_schedule_association.c.user_id == user_id)
            .limit(limit)
            .all()
        )
        rows = [{"user_id": item.user_id, "schedule_id": item.schedule_id} for item in records]
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported table: {table_name}")

    plan.rows = rows
    plan.params = {"user_id": user_id, "limit": limit, "filters": filters}
    plan.message = "Query executed" if rows else _build_empty_message(table_name, filters)
    return plan


def _build_schedule_write_plan(user_id: int, request: Text2SQLRequest) -> Text2SQLResponse:
    if request.operation == Text2SQLOperation.CREATE_SCHEDULE:
        normalized_data = _normalize_schedule_write_data(request.data)
    else:
        normalized_data = _normalize_schedule_write_data(request.data, require_identifier=True)

    if request.operation == Text2SQLOperation.CREATE_SCHEDULE:
        sql_preview = (
            "INSERT INTO schedules(name, location, start_time, end_time, teacher, weekday, description, schedule_type) "
            "VALUES(:name, :location, :start_time, :end_time, :teacher, :weekday, :description, :schedule_type); "
            "INSERT INTO user_schedule_association(user_id, schedule_id) VALUES(:user_id, :new_schedule_id)"
        )
        params = {"user_id": user_id, **normalized_data}
    elif request.operation == Text2SQLOperation.UPDATE_SCHEDULE:
        sql_preview = (
            "UPDATE schedules SET <allowed_fields> WHERE schedule_id = :schedule_id "
            "AND schedule_id IN (SELECT schedule_id FROM user_schedule_association WHERE user_id = :user_id)"
        )
        params = {"user_id": user_id, **normalized_data}
    elif request.operation == Text2SQLOperation.DELETE_SCHEDULE:
        sql_preview = (
            "DELETE FROM user_schedule_association WHERE user_id = :user_id AND schedule_id = :schedule_id; "
            "DELETE FROM schedules WHERE schedule_id = :schedule_id AND NOT EXISTS "
            "(SELECT 1 FROM user_schedule_association WHERE schedule_id = :schedule_id)"
        )
        params = {"user_id": user_id, **normalized_data}
    else:
        raise HTTPException(status_code=400, detail="Unsupported schedule write operation")

    return Text2SQLResponse(
        success=True,
        message="Write operation requires confirmation",
        table_name="schedules",
        allowed_fields=sorted(ALLOWED_SCHEDULE_WRITE_FIELDS),
        sql_preview=sql_preview,
        params=params,
        requires_confirmation=True,
    )


def _execute_create_schedule(db: Session, user_id: int, data: dict[str, Any]) -> Text2SQLResponse:
    normalized_data = _normalize_schedule_write_data(data)
    name = normalized_data.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    payload: dict[str, Any] = {}
    for field in ALLOWED_SCHEDULE_WRITE_FIELDS:
        if field in normalized_data:
            payload[field] = normalized_data[field]
    payload["name"] = name

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    schedule = Schedule(**payload)
    db.add(schedule)
    db.flush()
    user.schedules.append(schedule)
    db.commit()
    db.refresh(schedule)

    return Text2SQLResponse(
        success=True,
        message="Schedule created",
        table_name="schedules",
        rows=[_schedule_to_dict(schedule)],
        affected_rows=1,
    )


def _execute_update_schedule(db: Session, user_id: int, data: dict[str, Any]) -> Text2SQLResponse:
    normalized_data = _normalize_schedule_write_data(data, require_identifier=True)
    schedule_id = normalized_data.get("schedule_id")
    if schedule_id is None:
        raise HTTPException(status_code=400, detail="schedule_id is required")

    schedule = _get_user_schedule(db=db, user_id=user_id, schedule_id=schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found for current user")

    updated = False
    for field in ALLOWED_SCHEDULE_WRITE_FIELDS:
        if field not in normalized_data:
            continue
        value = normalized_data[field]
        setattr(schedule, field, value)
        updated = True

    if not updated:
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    db.commit()
    db.refresh(schedule)
    return Text2SQLResponse(
        success=True,
        message="Schedule updated",
        table_name="schedules",
        rows=[_schedule_to_dict(schedule)],
        affected_rows=1,
    )


def _execute_delete_schedule(db: Session, user_id: int, data: dict[str, Any]) -> Text2SQLResponse:
    normalized_data = _normalize_schedule_write_data(data, require_identifier=True)
    schedule_id = normalized_data.get("schedule_id")
    if schedule_id is None:
        raise HTTPException(status_code=400, detail="schedule_id is required")

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    schedule = _get_user_schedule(db=db, user_id=user_id, schedule_id=schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found for current user")

    if schedule in user.schedules:
        user.schedules.remove(schedule)

    should_delete_schedule_row = len(schedule.users) <= 1
    if should_delete_schedule_row:
        db.delete(schedule)

    db.commit()
    return Text2SQLResponse(
        success=True,
        message="Schedule deleted" if should_delete_schedule_row else "Schedule unlinked from current user",
        table_name="schedules",
        affected_rows=1,
    )


def execute_text2sql_tool(db: Session, user_id: int, request: Text2SQLRequest) -> Text2SQLResponse:
    if request.operation == Text2SQLOperation.SCHEMA:
        return Text2SQLResponse(
            success=True,
            message="Allowed tables and fields",
            rows=[{"table_name": k, "fields": v} for k, v in ALLOWED_ENTITY_TABLES.items()],
        )

    if request.operation == Text2SQLOperation.SELECT_ENTITIES:
        plan = _build_select_entities(user_id=user_id, request=request)
        return _run_select_entities(db=db, user_id=user_id, request=request, plan=plan)

    if request.operation in {
        Text2SQLOperation.CREATE_SCHEDULE,
        Text2SQLOperation.UPDATE_SCHEDULE,
        Text2SQLOperation.DELETE_SCHEDULE,
    }:
        normalized_request = _canonicalize_schedule_request(request)
        _precheck_schedule_write_request(db=db, user_id=user_id, request=normalized_request)
        plan = _build_schedule_write_plan(user_id=user_id, request=normalized_request)
        if not normalized_request.confirm:
            confirmation_id = _create_confirmation(
                user_id=user_id,
                request=normalized_request,
                sql_preview=plan.sql_preview or "",
                params=plan.params,
            )
            plan.confirmation_id = confirmation_id
            return plan

        _validate_confirmation(user_id=user_id, request=normalized_request)
        if normalized_request.operation == Text2SQLOperation.CREATE_SCHEDULE:
            return _execute_create_schedule(db=db, user_id=user_id, data=normalized_request.data)
        if normalized_request.operation == Text2SQLOperation.UPDATE_SCHEDULE:
            return _execute_update_schedule(db=db, user_id=user_id, data=normalized_request.data)
        return _execute_delete_schedule(db=db, user_id=user_id, data=normalized_request.data)

    raise HTTPException(status_code=400, detail="Unsupported operation")
