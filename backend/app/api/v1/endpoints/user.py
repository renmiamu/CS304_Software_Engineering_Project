from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_db_sync
from app.core.security import get_current_user_id
from app.db.CRUD.user import get_user_by_id, update_user
from app.schemas.user import (
    UserInterestCreateRequest,
    UserInterestResponse,
    UserProfileResponse,
    UserInterestUpdateRequest,
)

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile_endpoint(
    user_id: int = Depends(get_current_user_id),
) -> UserProfileResponse:
    db = get_db_sync()
    try:
        user = get_user_by_id(db, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return UserProfileResponse.model_validate(user)
    finally:
        db.close()


@router.get("/interest", response_model=UserInterestResponse)
async def get_interest_endpoint(
    user_id: int = Depends(get_current_user_id),
) -> UserInterestResponse:
    db = get_db_sync()
    try:
        user = get_user_by_id(db, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return UserInterestResponse(user_id=user.user_id, interest=user.interest)
    finally:
        db.close()


@router.post("/interest", response_model=UserInterestResponse)
async def create_interest_endpoint(
    request: UserInterestCreateRequest,
    user_id: int = Depends(get_current_user_id),
) -> UserInterestResponse:
    db = get_db_sync()
    try:
        user = update_user(db, user_id=user_id, interest=request.interest)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return UserInterestResponse(user_id=user.user_id, interest=user.interest)
    finally:
        db.close()


@router.patch("/interest", response_model=UserInterestResponse)
async def update_interest_endpoint(
    request: UserInterestUpdateRequest,
    user_id: int = Depends(get_current_user_id),
) -> UserInterestResponse:
    db = get_db_sync()
    try:
        user = update_user(db, user_id=user_id, interest=request.interest)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return UserInterestResponse(user_id=user.user_id, interest=user.interest)
    finally:
        db.close()


@router.delete("/interest", response_model=UserInterestResponse)
async def delete_interest_endpoint(
    user_id: int = Depends(get_current_user_id),
) -> UserInterestResponse:
    db = get_db_sync()
    try:
        user = update_user(db, user_id=user_id, interest=None)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return UserInterestResponse(user_id=user.user_id, interest=user.interest)
    finally:
        db.close()
