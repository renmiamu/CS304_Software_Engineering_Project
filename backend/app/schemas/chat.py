from pydantic import BaseModel
from typing import Any, Dict

class SessionResponse(BaseModel):
    session_id: str
    status: str
    message: str

class ChatRequest(BaseModel):
    message: str


class ApprovalDecisionRequest(BaseModel):
    action_id: str
    approved: bool


class ApprovalDecisionResponse(BaseModel):
    success: bool
    action_id: str
    state: str
    message: str
    target: str


class FileToolRequest(BaseModel):
    payload: Dict[str, Any]


class FileWorkspaceRequest(BaseModel):
    path: str
