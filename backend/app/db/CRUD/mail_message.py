from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.mail import MailMessage


def get_mail_message_by_id(db: Session, user_id: int, mail_id: int) -> MailMessage | None:
    return (
        db.query(MailMessage)
        .filter(MailMessage.user_id == user_id, MailMessage.id == mail_id)
        .first()
    )


def list_mail_messages_by_user_id(
    db: Session,
    user_id: int,
    mailbox: str | None = None,
    folder: str | None = None,
    limit: int = 50,
) -> list[MailMessage]:
    query = db.query(MailMessage).filter(MailMessage.user_id == user_id)
    if mailbox:
        query = query.filter(MailMessage.mailbox == mailbox)
    if folder:
        query = query.filter(MailMessage.folder == folder)
    return (
        query.order_by(
            MailMessage.received_at.desc(),
            MailMessage.id.desc(),
        )
        .limit(limit)
        .all()
    )


def upsert_mail_messages(
    db: Session,
    user_id: int,
    mailbox: str,
    folder: str,
    items: Iterable[dict[str, Any]],
) -> dict[str, int]:
    payloads = list(items)
    if not payloads:
        return {"inserted": 0, "updated": 0}

    uids = [str(item["imap_uid"]) for item in payloads if item.get("imap_uid") is not None]
    existing_rows = (
        db.query(MailMessage)
        .filter(
            MailMessage.user_id == user_id,
            MailMessage.mailbox == mailbox,
            MailMessage.folder == folder,
            MailMessage.imap_uid.in_(uids),
        )
        .all()
    )
    existing_by_uid = {row.imap_uid: row for row in existing_rows}

    inserted = 0
    updated = 0
    synced_at = datetime.now()

    for item in payloads:
        imap_uid = str(item["imap_uid"])
        row = existing_by_uid.get(imap_uid)
        if row is None:
            row = MailMessage(
                user_id=user_id,
                mailbox=mailbox,
                folder=folder,
                imap_uid=imap_uid,
            )
            db.add(row)
            existing_by_uid[imap_uid] = row
            inserted += 1
        else:
            updated += 1

        row.message_id = item.get("message_id")
        row.subject = item.get("subject")
        row.from_address = item.get("from_address")
        row.to_address = item.get("to_address")
        row.cc_address = item.get("cc_address")
        row.received_at = item.get("received_at")
        row.raw_date = item.get("raw_date")
        row.snippet = item.get("snippet")
        row.text_body = item.get("text_body")
        row.html_body = item.get("html_body")
        row.is_seen = 1 if item.get("is_seen") else 0
        row.has_attachment = 1 if item.get("has_attachment") else 0
        row.synced_at = synced_at

    db.commit()
    return {"inserted": inserted, "updated": updated}
