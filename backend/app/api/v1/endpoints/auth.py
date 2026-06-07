from fastapi import APIRouter, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends

from app.services.auth_service import list_services, logout, sso_login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/services")
async def list_services_endpoint() -> dict[str, object]:
	return {"services": list_services()}


@router.post("/login")
async def login_endpoint(
	form_data: OAuth2PasswordRequestForm = Depends(),
	service: str = Query(default="all", description="Target service key, e.g. all/bb/tis/blackboard/mail"),
) -> dict[str, object]:
	try:
		return sso_login(form_data.username, form_data.password, service)
	except HTTPException:
		raise
	except Exception as exc:
		raise HTTPException(status_code=500, detail=f"Login failed: {exc}") from exc


@router.post("/logout")
async def logout_endpoint() -> dict[str, str]:
	return logout()

