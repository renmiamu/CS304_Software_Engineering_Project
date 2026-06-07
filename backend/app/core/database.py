from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from . import config

DATABASE_URL = config.DATABASE_URL

_engine_kwargs = {}
if DATABASE_URL.startswith("postgresql"):
    # Ensure PostgreSQL resolves unqualified table names to public schema.
    _engine_kwargs["connect_args"] = {"options": "-c search_path=public"}

engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(engine, future=True)
Base = declarative_base()


def _ensure_deadline_completed_column(conn) -> None:
    inspector = inspect(conn)
    if "deadlines" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("deadlines")}
    if "is_completed" in columns:
        return

    conn.execute(text("ALTER TABLE deadlines ADD COLUMN is_completed INTEGER NOT NULL DEFAULT 0"))


def _ensure_messages_columns(conn) -> None:
    inspector = inspect(conn)
    if "messages" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("messages")}

    if "documents" not in columns:
        conn.execute(text("ALTER TABLE messages ADD COLUMN documents TEXT"))

    if "recommended_questions" not in columns:
        conn.execute(text("ALTER TABLE messages ADD COLUMN recommended_questions TEXT"))

    if "think" not in columns:
        conn.execute(text("ALTER TABLE messages ADD COLUMN think TEXT"))

    if "created_at" not in columns:
        conn.execute(text("ALTER TABLE messages ADD COLUMN created_at TIMESTAMP DEFAULT NOW()"))

def init_db():
    """
    初始化数据库，创建所有模型表。
    """
    # Import models first so SQLAlchemy can register table metadata.
    from app.db.models import document_upload, entities, mail, message, session  # noqa: F401

    if DATABASE_URL.startswith("postgresql"):
        with engine.begin() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
            conn.execute(text("SET search_path TO public"))

            print("Initializing database...")
            Base.metadata.create_all(bind=conn)
            _ensure_deadline_completed_column(conn)
            _ensure_messages_columns(conn)
        return

    print("Initializing database...")
    Base.metadata.create_all(engine, )
    with engine.begin() as conn:
        _ensure_deadline_completed_column(conn)
        _ensure_messages_columns(conn)

def get_db():
    """
    获取一个数据库会话（Session），用于FastAPI依赖注入。
    请求结束后自动关闭会话。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_sync():
    """
    获取一个同步数据库会话（Session），适用于非异步场景。
    需要手动关闭会话。
    """
    return SessionLocal()
