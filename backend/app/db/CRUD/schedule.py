from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models.entities import Schedule
from app.db.CRUD.user import get_user_by_id


def create_schedule(db: Session, **schedule_data: Any) -> Schedule:
    schedule = Schedule(**schedule_data)
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def get_schedule_by_id(db: Session, schedule_id: int) -> Schedule | None:
    return db.query(Schedule).filter(Schedule.schedule_id == schedule_id).first()


def list_schedules(db: Session, offset: int = 0, limit: int = 200) -> list[Schedule]:
    return db.query(Schedule).offset(offset).limit(limit).all()


def assign_schedule_to_user(db: Session, user_id: int, schedule_id: int) -> bool:
    user = get_user_by_id(db, user_id)
    schedule = get_schedule_by_id(db, schedule_id)
    if user is None or schedule is None:
        return False

    if schedule not in user.schedules:
        user.schedules.append(schedule)
        db.commit()
    return True


def remove_schedule_from_user(db: Session, user_id: int, schedule_id: int) -> bool:
    user = get_user_by_id(db, user_id)
    schedule = get_schedule_by_id(db, schedule_id)
    if user is None or schedule is None:
        return False

    if schedule in user.schedules:
        user.schedules.remove(schedule)
        db.commit()
    return True
