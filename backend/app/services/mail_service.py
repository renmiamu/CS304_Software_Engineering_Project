from __future__ import annotations

import imaplib
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email import policy
from email.header import decode_header, make_header
from email.parser import BytesParser
from email.utils import formatdate, getaddresses, make_msgid, parsedate_to_datetime
from threading import Lock

from bs4 import BeautifulSoup
from fastapi import HTTPException

from app.core import config
from app.core.database import get_db_sync
from app.db.CRUD import get_user_by_id, get_mail_message_by_id, list_mail_messages_by_user_id, upsert_mail_messages


@dataclass(frozen=True)
class MailProviderConfig:
    provider: str
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int


@dataclass
class MailAccountSession:
    provider: str
    email_address: str
    password: str
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    logged_in_at: datetime


_MAIL_SESSIONS: dict[int, MailAccountSession] = {}
_MAIL_SESSION_LOCK = Lock()


def _decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def _join_addresses(raw_value: str | None) -> str:
    if not raw_value:
        return ""
    parsed = getaddresses([raw_value])
    formatted: list[str] = []
    for name, address in parsed:
        clean_name = _decode_mime_header(name)
        if clean_name and address:
            formatted.append(f"{clean_name} <{address}>")
        elif address:
            formatted.append(address)
        elif clean_name:
            formatted.append(clean_name)
    return ", ".join(formatted)


def _extract_received_at(raw_date: str | None) -> datetime | None:
    if not raw_date:
        return None
    try:
        parsed = parsedate_to_datetime(raw_date)
    except Exception:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


def _html_to_text(value: str) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    return soup.get_text("\n", strip=True)


def _extract_bodies(message) -> tuple[str, str, bool]:
    text_chunks: list[str] = []
    html_chunks: list[str] = []
    has_attachment = False

    for part in message.walk():
        if part.is_multipart():
            continue

        filename = part.get_filename()
        disposition = (part.get_content_disposition() or "").lower()
        if filename or disposition == "attachment":
            has_attachment = True
            continue

        content_type = (part.get_content_type() or "").lower()
        try:
            payload = part.get_content()
        except Exception:
            payload_bytes = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            payload = payload_bytes.decode(charset, errors="replace")

        if not isinstance(payload, str):
            payload = str(payload)

        clean_payload = payload.strip()
        if not clean_payload:
            continue

        if content_type == "text/plain":
            text_chunks.append(clean_payload)
        elif content_type == "text/html":
            html_chunks.append(clean_payload)

    text_body = "\n\n".join(text_chunks).strip()
    html_body = "\n\n".join(html_chunks).strip()
    if not text_body and html_body:
        text_body = _html_to_text(html_body)

    return text_body, html_body, has_attachment


def _build_snippet(text_body: str, html_body: str, max_length: int = 200) -> str:
    candidate = text_body.strip() or _html_to_text(html_body)
    if len(candidate) <= max_length:
        return candidate
    return candidate[:max_length].rstrip() + "..."


def _normalize_folder(folder: str) -> str:
    normalized = folder.strip()
    return normalized or "INBOX"


def _get_provider_config(provider: str) -> MailProviderConfig:
    provider_key = provider.strip().lower()
    if provider_key == "qq":
        return MailProviderConfig(
            provider="qq",
            imap_host=config.QQ_MAIL_IMAP_HOST,
            imap_port=config.QQ_MAIL_IMAP_PORT,
            smtp_host=config.QQ_MAIL_SMTP_HOST,
            smtp_port=config.QQ_MAIL_SMTP_PORT,
        )
    if provider_key == "exmail":
        return MailProviderConfig(
            provider="exmail",
            imap_host=config.EXMAIL_IMAP_HOST,
            imap_port=config.EXMAIL_IMAP_PORT,
            smtp_host=config.EXMAIL_SMTP_HOST,
            smtp_port=config.EXMAIL_SMTP_PORT,
        )
    raise HTTPException(status_code=400, detail="Unsupported mail provider")


def _get_mail_session(user_id: int) -> MailAccountSession:
    with _MAIL_SESSION_LOCK:
        session = _MAIL_SESSIONS.get(user_id)
    if session is None:
        raise HTTPException(status_code=401, detail="Mail account is not logged in")
    return session


def _require_current_mailbox(user_id: int, mailbox: str | None = None) -> MailAccountSession:
    session = _get_mail_session(user_id)
    if mailbox and mailbox.strip() != session.email_address:
        raise HTTPException(status_code=403, detail="Only current logged-in mailbox can be used")
    return session


def _ensure_user_exists(user_id: int) -> None:
    db = get_db_sync()
    try:
        if get_user_by_id(db, user_id) is None:
            raise HTTPException(status_code=404, detail="User not found")
    finally:
        db.close()


def _check_imap_login(mailbox: str, password: str, provider_config: MailProviderConfig) -> None:
    client = None
    try:
        client = imaplib.IMAP4_SSL(
            provider_config.imap_host,
            provider_config.imap_port,
            timeout=config.QQ_MAIL_FETCH_TIMEOUT_SECONDS,
        )
        client.login(mailbox, password)
    except imaplib.IMAP4.error as exc:
        raise HTTPException(status_code=401, detail=f"IMAP login failed: {exc}") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="IMAP login timed out") from exc
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to connect IMAP server: {exc}") from exc
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass


def _check_smtp_login(mailbox: str, password: str, provider_config: MailProviderConfig) -> None:
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            provider_config.smtp_host,
            provider_config.smtp_port,
            timeout=config.QQ_MAIL_SEND_TIMEOUT_SECONDS,
            context=context,
        ) as client:
            client.login(mailbox, password)
    except smtplib.SMTPAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=f"SMTP login failed: {_smtp_error_text(exc)}") from exc
    except smtplib.SMTPException as exc:
        raise HTTPException(status_code=502, detail=f"SMTP login request failed: {_smtp_error_text(exc)}") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="SMTP login timed out") from exc
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to connect SMTP server: {exc}") from exc


def login_mail_account_service(
    user_id: int,
    provider: str,
    email_address: str,
    password: str,
) -> dict[str, object]:
    _ensure_user_exists(user_id)

    mailbox = email_address.strip()
    mail_password = password.strip()
    if "@" not in mailbox:
        raise HTTPException(status_code=400, detail="Mail account should be a valid email address")
    if not mail_password:
        raise HTTPException(status_code=400, detail="Mail password is required")

    provider_config = _get_provider_config(provider)
    _check_imap_login(mailbox, mail_password, provider_config)
    _check_smtp_login(mailbox, mail_password, provider_config)

    session = MailAccountSession(
        provider=provider_config.provider,
        email_address=mailbox,
        password=mail_password,
        imap_host=provider_config.imap_host,
        imap_port=provider_config.imap_port,
        smtp_host=provider_config.smtp_host,
        smtp_port=provider_config.smtp_port,
        logged_in_at=datetime.now(),
    )
    with _MAIL_SESSION_LOCK:
        _MAIL_SESSIONS[user_id] = session

    return _mail_session_to_dict(session)


def logout_mail_account_service(user_id: int) -> dict[str, object]:
    _ensure_user_exists(user_id)
    with _MAIL_SESSION_LOCK:
        session = _MAIL_SESSIONS.pop(user_id, None)
    return {
        "logged_out": session is not None,
        "mailbox": session.email_address if session is not None else None,
    }


def get_mail_account_service(user_id: int) -> dict[str, object]:
    _ensure_user_exists(user_id)
    with _MAIL_SESSION_LOCK:
        session = _MAIL_SESSIONS.get(user_id)
    if session is None:
        return {"logged_in": False, "provider": None, "mailbox": None, "logged_in_at": None}
    return _mail_session_to_dict(session)


def _mail_session_to_dict(session: MailAccountSession) -> dict[str, object]:
    return {
        "logged_in": True,
        "provider": session.provider,
        "mailbox": session.email_address,
        "logged_in_at": session.logged_in_at,
    }


def _normalize_recipients(
    values: list[str] | None,
    field_name: str,
    required: bool = False,
) -> list[str]:
    raw_values = [value.strip() for value in values or [] if value and value.strip()]
    parsed_addresses = [address.strip() for _, address in getaddresses(raw_values) if address.strip()]

    if required and not parsed_addresses:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")

    invalid_addresses = [address for address in parsed_addresses if "@" not in address]
    if invalid_addresses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid email address in {field_name}: {invalid_addresses[0]}",
        )

    return list(dict.fromkeys(parsed_addresses))


def _smtp_error_text(exc: object) -> str:
    smtp_error = getattr(exc, "smtp_error", exc)
    if isinstance(smtp_error, bytes):
        return smtp_error.decode("utf-8", errors="replace")
    return str(smtp_error)


def send_mail_service(
    user_id: int,
    to_addresses: list[str],
    subject: str,
    body: str | None = None,
    cc_addresses: list[str] | None = None,
    bcc_addresses: list[str] | None = None,
    html_body: str | None = None,
) -> dict[str, object]:
    _ensure_user_exists(user_id)

    mail_session = _get_mail_session(user_id)
    mailbox = mail_session.email_address
    password = mail_session.password

    clean_subject = subject.strip()
    if not clean_subject:
        raise HTTPException(status_code=400, detail="Mail subject is required")

    plain_body = (body or "").strip()
    html_content = (html_body or "").strip()
    if not plain_body and html_content:
        plain_body = _html_to_text(html_content)
    if not plain_body and not html_content:
        raise HTTPException(status_code=400, detail="Mail body is required")

    to_list = _normalize_recipients(to_addresses, "to_addresses", required=True)
    cc_list = _normalize_recipients(cc_addresses, "cc_addresses")
    bcc_list = _normalize_recipients(bcc_addresses, "bcc_addresses")
    all_recipients = to_list + cc_list + bcc_list

    domain = mailbox.rsplit("@", 1)[-1]
    message_id = make_msgid(domain=domain)

    message = EmailMessage()
    message["From"] = mailbox
    message["To"] = ", ".join(to_list)
    if cc_list:
        message["Cc"] = ", ".join(cc_list)
    message["Subject"] = clean_subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = message_id

    if html_content:
        message.set_content(plain_body or " ")
        message.add_alternative(html_content, subtype="html")
    else:
        message.set_content(plain_body)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            mail_session.smtp_host,
            mail_session.smtp_port,
            timeout=config.QQ_MAIL_SEND_TIMEOUT_SECONDS,
            context=context,
        ) as client:
            client.login(mailbox, password)
            client.send_message(message, from_addr=mailbox, to_addrs=all_recipients)
    except smtplib.SMTPAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=f"SMTP login failed: {_smtp_error_text(exc)}") from exc
    except smtplib.SMTPRecipientsRefused as exc:
        raise HTTPException(status_code=400, detail=f"SMTP recipients refused: {exc.recipients}") from exc
    except smtplib.SMTPException as exc:
        raise HTTPException(status_code=502, detail=f"Failed to send mail: {_smtp_error_text(exc)}") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="SMTP request timed out") from exc
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to connect SMTP server: {exc}") from exc

    return {
        "mailbox": mailbox,
        "to_addresses": to_list,
        "cc_addresses": cc_list,
        "bcc_count": len(bcc_list),
        "subject": clean_subject,
        "message_id": message_id,
        "sent_at": datetime.now(),
    }


def sync_mail_service(
    user_id: int,
    folder: str = "INBOX",
    limit: int = 20,
    unread_only: bool = False,
) -> dict[str, object]:
    _ensure_user_exists(user_id)

    mail_session = _get_mail_session(user_id)
    mailbox = mail_session.email_address
    password = mail_session.password
    normalized_folder = _normalize_folder(folder)

    client = None

    try:
        client = imaplib.IMAP4_SSL(
            mail_session.imap_host,
            mail_session.imap_port,
            timeout=config.QQ_MAIL_FETCH_TIMEOUT_SECONDS,
        )
        client.login(mailbox, password)
        status, _ = client.select(f'"{normalized_folder}"', readonly=True)
        if status != "OK":
            raise HTTPException(status_code=400, detail=f"Failed to open folder: {normalized_folder}")

        search_criteria = "UNSEEN" if unread_only else "ALL"
        status, data = client.uid("SEARCH", None, search_criteria)
        if status != "OK":
            raise HTTPException(status_code=502, detail="Failed to search mailbox")

        all_uids = data[0].split() if data and data[0] else []
        target_uids = [uid.decode("utf-8") for uid in all_uids[-limit:]]

        parsed_messages: list[dict[str, object]] = []
        for uid in reversed(target_uids):
            status, fetch_data = client.uid("FETCH", uid, "(RFC822 FLAGS)")
            if status != "OK" or not fetch_data:
                continue

            message_bytes = b""
            flags_text = ""
            for item in fetch_data:
                if not isinstance(item, tuple):
                    continue
                meta, body = item
                if body:
                    message_bytes = body
                if isinstance(meta, bytes):
                    flags_text = meta.decode("utf-8", errors="ignore")

            if not message_bytes:
                continue

            message = BytesParser(policy=policy.default).parsebytes(message_bytes)
            text_body, html_body, has_attachment = _extract_bodies(message)
            raw_date = message.get("Date")

            parsed_messages.append(
                {
                    "imap_uid": uid,
                    "message_id": (message.get("Message-ID") or "").strip() or None,
                    "subject": _decode_mime_header(message.get("Subject")) or None,
                    "from_address": _join_addresses(message.get("From")) or None,
                    "to_address": _join_addresses(message.get("To")) or None,
                    "cc_address": _join_addresses(message.get("Cc")) or None,
                    "received_at": _extract_received_at(raw_date),
                    "raw_date": raw_date.strip() if raw_date else None,
                    "snippet": _build_snippet(text_body, html_body) or None,
                    "text_body": text_body or None,
                    "html_body": html_body or None,
                    "is_seen": "\\Seen" in flags_text,
                    "has_attachment": has_attachment,
                }
            )

        db = get_db_sync()
        try:
            upsert_result = upsert_mail_messages(
                db,
                user_id=user_id,
                mailbox=mailbox,
                folder=normalized_folder,
                items=parsed_messages,
            )
        finally:
            db.close()

        return {
            "mailbox": mailbox,
            "folder": normalized_folder,
            "requested_limit": limit,
            "unread_only": unread_only,
            "fetched": len(parsed_messages),
            "inserted": upsert_result["inserted"],
            "updated": upsert_result["updated"],
        }
    except imaplib.IMAP4.error as exc:
        raise HTTPException(status_code=401, detail=f"IMAP request failed: {exc}") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="IMAP request timed out") from exc
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to connect IMAP server: {exc}") from exc
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass


def list_mail_messages_service(
    user_id: int,
    mailbox: str | None = None,
    folder: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    mail_session = _require_current_mailbox(user_id, mailbox)
    db = get_db_sync()
    try:
        rows = list_mail_messages_by_user_id(
            db,
            user_id=user_id,
            mailbox=mail_session.email_address,
            folder=_normalize_folder(folder) if folder else None,
            limit=limit,
        )
        return [_mail_row_to_dict(row) for row in rows]
    finally:
        db.close()


def get_mail_message_service(user_id: int, mail_id: int) -> dict[str, object]:
    mail_session = _get_mail_session(user_id)
    db = get_db_sync()
    try:
        row = get_mail_message_by_id(db, user_id=user_id, mail_id=mail_id)
        if row is None or row.mailbox != mail_session.email_address:
            raise HTTPException(status_code=404, detail="Mail message not found")
        return _mail_row_to_dict(row)
    finally:
        db.close()


def _mail_row_to_dict(row) -> dict[str, object]:
    return {
        "id": row.id,
        "mailbox": row.mailbox,
        "folder": row.folder,
        "imap_uid": row.imap_uid,
        "message_id": row.message_id,
        "subject": row.subject,
        "from_address": row.from_address,
        "to_address": row.to_address,
        "cc_address": row.cc_address,
        "received_at": row.received_at,
        "raw_date": row.raw_date,
        "snippet": row.snippet,
        "text_body": row.text_body,
        "html_body": row.html_body,
        "is_seen": bool(row.is_seen),
        "has_attachment": bool(row.has_attachment),
        "synced_at": row.synced_at,
    }
