from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user_id
from app.schemas.mail import (
    MailAccountResponse,
    MailListResponse,
    MailLoginRequest,
    MailLogoutResponse,
    MailMessageItem,
    MailSendRequest,
    MailSendResponse,
    MailSyncRequest,
    MailSyncResponse,
)
from app.services.mail_service import (
    get_mail_account_service,
    get_mail_message_service,
    list_mail_messages_service,
    login_mail_account_service,
    logout_mail_account_service,
    send_mail_service,
    sync_mail_service,
)

router = APIRouter(prefix="/mail", tags=["mail"])


@router.post("/account/login", response_model=MailAccountResponse)
async def login_mail_account_endpoint(
    request: MailLoginRequest,
    user_id: int = Depends(get_current_user_id),
) -> MailAccountResponse:
    data = login_mail_account_service(
        user_id=user_id,
        provider=request.provider,
        email_address=request.email_address,
        password=request.password,
    )
    return MailAccountResponse(**data)


@router.post("/account/logout", response_model=MailLogoutResponse)
async def logout_mail_account_endpoint(
    user_id: int = Depends(get_current_user_id),
) -> MailLogoutResponse:
    data = logout_mail_account_service(user_id=user_id)
    return MailLogoutResponse(**data)


@router.get("/account", response_model=MailAccountResponse)
async def get_mail_account_endpoint(
    user_id: int = Depends(get_current_user_id),
) -> MailAccountResponse:
    data = get_mail_account_service(user_id=user_id)
    return MailAccountResponse(**data)


@router.post("/send", response_model=MailSendResponse)
async def send_mail_endpoint(
    request: MailSendRequest,
    user_id: int = Depends(get_current_user_id),
) -> MailSendResponse:
    data = send_mail_service(
        user_id=user_id,
        to_addresses=request.to_addresses,
        cc_addresses=request.cc_addresses,
        bcc_addresses=request.bcc_addresses,
        subject=request.subject,
        body=request.body,
        html_body=request.html_body,
    )
    return MailSendResponse(**data)


@router.post("/sync", response_model=MailSyncResponse)
async def sync_mail_endpoint(
    request: MailSyncRequest,
    user_id: int = Depends(get_current_user_id),
) -> MailSyncResponse:
    data = sync_mail_service(
        user_id=user_id,
        folder=request.folder,
        limit=request.limit,
        unread_only=request.unread_only,
    )
    return MailSyncResponse(**data)


@router.get("/messages", response_model=MailListResponse)
async def list_mail_messages_endpoint(
    mailbox: str | None = Query(default=None),
    folder: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user_id: int = Depends(get_current_user_id),
) -> MailListResponse:
    rows = list_mail_messages_service(user_id=user_id, mailbox=mailbox, folder=folder, limit=limit)
    return MailListResponse(messages=[MailMessageItem(**row) for row in rows])


@router.get("/messages/{mail_id}", response_model=MailMessageItem)
async def get_mail_message_endpoint(
    mail_id: int,
    user_id: int = Depends(get_current_user_id),
) -> MailMessageItem:
    row = get_mail_message_service(user_id=user_id, mail_id=mail_id)
    return MailMessageItem(**row)
