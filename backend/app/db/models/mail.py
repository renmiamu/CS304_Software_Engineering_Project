from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.db.models.entities import Base, beijing_now


class MailMessage(Base):
    __tablename__ = "mail_messages"
    __table_args__ = (
        UniqueConstraint("user_id", "mailbox", "folder", "imap_uid", name="uq_mail_message_sync_scope"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    mailbox = Column(String(255), nullable=False)
    folder = Column(String(100), nullable=False, default="INBOX")
    imap_uid = Column(String(64), nullable=False)
    message_id = Column(String(255), nullable=True)
    subject = Column(String(500), nullable=True)
    from_address = Column(String(500), nullable=True)
    to_address = Column(Text, nullable=True)
    cc_address = Column(Text, nullable=True)
    received_at = Column(DateTime, nullable=True)
    raw_date = Column(String(255), nullable=True)
    snippet = Column(Text, nullable=True)
    text_body = Column(Text, nullable=True)
    html_body = Column(Text, nullable=True)
    is_seen = Column(Integer, nullable=False, default=0)
    has_attachment = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=beijing_now, nullable=False)
    updated_at = Column(DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    synced_at = Column(DateTime, default=beijing_now, nullable=False)
