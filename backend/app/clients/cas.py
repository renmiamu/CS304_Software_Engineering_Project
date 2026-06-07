import json
import sys
import warnings
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from fastapi import HTTPException
from urllib3.exceptions import InsecureRequestWarning

try:
    from app.core import config
except ModuleNotFoundError:
    # Allow running from backend/app/clients for local quick tests.
    backend_root = Path(__file__).resolve().parents[2]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    from app.core import config

if not config.CAS_VERIFY_SSL:
    warnings.filterwarnings("ignore", category=InsecureRequestWarning)


SERVICES = {
    "bb": "https://bb.sustech.edu.cn/webapps/bb-sso-BBLEARN/index.jsp",
    "tis": "https://tis.sustech.edu.cn/cas",
}

RESOURCE_DIR = Path(__file__).resolve().parent / "resources"
DEFAULT_COOKIES_FILE = str(RESOURCE_DIR / "cookies.json")


def _build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"user-agent": config.CAS_USER_AGENT})
    return session


def _append_ticket(url: str, ticket: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["ticket"] = ticket
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def cas_login(sid: str, password: str, service_url: str):
    """CAS登录并获取TGT Cookie"""
    try:
        session = _build_session()
        login_page = session.get(
            config.CAS_LOGIN_URL,
            params={"service": service_url},
            verify=config.CAS_VERIFY_SSL,
            timeout=config.CAS_TIMEOUT_SECONDS,
        )

        if login_page.status_code != 200:
            raise HTTPException(status_code=502, detail="CAS服务不可用")

        execution_token = ""
        if 'name="execution"' in login_page.text:
            execution_token = login_page.text.split('name="execution" value="')[1].split('"')[0]

        login_data = {
            "username": sid,
            "password": password,
            "execution": execution_token,
            "_eventId": "submit",
            "geolocation": "",
        }

        login_response = session.post(
            config.CAS_LOGIN_URL,
            data=login_data,
            allow_redirects=False,
            verify=config.CAS_VERIFY_SSL,
            timeout=config.CAS_TIMEOUT_SECONDS,
        )

        if login_response.status_code != 302 or "Location" not in login_response.headers:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        return session.cookies.get_dict()

    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="CAS服务请求失败") from exc


def get_service_ticket(cas_cookies: dict, service_url: str):
    """获取特定服务的ST票据"""
    try:
        session = _build_session()
        session.cookies.update(cas_cookies)

        response = session.get(
            config.CAS_LOGIN_URL,
            params={"service": service_url},
            allow_redirects=False,
            verify=config.CAS_VERIFY_SSL,
            timeout=config.CAS_TIMEOUT_SECONDS,
        )

        if response.status_code != 302 or "Location" not in response.headers:
            raise ValueError("获取服务票据失败")

        location = response.headers["Location"]
        if "ticket=" not in location:
            raise ValueError("票据未找到")

        return location.split("ticket=")[1].split("&")[0]

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取服务票据失败: {str(exc)}") from exc


def get_bb_cookies(ticket: str, cas_cookies: dict | None = None) -> dict[str, str]:
    """获取BB系统cookies。失败时返回空字典。"""
    try:
        session = _build_session()
        if cas_cookies:
            session.cookies.update(cas_cookies)

        bb_url = _append_ticket(SERVICES["bb"], ticket)
        response = session.get(
            bb_url,
            allow_redirects=True,
            verify=config.CAS_VERIFY_SSL,
            timeout=config.CAS_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            return {}

        bb_cookies: dict[str, str] = {}
        for cookie in session.cookies:
            domain = cookie.domain.lower()
            name = cookie.name.lower()
            if "bb.sustech.edu.cn" in domain or "blackboard" in name:
                bb_cookies[cookie.name] = cookie.value

        return bb_cookies

    except Exception:
        return {}


def get_tis_cookies(ticket: str, cas_cookies: dict | None = None) -> dict[str, str]:
    """获取TIS系统cookies。失败时返回空字典。"""
    try:
        session = _build_session()
        if cas_cookies:
            session.cookies.update(cas_cookies)

        tis_url = _append_ticket(SERVICES["tis"], ticket)
        response = session.get(
            tis_url,
            allow_redirects=True,
            verify=config.CAS_VERIFY_SSL,
            timeout=config.CAS_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            return {}

        tis_cookies: dict[str, str] = {}
        for cookie in session.cookies:
            domain = cookie.domain.lower()
            name = cookie.name.lower()
            if "tis.sustech.edu.cn" in domain or "tis" in name:
                tis_cookies[cookie.name] = cookie.value

        return tis_cookies

    except Exception:
        return {}


def validate_cookies(service: str, cookies: dict[str, str]) -> bool:
    """验证指定服务cookies是否有效。"""
    if not cookies:
        return False

    service_key = service.lower().strip()
    if service_key in {"bb", "blackboard"}:
        test_url = "https://bb.sustech.edu.cn/webapps/portal/execute/tabs/tabAction"
    elif service_key == "tis":
        test_url = "https://tis.sustech.edu.cn/Xskbcx/queryXskbcxList"
    else:
        return False

    try:
        session = _build_session()
        response = session.get(
            test_url,
            cookies=cookies,
            allow_redirects=True,
            verify=config.CAS_VERIFY_SSL,
            timeout=config.CAS_TIMEOUT_SECONDS,
        )
        return response.status_code == 200 and "login" not in str(response.url).lower()
    except Exception:
        return False


def extract_all_cookies(
    sid: str,
    password: str,
    filename: str = DEFAULT_COOKIES_FILE,
) -> dict[str, Any]:
    """登录CAS后提取BB/TIS cookies，可选写入JSON文件。"""
    results: dict[str, Any] = {
        "sid": sid,
        "cas_login_ok": False,
        "services": {},
    }

    try:
        initial_service = SERVICES["bb"]
        cas_cookies = cas_login(sid, password, initial_service)
        results["cas_login_ok"] = bool(cas_cookies)

        for service_name, service_url in SERVICES.items():
            try:
                ticket = get_service_ticket(cas_cookies, service_url)

                if service_name == "bb":
                    service_cookies = get_bb_cookies(ticket, cas_cookies)
                elif service_name == "tis":
                    service_cookies = get_tis_cookies(ticket, cas_cookies)
                else:
                    service_cookies = {}

                is_valid = validate_cookies(service_name, service_cookies)

                results["services"][service_name] = {
                    "is_valid": is_valid,
                    "cookies": dict(service_cookies),
                }
            except Exception as exc:
                results["services"][service_name] = {
                    "error": str(exc),
                    "is_valid": False,
                }

    except Exception as exc:
        results["error"] = str(exc)


    save_cookies_to_file(results, filename)

    return results


def save_cookies_to_file(cookies_data: dict[str, Any], filename: str) -> bool:
    """保存cookies到JSON文件。"""
    try:
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(cookies_data, file, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

"""
python -c "from clients.cas import extract_all_cookies; r = extract_all_cookies('12311020', '5616298laz');print(r)"
"""
