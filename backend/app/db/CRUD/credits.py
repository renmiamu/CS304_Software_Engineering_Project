from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.clients.tis.credit import query_credits
from app.db.models.entities import Credits


DEFAULT_COOKIES_FILE = "clients/resources/cookies.json"


def get_credits_by_user_id(db: Session, user_id: int) -> Credits | None:
    return db.query(Credits).filter(Credits.user_id == user_id).first()


def create_credits(
    db: Session,
    user_id: int,
    cookies_file: str = DEFAULT_COOKIES_FILE,
) -> Credits | None:
    """Create credits record from latest TIS credits result."""
    existing = get_credits_by_user_id(db, user_id)
    if existing is not None:
        return existing

    credits_data = query_credits(cookies_file=cookies_file)
    if not credits_data:
        return None

    credits = Credits(
        user_id=user_id,
        total_credit=credits_data.get("total_credit", 0.0),
        category_credit=credits_data.get("category_credit", {}),
    )
    db.add(credits)
    db.commit()
    db.refresh(credits)
    return credits


def update_credits(
    db: Session,
    user_id: int,
    cookies_file: str = DEFAULT_COOKIES_FILE,
) -> Credits | None:
    """Update credits record with latest TIS credits result."""
    credits_data = query_credits(cookies_file=cookies_file)
    if not credits_data:
        return None

    credits = get_credits_by_user_id(db, user_id)
    if credits is None:
        return create_credits(db, user_id=user_id, cookies_file=cookies_file)

    credits.total_credit = credits_data.get("total_credit", 0.0)
    credits.category_credit = credits_data.get("category_credit", {})
    db.commit()
    db.refresh(credits)
    return credits


def delete_credits(db: Session, user_id: int) -> bool:
    """Delete credits record for a user."""
    credits = get_credits_by_user_id(db, user_id)
    if credits is None:
        return False

    db.delete(credits)
    db.commit()
    return True


def upsert_credits(
    db: Session,
    user_id: int,
    total_credit: float | None = None,
    category_credit: dict[str, Any] | None = None,
) -> Credits:
    credits = get_credits_by_user_id(db, user_id)
    if credits is None:
        credits = Credits(user_id=user_id)
        db.add(credits)

    if total_credit is not None:
        credits.total_credit = total_credit
    if category_credit is not None:
        credits.category_credit = category_credit

    db.commit()
    db.refresh(credits)
    return credits
