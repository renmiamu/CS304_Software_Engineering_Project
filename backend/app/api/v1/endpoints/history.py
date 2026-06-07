from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.db.models.message import KnowledgeBase  
from app.schemas.message import (
    DeleteSessionResponse,
    FilestResponse,
    RenameSessionRequest,
    RenameSessionResponse,
    SessionListResponse,
    SessionResponse,
)
from typing import List
from sqlalchemy import text ,select 
from urllib.parse import unquote
from app.services.document_operations_service import delete_document
from app.core.security import get_current_user_id
from app.services.session_service import SessionService, get_session_service


router = APIRouter(prefix="/history", tags=["history"])

@router.get("/get_files", response_model=List[FilestResponse])
async def get_documents_by_user_id(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    获取用户上传的文档列表，需要用户认证
    """
    try:
        user_id = str(user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 构建查询语句
        stmt = select(KnowledgeBase).where(KnowledgeBase.user_id == user_id)
        
        # 执行查询
        result = db.execute(stmt).scalars().all()

        # 如果没有找到文档，返回空列表
        if not result:
            return []

        # 将查询结果转换为 Pydantic 模型
        documents = [
            FilestResponse(
                user_id=row.user_id,
                file_name=row.file_name,
                created_at=row.created_at.isoformat(),
                updated_at=row.updated_at.isoformat()
            )
            for row in result
        ]

        return documents

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve documents: {str(e)}"
        )
    
@router.delete("/delete_file/{file_name}")
async def delete_document_endpoint(
    file_name: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    try:
        user_id = str(user_id)
        # URL 解码文件名
        decoded_file_name = unquote(file_name)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 调用 service 层的删除方法
        result = delete_document(user_id, decoded_file_name, db)
        
        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["message"])
            
        return {"message": result["message"]}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/get_messages")
async def get_messages_by_session_id(
    session_id: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    try:
        user_id = str(user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 查询 messages 表中对应 session_id 的消息
        messages_data = db.execute(
            text("SELECT message_id, session_id, user_question, model_answer, documents, recommended_questions, think, created_at FROM messages WHERE session_id = :session_id"),
            {"session_id": session_id}
        ).fetchall()

        # 构造返回数据
        messages = []
        for message in messages_data:
            messages.append(
                {
                    "message_id": message.message_id,
                    "session_id": message.session_id,
                    "user_question": message.user_question,
                    "model_answer":message.model_answer,
                    "documents" : message.documents,
                    "recommended_questions" : message.recommended_questions,
                    "think" : message.think,
                    "created_at": message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                }
            )

        return messages

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve messages: {str(e)}"
        )
    
@router.get("/get_sessions", response_model=SessionListResponse)
async def get_sessions_by_user_id(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    try:
        user_id = str(user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")


        # 查询 sessions 表中对应 user_id 的所有会话
        sessions_data = db.execute(
            text("SELECT * FROM sessions WHERE user_id = :user_id"),
            {"user_id": user_id}
        ).fetchall()

        # 构造返回数据
        sessions = []
        for session in sessions_data:
            sessions.append(
                SessionResponse(
                    session_id=session.session_id,
                    session_name=session.session_name,
                    user_id=session.user_id,
                    created_at=session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    updated_at=session.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                )
            )

        return {"user_id": user_id, "sessions": sessions}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.patch("/sessions/{session_id}/rename", response_model=RenameSessionResponse)
async def rename_session_endpoint(
    session_id: str,
    request: RenameSessionRequest,
    user_id: int = Depends(get_current_user_id),
    session_service: SessionService = Depends(get_session_service),
):
    try:
        user_id = str(user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        return session_service.rename_session(user_id, session_id, request.session_name)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
async def delete_session_endpoint(
    session_id: str,
    user_id: int = Depends(get_current_user_id),
    session_service: SessionService = Depends(get_session_service),
):
    try:
        user_id = str(user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        return session_service.delete_session(user_id, session_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
