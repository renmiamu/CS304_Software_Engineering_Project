from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models.entities import User


def create_user(db: Session, **user_data: Any) -> User:
    user = User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.user_id == user_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def list_users(db: Session, offset: int = 0, limit: int = 100) -> list[User]:
    return db.query(User).offset(offset).limit(limit).all()


def update_user(db: Session, user_id: int, **updates: Any) -> User | None:
    user = get_user_by_id(db, user_id)
    if user is None:
        return None

    allowed_fields = {
        "name",
        "pinyin_name",
        "photo",
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
    }
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> bool:
    user = get_user_by_id(db, user_id)
    if user is None:
        return False
    db.delete(user)
    db.commit()
    return True
