from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.entities import BBGrade


def create_bb_grade(db: Session, **grade_data: Any) -> BBGrade:
    bb_grade = BBGrade(**grade_data)
    db.add(bb_grade)
    db.commit()
    db.refresh(bb_grade)
    return bb_grade


def replace_bb_grades(db: Session, user_id: int, items: Any) -> int:
    """Replace all grades of a user with provided grade items."""
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except Exception:
            items = []

    if not isinstance(items, list):
        items = []

    db.query(BBGrade).filter(BBGrade.user_id == user_id).delete()

    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue

        db.add(
            BBGrade(
                user_id=user_id,
                course_id=item.get("course_id", ""),
                course_name=item.get("course_name"),
                item_name=item.get("item_name", ""),
                full_grade=item.get("full_grade", ""),
            )
        )
        count += 1

    db.commit()
    return count


def list_bb_grades(db: Session, user_id: int, course_name: str | None = None) -> list[BBGrade]:
    query = db.query(BBGrade).filter(BBGrade.user_id == user_id).order_by(BBGrade.id.desc())
    if course_name:
        query = query.filter(BBGrade.course_name == course_name)
    return query.all()


def list_bb_grades_by_user_id(db: Session, user_id: int) -> list[BBGrade]:
    return list_bb_grades(db, user_id)


def delete_bb_grades(db: Session, user_id: int, course_name: str | None = None) -> int:
    query = db.query(BBGrade).filter(BBGrade.user_id == user_id)
    if course_name:
        query = query.filter(BBGrade.course_name == course_name)

    deleted = query.count()
    query.delete()
    db.commit()
    return deleted
