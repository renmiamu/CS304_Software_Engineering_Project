import json
from pathlib import Path

from fastapi import HTTPException, status

from app.clients.cas import (
    SERVICES,
    cas_login,
    extract_all_cookies,
    get_bb_cookies,
    get_service_ticket,
    get_tis_cookies,
    validate_cookies,
)
from app.clients.cookies_loader import load_cookies
from app.clients.tis.infor import query_tis_data
from app.core.database import get_db_sync
from app.core.security import generate_access_jwt
from app.db.CRUD.user import create_user, get_user_by_email, get_user_by_id, update_user

SERVICE_MAP = {
    "tis": SERVICES["tis"],
    "bb": SERVICES["bb"],
    "mail": "https://mail.sustech.edu.cn/",
}

DEFAULT_LOGIN_SERVICES = ("bb", "tis")
RESOURCE_DIR = Path(__file__).resolve().parents[1] / "clients" / "resources"
DEFAULT_COOKIES_FILE = str(RESOURCE_DIR / "cookies.json")


def _load_cookie_bundle(cookies_file: str = DEFAULT_COOKIES_FILE) -> dict:
    try:
        path = Path(cookies_file)
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _can_reuse_saved_cookies(username: str, services: tuple[str, ...] = DEFAULT_LOGIN_SERVICES) -> bool:
    cookie_bundle = _load_cookie_bundle(DEFAULT_COOKIES_FILE)
    if not cookie_bundle:
        return False

    if str(cookie_bundle.get("sid", "")).strip() != username.strip():
        return False

    for service in services:
        cookies = load_cookies(service, DEFAULT_COOKIES_FILE)
        if not cookies or not validate_cookies(service, cookies):
            return False

    return True


def _get_or_refresh_all_service_cookies(username: str, password: str) -> dict[str, object]:
    if _can_reuse_saved_cookies(username, DEFAULT_LOGIN_SERVICES):
        cookie_bundle = _load_cookie_bundle(DEFAULT_COOKIES_FILE)
        services = cookie_bundle.get("services", {})
        if isinstance(services, dict):
            return services

    return extract_all_cookies(username, password, filename=DEFAULT_COOKIES_FILE).get("services", {})


def _as_clean_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_birth_date(value: object) -> str | None:
    text = _as_clean_str(value)
    if not text:
        return None
    return text.split(" ", 1)[0]


def _extract_user_payload_from_infor(infor: object, sid_int: int, username: str) -> dict[str, object]:
    data = infor if isinstance(infor, dict) else {}

    name = _as_clean_str(data.get("name")) or username
    email = _as_clean_str(data.get("email")) or f"{username}@mail.sustech.edu.cn"

    return {
        "user_id": sid_int,
        "name": name,
        "pinyin_name": _as_clean_str(data.get("pinyin_name")),
        "gender": _as_clean_str(data.get("gender")),
        "birth_date": _normalize_birth_date(data.get("birth_date")),
        "college": _as_clean_str(data.get("college")),
        "dormitory": _as_clean_str(data.get("dormitory")),
        "phone": _as_clean_str(data.get("phone")),
        "email": email,
        "department": _as_clean_str(data.get("department")),
    }


def _initialize_user_on_login(username: str, password: str, refresh_cookies: bool = True) -> dict[str, object]:
    try:
        sid_int = int(username)
    except ValueError:
        return {"ok": False, "reason": "username is not numeric sid"}

    if refresh_cookies:
        extract_all_cookies(username, password, filename=DEFAULT_COOKIES_FILE)

    db = get_db_sync()
    try:
        existing = get_user_by_id(db, sid_int)
        if existing is not None:
            return {"ok": True, "user_id": existing.user_id, "created": False}

        infor = query_tis_data(cookies_file=DEFAULT_COOKIES_FILE, output_file=None, debug=False)
        payload = _extract_user_payload_from_infor(infor, sid_int, username)

        existing_email = get_user_by_email(db, payload["email"])
        if existing_email is not None:
            updated = update_user(
                db,
                user_id=existing_email.user_id,
                name=payload.get("name"),
                pinyin_name=payload.get("pinyin_name"),
                gender=payload.get("gender"),
                birth_date=payload.get("birth_date"),
                college=payload.get("college"),
                dormitory=payload.get("dormitory"),
                phone=payload.get("phone"),
                email=payload.get("email"),
                department=payload.get("department"),
            )
            user_id = existing_email.user_id if updated is None else updated.user_id
            return {"ok": True, "user_id": user_id, "created": False}

        created = create_user(db, **payload)
        return {"ok": True, "user_id": created.user_id, "created": True}
    finally:
        db.close()


def list_services() -> dict[str, str]:
    return dict(SERVICE_MAP)


def _resolve_service(service: str) -> tuple[str, str]:
    service_key = service.lower().strip()
    if service_key == "blackboard":
        service_key = "bb"
    service_url = SERVICE_MAP.get(service_key)
    if service_url is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported service")
    return service_key, service_url


def _extract_service_cookies(service: str, ticket: str, cas_cookies: dict[str, str]) -> dict[str, str]:
    if service == "bb":
        return get_bb_cookies(ticket, cas_cookies)
    if service == "tis":
        return get_tis_cookies(ticket, cas_cookies)
    return {}


def _is_service_cookie_valid(service: str, cookies: dict[str, str]) -> bool:
    if service in {"bb", "tis"}:
        return validate_cookies(service, cookies)
    return bool(cookies)


def _login_multiple_services(username: str, password: str, services: tuple[str, ...]) -> dict[str, object]:
    cas_cookies = cas_login(username, password, SERVICE_MAP["bb"])
    service_results: dict[str, object] = {}

    for service in services:
        service_url = SERVICE_MAP[service]
        try:
            ticket = get_service_ticket(cas_cookies, service_url)
            service_cookies = _extract_service_cookies(service, ticket, cas_cookies)
            is_valid = _is_service_cookie_valid(service, service_cookies)
            service_results[service] = {
                "is_valid": is_valid,
                "cookies": service_cookies,
            }
        except Exception as exc:
            service_results[service] = {
                "is_valid": False,
                "error": str(exc),
            }

    return service_results


def sso_login(username: str, password: str, service: str = "all") -> dict[str, object]:
    if not username.strip() or not password.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username and password are required")

    service_key = (service or "all").strip().lower()
    access_token = generate_access_jwt(username)

    if service_key in {"", "all", "both"}:
        services = _get_or_refresh_all_service_cookies(username, password)
        try:
            user_init = _initialize_user_on_login(username, password, refresh_cookies=False)
        except Exception as exc:
            user_init = {"ok": False, "error": str(exc)}
        return {
            "message": "login success",
            "service": "all",
            "services": services,
            "user_init": user_init,
            "access_token": access_token,
            "token_type": "bearer",
        }

    resolved_service, service_url = _resolve_service(service_key)
    cookies = cas_login(username, password, service_url)

    try:
        user_init = _initialize_user_on_login(username, password)
    except Exception as exc:
        user_init = {"ok": False, "error": str(exc)}

    return {
        "message": "login success",
        "service": resolved_service,
        "cookies": cookies,
        "user_init": user_init,
        "access_token": access_token,
        "token_type": "bearer",
    }


def logout() -> dict[str, str]:
    return {"message": "logout success"}
