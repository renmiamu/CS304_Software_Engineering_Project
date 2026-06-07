import uuid

from fastapi import Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.db.models.document_upload import DocumentUpload
from app.db.models.message import Message
from app.db.models.session import Session as ChatSession


class SessionService:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, user_id: int | str):
        try:
            session_id = str(uuid.uuid4()).replace("-", "")[:16]
            session_name = f"session-{session_id}"

            session_record = ChatSession(
                session_id=session_id,
                session_name=session_name,
                user_id=str(user_id),
            )
            self.db.add(session_record)
            self.db.commit()

            return {
                "session_id": session_id,
                "status": "success",
                "message": "Session created successfully",
            }
        except SQLAlchemyError as e:
            self.db.rollback()
            raise e

    def rename_session(self, user_id: int | str, session_id: str, session_name: str):
        session_name = session_name.strip()
        if not session_name:
            raise HTTPException(status_code=400, detail="Session name cannot be empty")
        if len(session_name) > 255:
            raise HTTPException(status_code=400, detail="Session name cannot exceed 255 characters")

        try:
            session_record = self.db.get(ChatSession, session_id)
            if session_record is None or session_record.user_id != str(user_id):
                raise HTTPException(status_code=404, detail="Session not found")

            session_record.session_name = session_name
            session_record.updated_at = func.now()
            self.db.commit()
            self.db.refresh(session_record)

            return {
                "session_id": session_record.session_id,
                "session_name": session_record.session_name,
                "status": "success",
                "message": "Session renamed successfully",
            }
        except HTTPException:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise e

    def delete_session(self, user_id: int | str, session_id: str):
        try:
            session_record = self.db.get(ChatSession, session_id)
            if session_record is None or session_record.user_id != str(user_id):
                raise HTTPException(status_code=404, detail="Session not found")

            deleted_messages = (
                self.db.query(Message)
                .filter(Message.session_id == session_id)
                .delete(synchronize_session=False)
            )
            deleted_documents = (
                self.db.query(DocumentUpload)
                .filter(DocumentUpload.session_id == session_id)
                .delete(synchronize_session=False)
            )
            self.db.delete(session_record)
            self.db.commit()

            return {
                "session_id": session_id,
                "deleted": True,
                "deleted_messages": deleted_messages,
                "deleted_documents": deleted_documents,
                "status": "success",
                "message": "Session deleted successfully",
            }
        except HTTPException:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise e


def get_session_service(db: Session = Depends(get_db)):
    return SessionService(db)
