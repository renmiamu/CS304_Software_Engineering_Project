import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

# Allow running this file directly: python app/main.py
if __package__ is None or __package__ == "":
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.bb import router as bb_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.history import router as history_router
from app.api.v1.endpoints.mail import router as mail_router
from app.api.v1.endpoints.schedule import router as schedule_router
from app.api.v1.endpoints.sync import router as sync_router
from app.api.v1.endpoints.tis import router as tis_router
from app.api.v1.endpoints.user import router as user_router
from app.core.database import init_db

app = FastAPI(title="SUSTech Assistant Backend", version="0.1.0")


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )

    upload_files_path = openapi_schema.get("paths", {}).get("/api/v1/chat/upload_files", {})
    upload_post = upload_files_path.get("post", {})
    multipart_schema = (
        upload_post
        .get("requestBody", {})
        .get("content", {})
        .get("multipart/form-data", {})
        .get("schema", {})
    )

    schema_ref = multipart_schema.get("$ref", "")
    if schema_ref.startswith("#/components/schemas/"):
        schema_name = schema_ref.rsplit("/", 1)[-1]
        body_schema = openapi_schema.get("components", {}).get("schemas", {}).get(schema_name, {})
        files_schema = body_schema.get("properties", {}).get("files", {})
        file_items = files_schema.get("items", {})
        if isinstance(file_items, dict):
            file_items.pop("contentMediaType", None)
            file_items["type"] = "string"
            file_items["format"] = "binary"

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.on_event("startup")
def startup_initialize_database() -> None:
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Backend is running"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api/v1")
app.include_router(bb_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(history_router, prefix="/api/v1")
app.include_router(mail_router, prefix="/api/v1")
app.include_router(schedule_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")
app.include_router(tis_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "9000"))
    uvicorn.run("app.main:app", host=host, port=port)
