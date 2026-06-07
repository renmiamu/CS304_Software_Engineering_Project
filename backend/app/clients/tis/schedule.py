from __future__ import annotations

import json
import re
import warnings
from pathlib import Path
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


URL = "https://tis.sustech.edu.cn/Xskbcx/queryXskbcxList"

DEFAULT_FORM = {
	"bs": "2",
	"xn": "2025-2026",
	"xq": "2",
}

HEADERS = {
	"User-Agent": "Mozilla/5.0",
	"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
	"X-Requested-With": "XMLHttpRequest",
	"Referer": "https://tis.sustech.edu.cn/webroot/decision/",
}

DEFAULT_COOKIES_FILE = "clients/resources/cookies.json"
DEFAULT_DATA_DIR = Path("clients/resources")

if not config.CAS_VERIFY_SSL:
	warnings.filterwarnings("ignore", category=InsecureRequestWarning)

WEEKDAY_MAP = {
	"1": "星期一",
	"2": "星期二",
	"3": "星期三",
	"4": "星期四",
	"5": "星期五",
	"6": "星期六",
	"7": "星期日",
}


def get_weekday_from_key(key: str) -> str:
	match = re.search(r"xq(\d+)", key or "")
	if not match:
		return "星期一"
	return WEEKDAY_MAP.get(match.group(1), "星期一")


def parse_kbxx(kbxx: str, key: str = "") -> dict[str, str]:
	"""Parse kbxx text into a structured class record."""
	if not kbxx:
		return {}

	lines = [line.strip() for line in kbxx.strip().splitlines() if line.strip()]
	if not lines:
		return {}

	course_name = lines[0] if lines else ""
	teacher = ""
	if len(lines) > 1:
		teacher_match = re.search(r"\[([^\]]+)\]", lines[1])
		teacher = teacher_match.group(1) if teacher_match else ""

	info_line = lines[-1]
	brackets = re.findall(r"\[([^\]]*)\]", info_line)

	weeks = next((s for s in brackets if "周" in s), "")
	time_slots = next((s for s in brackets if "节" in s), "")
	location = ""
	for seg in brackets:
		if seg != weeks and seg != time_slots:
			location = seg
			break

	return {
		"course_name": course_name,
		"teacher": teacher,
		"weekday": get_weekday_from_key(key),
		"weeks": weeks,
		"location": location,
		"time_slots": time_slots,
	}


def process_schedule_data(raw_data: list[dict[str, Any]]) -> list[dict[str, str]]:
	"""Convert raw TIS response list into normalized schedule records."""
	processed_courses: list[dict[str, str]] = []

	for item in raw_data or []:
		kbxx = str(item.get("kbxx") or "")
		key = str(item.get("key") or "")
		course_info = parse_kbxx(kbxx, key)
		if course_info:
			processed_courses.append(course_info)

	return processed_courses


def fetch_tis_schedule_data(
	cookies_file: str = DEFAULT_COOKIES_FILE,
	form: dict[str, str] | None = None,
	debug: bool = False,
) -> list[dict[str, Any]]:
	"""Fetch raw schedule data from TIS using cookies_loader only."""
	cookies = load_cookies("tis", cookies_file)
	if not cookies:
		print("没有读取到有效 TIS cookies")
		return []

	payload = dict(DEFAULT_FORM)
	if form:
		payload.update(form)

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
			URL,
			data=payload,
			timeout=config.CAS_TIMEOUT_SECONDS,
			verify=config.CAS_VERIFY_SSL,
		)
		response.raise_for_status()

		ctype = (response.headers.get("Content-Type") or "").lower()
		if "json" not in ctype and debug:
			print(f"返回 Content-Type 非 JSON: {ctype}")

		data = response.json()
		if isinstance(data, list):
			if debug:
				print(f"成功获取课表数据，共 {len(data)} 条")
			return data

		if isinstance(data, dict):
			content = data.get("content")
			if isinstance(content, list):
				if debug:
					print(f"成功获取课表数据 content，共 {len(content)} 条")
				return content

		if debug:
			print(f"返回结构非预期: {type(data).__name__}")
		return []
	except requests.RequestException as exc:
		status_code = getattr(getattr(exc, "response", None), "status_code", None)
		print(f"获取课表请求失败: {exc}")
		if status_code == 401:
			print("提示: 当前是 401 鉴权失败，请重新登录以刷新 TIS cookies 后重试")
		elif isinstance(exc, requests.exceptions.SSLError):
			print("提示: SSL 校验失败，可临时设置环境变量 CAS_VERIFY_SSL=false 后重试")
		else:
			print("提示: 请检查网络连通性、cookies 是否过期，或稍后重试")
		return []
	except ValueError as exc:
		print(f"解析 JSON 失败: {exc}")
		return []


def save_json(data: Any, output_file: str | Path) -> bool:
	try:
		path = Path(output_file)
		if not path.is_absolute():
			path = DEFAULT_DATA_DIR / path.name
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
		print(f"已保存: {path.resolve()}")
		return True
	except Exception as exc:
		print(f"保存失败: {exc}")
		return False


def fetch_and_process_schedule(
	cookies_file: str = DEFAULT_COOKIES_FILE,
	form: dict[str, str] | None = None,
	processed_output: str | Path | None = None,
	debug: bool = False,
) -> list[dict[str, str]]:
	"""Fetch raw schedule from TIS and return simplified parsed records."""
	raw_data = fetch_tis_schedule_data(cookies_file=cookies_file, form=form, debug=debug)
	if not raw_data:
		return []

	processed = process_schedule_data(raw_data)
	if processed_output:
		save_json(processed, processed_output)

	return processed

"""python -c "from clients.tis.schedule import fetch_and_process_schedule; d=fetch_and_process_schedule(); print('count=', len(d))"
"""