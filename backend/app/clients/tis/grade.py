from __future__ import annotations

import warnings
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.exceptions import InsecureRequestWarning
from urllib3.util.retry import Retry

try:
	from app.clients.cookies_loader import load_cookies
except ModuleNotFoundError:
	from clients.cookies_loader import load_cookies

try:
	from app.core import config
except ModuleNotFoundError:
	from core import config


BASE_URL = "https://tis.sustech.edu.cn"
GRADE_QUERY_URL = f"{BASE_URL}/cjgl/xscjgl/xsgrcjcx/queryXnAndXqXfj"

HEADERS = {
	"Accept": "*/*",
	"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
	"User-Agent": (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
		"AppleWebKit/537.36 (KHTML, like Gecko) "
		"Chrome/120.0.0.0 Safari/537.36"
	),
	"Referer": "https://tis.sustech.edu.cn/",
	"X-Requested-With": "XMLHttpRequest",
}

DEFAULT_COOKIES_FILE = "clients/resources/cookies.json"

if not config.CAS_VERIFY_SSL:
	warnings.filterwarnings("ignore", category=InsecureRequestWarning)


def _extract_gpa_rank(data: dict[str, Any]) -> dict[str, Any]:
	xfj = data.get("xfjandpm", {})
	if not isinstance(xfj, dict):
		return {}

	result = {
		"GPA": xfj.get("PJXFJ"),
		"Rank": xfj.get("PM"),
	}

	if result["GPA"] is None or result["Rank"] is None:
		return {}
	return result


def query_grades(
	cookies_file: str = DEFAULT_COOKIES_FILE,
) -> dict[str, Any]:
	"""Query TIS GPA and rank using TIS cookies from cookies_loader."""
	cookies = load_cookies("tis", cookies_file)
	if not cookies:
		print("没有读取到有效 TIS cookies")
		return {}

	try:
		session = requests.Session()
		retry = Retry(
			total=2,
			connect=2,
			read=2,
			status=0,
			backoff_factor=0.3,
			allowed_methods=frozenset(["POST"]),
		)
		session.mount("https://", HTTPAdapter(max_retries=retry))
		session.headers.update(HEADERS)
		session.cookies.update(cookies)

		response = session.post(
			GRADE_QUERY_URL,
			timeout=config.CAS_TIMEOUT_SECONDS,
			verify=config.CAS_VERIFY_SSL,
		)
		response.raise_for_status()

		data = response.json()
		if not isinstance(data, dict):
			print("成绩查询失败: 响应不是字典")
			return {}

		result = _extract_gpa_rank(data)
		if not result:
			print("成绩查询失败: 响应缺少 xfjandpm 或字段不完整")
			return {}

		return result
	except requests.RequestException as exc:
		status_code = getattr(getattr(exc, "response", None), "status_code", None)
		print(f"查询成绩请求失败: {exc}")
		if status_code == 401:
			print("提示: 当前是 401 鉴权失败，请重新登录以刷新 TIS cookies 后重试")
		elif isinstance(exc, requests.exceptions.SSLError):
			print("提示: SSL 校验失败，可临时设置环境变量 CAS_VERIFY_SSL=false 后重试")
		else:
			print("提示: 请检查网络连通性、cookies 是否过期，或稍后重试")
		return {}
	except ValueError as exc:
		print(f"解析 JSON 失败: {exc}")
		return {}

"""python -c "from clients.tis.grade import query_grades; print(query_grades())"
"""