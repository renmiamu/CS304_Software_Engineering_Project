from __future__ import annotations

import warnings
from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

try:
	from app.clients.cookies_loader import load_cookies
except ModuleNotFoundError:
	from clients.cookies_loader import load_cookies

try:
	from app.core import config
except ModuleNotFoundError:
	from core import config


BASE_URL = "https://tis.sustech.edu.cn"
GRADES_DETAIL_URL = f"{BASE_URL}/cjgl/grcjcx/grcjcx"

HEADERS = {
	"Accept": "application/json, text/javascript, */*; q=0.01",
	"Content-Type": "application/json",
	"Origin": "https://tis.sustech.edu.cn",
	"Referer": "https://tis.sustech.edu.cn/cjgl/grcjcx/go/1",
	"User-Agent": (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
		"AppleWebKit/537.36 (KHTML, like Gecko) "
		"Chrome/120.0.0.0 Safari/537.36"
	),
	"X-Requested-With": "XMLHttpRequest",
	"Rolecode": "01",
}

DEFAULT_COOKIES_FILE = "clients/resources/cookies.json"

if not config.CAS_VERIFY_SSL:
	warnings.filterwarnings("ignore", category=InsecureRequestWarning)


def analyze_credits_to_json(data: dict[str, Any]) -> dict[str, Any]:
	"""Summarize total and category credits from TIS grade response."""
	total_credit = 0.0
	category_credits: dict[str, float] = {}

	records = data.get("content", {}).get("list", [])
	if not isinstance(records, list):
		records = []

	for course in records:
		if not isinstance(course, dict):
			continue

		try:
			credit = float(course.get("xf", 0) or 0)
		except (TypeError, ValueError):
			credit = 0.0

		category = str(course.get("kclb") or "未分类")
		total_credit += credit
		category_credits[category] = category_credits.get(category, 0.0) + credit

	return {
		"total_credit": total_credit,
		"category_credit": category_credits,
	}


def query_credits(
	cookies_file: str = DEFAULT_COOKIES_FILE,
) -> dict[str, Any]:
	"""Query TIS grade details and return credit summary.
	"""
	cookies = load_cookies("tis", cookies_file)
	if not cookies:
		print("没有读取到有效 TIS cookies")
		return {}

	payload = {
		"xn": None,
		"xq": None,
		"kcmc": None,
		"cxbj": "-1",
		"pylx": "1",
		"current": 1,
		"pageSize": 60,
		"sffx": None,
	}

	try:
		session = requests.Session()
		session.headers.update(HEADERS)
		session.cookies.update(cookies)

		response = session.post(
			GRADES_DETAIL_URL,
			json=payload,
			timeout=config.CAS_TIMEOUT_SECONDS,
			verify=config.CAS_VERIFY_SSL,
		)
		response.raise_for_status()

		data = response.json()
		return analyze_credits_to_json(data if isinstance(data, dict) else {})
	except requests.RequestException as exc:
		status_code = getattr(getattr(exc, "response", None), "status_code", None)
		print(f"请求失败: {exc}")
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

