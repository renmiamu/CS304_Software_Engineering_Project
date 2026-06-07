from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MailLoginRequest(BaseModel):
    provider: Literal["qq", "exmail"] = "qq"
    email_address: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class MailAccountResponse(BaseModel):
    logged_in: bool
    provider: str | None = None
    mailbox: str | None = None
    logged_in_at: datetime | None = None


class MailLogoutResponse(BaseModel):
    logged_out: bool
    mailbox: str | None = None


class MailSyncRequest(BaseModel):
    folder: str = "INBOX"
    limit: int = Field(default=20, ge=1, le=100)
    unread_only: bool = False


class MailSendRequest(BaseModel):
    to_addresses: list[str] = Field(..., min_length=1)
    cc_addresses: list[str] = Field(default_factory=list)
    bcc_addresses: list[str] = Field(default_factory=list)
    subject: str = Field(..., min_length=1, max_length=255)
    body: str | None = None
    html_body: str | None = None


class MailMessageItem(BaseModel):
    id: int
    mailbox: str
    folder: str
    imap_uid: str
    message_id: str | None = None
    subject: str | None = None
    from_address: str | None = None
    to_address: str | None = None
    cc_address: str | None = None
    received_at: datetime | None = None
    raw_date: str | None = None
    snippet: str | None = None
    text_body: str | None = None
    html_body: str | None = None
    is_seen: bool
    has_attachment: bool
    synced_at: datetime


class MailListResponse(BaseModel):
    messages: list[MailMessageItem]


class MailSyncResponse(BaseModel):
    mailbox: str
    folder: str
    requested_limit: int
    unread_only: bool
    fetched: int
    inserted: int
    updated: int


class MailSendResponse(BaseModel):
    mailbox: str
    to_addresses: list[str]
    cc_addresses: list[str]
    bcc_count: int
    subject: str
    message_id: str
    sent_at: datetime
