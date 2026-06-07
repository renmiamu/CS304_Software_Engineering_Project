from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.core.database import get_db  # 根据实际模块名称导入
from fastapi import HTTPException

def insert_knowledgebase(user_id: str, file_name: str):
    """
    将知识库信息插入到 knowledgebases 表中。

    :param user_id: 用户 ID
    :param file_name: 文件名称
    """
    db = next(get_db())  # 获取数据库会话
    try:
        db.execute(
            text(
                """
                INSERT INTO knowledgebases (user_id, file_name)
                VALUES (:user_id, :file_name)
                """
            ),
            {
                "user_id": user_id,
                "file_name": file_name
            }
        )
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"Failed to insert into knowledgebases: {str(e)}")
    finally:
        db.close()

def verify_user_knowledgebase(user_id: str):
    """
    验证用户是否有自己的知识库。

    :param user_id: 用户 ID
    :return: 如果用户有知识库返回 True
    :raises HTTPException: 如果用户没有知识库，抛出 461 错误
    """
    db = next(get_db())  # 获取数据库会话
    try:
        query_result = db.execute(
            text("SELECT id FROM knowledgebases WHERE user_id = :user_id LIMIT 1"),
            {"user_id": user_id}
        ).fetchone()

        if not query_result:
            # 如果没有查到知识库数据，返回特定的错误码
            raise HTTPException(status_code=461,detail="You do not have your own knowledge base yet.")

        return True
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database operation failed: {str(e)}"
        )
    finally:
        db.close()

def get_user_history_questions(session_id: str):
    """
    获取用户的历史问题。

    :param session_id: 会话 ID
    :return: 用户的历史问题列表，如果没有数据则返回空列表
    """
    db = next(get_db())  # 获取数据库会话
    try:
        # 查询 messages 表中对应 session_id 的消息
        messages_data = db.execute(
            text("SELECT user_question FROM messages WHERE session_id = :session_id"),
            {"session_id": session_id}
        ).fetchall()

        # 构造返回数据
        history_questions = []
        for message in messages_data:
            history_questions.append(message.user_question)

        return history_questions
    except SQLAlchemyError as e:
        raise RuntimeError(f"Failed to fetch history questions: {str(e)}")
    finally:
        db.close()