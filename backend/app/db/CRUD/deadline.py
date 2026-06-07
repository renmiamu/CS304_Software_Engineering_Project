from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models.entities import Deadline, User


def _get_user_or_raise(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise ValueError("用户不存在")
    return user


def save_ddl_to_db(db: Session, user_id: int, schedule: list[dict[str, Any]]) -> int:
    """批量保存 DDL，跳过重复 title+end_time。返回新增条数。"""
    user = _get_user_or_raise(db, user_id)
    created = 0

    for item in schedule:
        title = item.get("title")
        end_time = item.get("end")
        if not title or not end_time:
            continue

        exists = (
            db.query(Deadline)
            .filter(
                Deadline.user_id == user_id,
                Deadline.title == title,
                Deadline.end_time == end_time,
            )
            .first()
        )
        if exists is not None:
            continue

        ddl_obj = Deadline(
            is_user_created=0 if item.get("userCreated") is False else 1,
            is_completed=1 if item.get("completed") else 0,
            calendar_name=item.get("calendarName"),
            end_time=end_time,
            title=title,
            event_type=item.get("eventType"),
            color=item.get("color"),
            user=user,
        )
        db.add(ddl_obj)
        created += 1

    db.commit()
    return created


def create_deadline(db: Session, **deadline_data: Any) -> Deadline:
    deadline = Deadline(**deadline_data)
    db.add(deadline)
    db.commit()
    db.refresh(deadline)
    return deadline


def get_deadline_by_id(db: Session, deadline_id: int) -> Deadline | None:
    return db.query(Deadline).filter(Deadline.id == deadline_id).first()


def get_ddl_by_user_id(db: Session, user_id: int) -> list[Deadline]:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        return []
    return user.deadlines


def list_deadlines_by_user_id(db: Session, user_id: int) -> list[Deadline]:
    return db.query(Deadline).filter(Deadline.user_id == user_id).order_by(Deadline.id.desc()).all()


def add_ddl_by_user_id(db: Session, user_id: int, ddl_data: dict[str, Any]) -> Deadline:
    _get_user_or_raise(db, user_id)

    title = ddl_data.get("title")
    end_time = ddl_data.get("end_time")
    if not title or not end_time:
        raise ValueError("title 和 end_time 不能为空")

    existing = (
        db.query(Deadline)
        .filter(
            Deadline.user_id == user_id,
            Deadline.title == title,
            Deadline.end_time == end_time,
        )
        .first()
    )
    if existing is not None:
        return existing

    ddl_obj = Deadline(
        is_user_created=1,
        is_completed=1 if ddl_data.get("completed") else 0,
        calendar_name=ddl_data.get("calendar_name"),
        end_time=end_time,
        title=title,
        event_type=ddl_data.get("event_type"),
        color=ddl_data.get("color"),
        user_id=user_id,
    )
    db.add(ddl_obj)
    db.commit()
    db.refresh(ddl_obj)
    return ddl_obj


def update_deadline(db: Session, deadline_id: int, **updates: Any) -> Deadline | None:
    deadline = get_deadline_by_id(db, deadline_id)
    if deadline is None:
        return None

    allowed_fields = {
        "is_user_created",
        "is_completed",
        "calendar_name",
        "end_time",
        "title",
        "event_type",
        "color",
    }
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(deadline, key, value)

    db.commit()
    db.refresh(deadline)
    return deadline


def delete_deadline(db: Session, deadline_id: int) -> bool:
    deadline = get_deadline_by_id(db, deadline_id)
    if deadline is None:
        return False
    db.delete(deadline)
    db.commit()
    return True


def delete_ddl_by_id(db: Session, user_id: int, ddl_id: int) -> bool:
    _get_user_or_raise(db, user_id)
    ddl_obj = (
        db.query(Deadline)
        .filter(
            Deadline.id == ddl_id,
            Deadline.user_id == user_id,
        )
        .first()
    )
    if ddl_obj is None:
        return False

    db.delete(ddl_obj)
    db.commit()
    return True
