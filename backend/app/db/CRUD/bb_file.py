from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.entities import BBFile


def create_bb_file(db: Session, **file_data: Any) -> BBFile:
    bb_file = BBFile(**file_data)
    db.add(bb_file)
    db.commit()
    db.refresh(bb_file)
    return bb_file


def get_bb_files_by_user_id(db: Session, user_id: int) -> list[BBFile]:
    return db.query(BBFile).filter(BBFile.user_id == user_id).order_by(BBFile.id.desc()).all()


def list_bb_files_by_user_id(db: Session, user_id: int) -> list[BBFile]:
    return get_bb_files_by_user_id(db, user_id)


def get_bb_files_by_course(db: Session, user_id: int, course: str) -> list[BBFile]:
    return (
        db.query(BBFile)
        .filter(BBFile.user_id == user_id, BBFile.course == course)
        .order_by(BBFile.id.desc())
        .all()
    )


def create_bb_files_from_json(db: Session, user_id: int, files_json: str) -> int:
    """Batch import BB files from a JSON string produced by crawler/download tasks."""
    try:
        items = json.loads(files_json)
    except json.JSONDecodeError:
        return 0

    if not isinstance(items, list) or not items:
        return 0

    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue

        bb_file = BBFile(
            user_id=user_id,
            course=item.get("course", ""),
            content=item.get("content", ""),
            file_url=item.get("file_url", ""),
            file_name=item.get("file_name", ""),
        )
        db.add(bb_file)
        count += 1

    if count == 0:
        return 0

    db.commit()
    return count


def delete_bb_files_by_user_id(db: Session, user_id: int) -> int:
    query = db.query(BBFile).filter(BBFile.user_id == user_id)
    deleted = query.count()
    query.delete()
    db.commit()
    return deleted


def delete_bb_files_by_course(db: Session, user_id: int, course: str) -> int:
    query = db.query(BBFile).filter(BBFile.user_id == user_id, BBFile.course == course)
    deleted = query.count()
    query.delete()
    db.commit()
    return deleted
