from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user_id
from app.schemas.tis import (
    TisCreditResponse,
    TisGradeResponse,
    TisIdResponse,
    TisInfoQueryRequest,
    TisInfoResponse,
    TisPhotoResponse,
    TisScheduleQueryRequest,
    TisScheduleResponse,
)
from app.services.tis_service import (
    DEFAULT_COOKIES_FILE,
    get_credit_service,
    get_grade_service,
    get_info_service,
    get_photo_service,
    get_schedule_service,
    get_tis_id_service,
)

router = APIRouter(prefix="/tis", tags=["tis"])


@router.post("/schedule", response_model=TisScheduleResponse)
async def schedule_endpoint(
    request: TisScheduleQueryRequest,
    cookies_file: str = Query(default=DEFAULT_COOKIES_FILE),
    user_id: int = Depends(get_current_user_id),
) -> TisScheduleResponse:
    courses = get_schedule_service(request, cookies_file=cookies_file, user_id=user_id)
    return TisScheduleResponse(courses=courses)


@router.get("/grade", response_model=TisGradeResponse)
async def grade_endpoint(
    cookies_file: str = Query(default=DEFAULT_COOKIES_FILE),
    user_id: int = Depends(get_current_user_id),
) -> TisGradeResponse:
    try:
        return TisGradeResponse(**get_grade_service(cookies_file=cookies_file, user_id=user_id))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TIS grade failed: {exc}") from exc


@router.get("/credit", response_model=TisCreditResponse)
async def credit_endpoint(
    cookies_file: str = Query(default=DEFAULT_COOKIES_FILE),
    user_id: int = Depends(get_current_user_id),
) -> TisCreditResponse:
    try:
        return TisCreditResponse(**get_credit_service(cookies_file=cookies_file, user_id=user_id))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TIS credit failed: {exc}") from exc


@router.post("/info", response_model=TisInfoResponse)
async def info_endpoint(
    request: TisInfoQueryRequest,
    cookies_file: str = Query(default=DEFAULT_COOKIES_FILE),
) -> TisInfoResponse:
    params: dict[str, Any] = {
        "page": request.page,
        "limit": request.limit,
        "sort": request.sort,
        "order": request.order,
    }
    data = get_info_service(query_params=params, cookies_file=cookies_file)
    return TisInfoResponse(**data)


@router.get("/id", response_model=TisIdResponse)
async def tis_id_endpoint(
    cookies_file: str = Query(default=DEFAULT_COOKIES_FILE),
) -> TisIdResponse:
    return TisIdResponse(**get_tis_id_service(cookies_file=cookies_file))


@router.post("/photo", response_model=TisPhotoResponse)
async def photo_endpoint(
    cookies_file: str = Query(default=DEFAULT_COOKIES_FILE),
    user_id: int = Depends(get_current_user_id),
) -> TisPhotoResponse:
    data = get_photo_service(cookies_file=cookies_file, user_id=user_id)
    return TisPhotoResponse(**data)
