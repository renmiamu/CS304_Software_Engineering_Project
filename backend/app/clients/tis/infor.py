
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

try:
	from app.clients.cookies_loader import load_cookies
except ModuleNotFoundError:
	from clients.cookies_loader import load_cookies


BASE_URL = "https://tis.sustech.edu.cn"
QUERY_URL = f"{BASE_URL}/xjgl/fxzygl/getxjxx"

HEADERS = {
	"Accept": "*/*",
	"Content-Type": "application/json",
	"User-Agent": (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
		"AppleWebKit/537.36 (KHTML, like Gecko) "
		"Chrome/120.0.0.0 Safari/537.36"
	),
	"Referer": "https://tis.sustech.edu.cn/",
	"Origin": "https://tis.sustech.edu.cn",
}

RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources"
DEFAULT_COOKIES_FILE = str(RESOURCE_DIR / "cookies.json")
DEFAULT_DATA_DIR = RESOURCE_DIR
DEFAULT_OUTPUT_FILE = DEFAULT_DATA_DIR / "tis_infor.json"
DEFAULT_YX_LIST_FILE = DEFAULT_DATA_DIR / "yx_list.json"
DEFAULT_SY_LIST_FILE = DEFAULT_DATA_DIR / "sy_list.json"
DEFAULT_BJ_LIST_FILE = DEFAULT_DATA_DIR / "bj_list.json"

PROFILE_ALIAS_KEYS = (
	"student_id",
	"name",
	"english_name",
	"pinyin_name",
	"gender",
	"gender_code",
	"birth_date",
	"dormitory",
	"phone",
	"email",
	"college",
	"college_code",
	"department",
	"department_code",
)

# Common short-field to Chinese-field mapping.
FIELD_MAPPING = {
	"id": "id",
	"xh": "学号",
	"xm": "姓名",
	"xm_en": "英文姓名",
	"xmpy": "姓名拼音",
	"xb": "性别",
	"xbm": "性别代码",
	"zjlxm": "证件类型代码",
	"zjh": "证件号",
	"sfz": "身份证号",
	"csrq": "出生日期",
	"sjh": "手机号",
	"lxdh": "联系电话",
	"email": "邮箱",
	"dzyx": "电子邮箱",
	"yxh": "院系号",
	"yxm": "院系代码",
	"yxmc": "院系名称",
	"xy": "学院",
	"sssym": "所属书院码",
	"zymc": "专业名称",
	"zy": "专业",
	"bj": "班级",
	"bjm": "班级代码",
	"nj": "年级",
	"njm": "年级代码",
	"xz": "学制",
	"xzlx": "学籍类型",
	"rxrq": "入学日期",
	"xslb": "学生类别",
	"jg": "籍贯",
	"ssh": "宿舍号",
	"rxgkkscj": "高考成绩",
	"byzxmc": "毕业中学名称",
}

UNWANTED_KEYS = {
	"globalXmList",
	"globalxmall",
	"pylx",
	"gjm",
	"mzm",
	"zzmmm",
	"jtyb",
	"xqm",
	"xdm",
	"glyxm",
	"zyxkm",
	"ycxz",
	"pyccm",
	"sfpt",
	"sfgfs",
	"sfjljhs",
	"sfcglx",
	"bmksh",
	"ksbh",
	"sydssm",
	"kslbm",
	"xjzt",
	"sfzx",
	"sfylrjbxx",
	"sfytxxjk",
	"cjsj",
	"cjr",
	"zhxgsj",
	"zhxgr",
	"zhsjzt",
	"学制",
	"入学日期",
}


def _remove_null_values(data: Any) -> Any:
	if isinstance(data, dict):
		cleaned: dict[str, Any] = {}
		for key, value in data.items():
			if value is None:
				continue
			cleaned_value = _remove_null_values(value)
			if cleaned_value is not None:
				cleaned[key] = cleaned_value
		return cleaned

	if isinstance(data, list):
		return [item for item in (_remove_null_values(x) for x in data) if item is not None]

	return data


def _map_fields_to_chinese(data: Any) -> Any:
	if isinstance(data, dict):
		return {FIELD_MAPPING.get(key, key): _map_fields_to_chinese(value) for key, value in data.items()}

	if isinstance(data, list):
		return [_map_fields_to_chinese(item) for item in data]

	return data


def _remove_unwanted_keys(data: Any, unwanted_keys: set[str]) -> Any:
	lowered = {k.lower() for k in unwanted_keys}

	if isinstance(data, dict):
		return {
			key: _remove_unwanted_keys(value, unwanted_keys)
			for key, value in data.items()
			if key.lower() not in lowered
		}

	if isinstance(data, list):
		return [_remove_unwanted_keys(item, unwanted_keys) for item in data]

	return data


def _load_yx_mapping(yx_list_file: Path = DEFAULT_YX_LIST_FILE) -> dict[str, str]:
	"""Load department code -> department name mapping."""
	try:
		if not yx_list_file.exists():
			return {}
		yx_list = json.loads(yx_list_file.read_text(encoding="utf-8"))
		if not isinstance(yx_list, list):
			return {}

		mapping: dict[str, str] = {}
		for item in yx_list:
			if not isinstance(item, dict):
				continue
			yxmc = item.get("yxmc")
			yxdm = item.get("yxdm")
			sjyxdm = item.get("sjyxdm")
			if isinstance(yxdm, str) and isinstance(yxmc, str) and yxdm.strip() and yxmc.strip():
				mapping[yxdm.strip()] = yxmc.strip()
			if isinstance(sjyxdm, str) and isinstance(yxmc, str) and sjyxdm.strip() and sjyxdm != "0":
				mapping[sjyxdm.strip()] = yxmc.strip()
		return mapping
	except Exception:
		return {}


def _load_sy_mapping(sy_list_file: Path = DEFAULT_SY_LIST_FILE) -> dict[str, str]:
	"""Load college code -> college name mapping."""
	try:
		if not sy_list_file.exists():
			return {}
		sy_list = json.loads(sy_list_file.read_text(encoding="utf-8"))
		if not isinstance(sy_list, list):
			return {}

		mapping: dict[str, str] = {}
		for item in sy_list:
			if not isinstance(item, dict):
				continue
			code = item.get("yxdm")
			name = item.get("yxmc")
			if isinstance(code, str) and isinstance(name, str) and code.strip() and name.strip():
				mapping[code.strip()] = name.strip()
		return mapping
	except Exception:
		return {}


def _load_bj_mapping(bj_list_file: Path = DEFAULT_BJ_LIST_FILE) -> dict[str, str]:
	"""Load class code -> class name mapping."""
	try:
		if not bj_list_file.exists():
			return {}
		bj_data = json.loads(bj_list_file.read_text(encoding="utf-8"))
		content = bj_data.get("content") if isinstance(bj_data, dict) else None
		if not isinstance(content, list):
			return {}

		mapping: dict[str, str] = {}
		for item in content:
			if not isinstance(item, dict):
				continue
			code = item.get("BJDM")
			name = item.get("BJMC")
			if isinstance(code, str) and isinstance(name, str) and code.strip() and name.strip():
				mapping[code.strip()] = name.strip()
		return mapping
	except Exception:
		return {}


def _replace_code_fields_with_names(
	data: Any,
	yx_mapping: dict[str, str],
	sy_mapping: dict[str, str],
	bj_mapping: dict[str, str],
) -> Any:
	"""Replace code fields with readable names and remove original code keys."""
	if isinstance(data, dict):
		processed: dict[str, Any] = {}
		for key, value in data.items():
			if key == "院系代码" and isinstance(value, str):
				if value in yx_mapping:
					processed["院系名称"] = yx_mapping[value]
				continue

			if key == "所属书院码" and isinstance(value, str):
				if value in sy_mapping:
					processed["所属书院名称"] = sy_mapping[value]
				continue

			if key == "班级代码" and isinstance(value, str):
				if value in bj_mapping:
					processed["班级名称"] = bj_mapping[value]
				continue

			processed[key] = _replace_code_fields_with_names(value, yx_mapping, sy_mapping, bj_mapping)
		return processed

	if isinstance(data, list):
		return [_replace_code_fields_with_names(item, yx_mapping, sy_mapping, bj_mapping) for item in data]

	return data


def _as_clean_str(value: Any) -> str | None:
	if value is None:
		return None
	text = str(value).strip()
	return text or None


def _normalize_gender(value: Any) -> str | None:
	text = _as_clean_str(value)
	if not text:
		return None
	if text == "1":
		return "男"
	if text == "2":
		return "女"
	return text


def _build_profile_aliases(
	raw_result: Any,
	yx_mapping: dict[str, str],
	sy_mapping: dict[str, str],
) -> dict[str, Any]:
	if not isinstance(raw_result, dict):
		return {}

	college_code = _as_clean_str(raw_result.get("sssym")) or _as_clean_str(raw_result.get("xy"))
	department_name = _as_clean_str(raw_result.get("zymc")) or _as_clean_str(raw_result.get("yxmc"))
	department_code = _as_clean_str(raw_result.get("yxm")) or _as_clean_str(raw_result.get("yxh"))
	gender_code = _as_clean_str(raw_result.get("xbm")) or _as_clean_str(raw_result.get("xb"))

	aliases = {
		"student_id": _as_clean_str(raw_result.get("xh")),
		"name": _as_clean_str(raw_result.get("xm")),
		"english_name": _as_clean_str(raw_result.get("xm_en")),
		"pinyin_name": _as_clean_str(raw_result.get("xmpy")),
		"gender": _normalize_gender(gender_code),
		"gender_code": gender_code,
		"birth_date": _as_clean_str(raw_result.get("csrq")),
		"dormitory": _as_clean_str(raw_result.get("ssh")),
		"phone": _as_clean_str(raw_result.get("lxdh")) or _as_clean_str(raw_result.get("sjh")),
		"email": _as_clean_str(raw_result.get("dzyx")) or _as_clean_str(raw_result.get("email")),
		"college": sy_mapping.get(college_code or "", college_code),
		"college_code": college_code,
		"department": department_name or yx_mapping.get(department_code or "", department_code),
		"department_code": department_code,
	}
	return {key: value for key, value in aliases.items() if value is not None}


def _normalize_result(
	raw_result: Any,
	yx_mapping: dict[str, str],
	sy_mapping: dict[str, str],
	bj_mapping: dict[str, str],
) -> Any:
	cleaned = _remove_null_values(raw_result)
	mapped = _map_fields_to_chinese(cleaned)
	replaced = _replace_code_fields_with_names(mapped, yx_mapping, sy_mapping, bj_mapping)
	normalized = _remove_unwanted_keys(replaced, UNWANTED_KEYS)
	aliases = _build_profile_aliases(cleaned, yx_mapping, sy_mapping)
	if isinstance(normalized, dict):
		for key in PROFILE_ALIAS_KEYS:
			value = aliases.get(key)
			if value is not None:
				normalized[key] = value

	return normalized


def _save_result(data: Any, output_file: str | Path | None) -> None:
	if output_file is None:
		path = Path(DEFAULT_OUTPUT_FILE)
	else:
		path = Path(output_file)
		if not path.is_absolute():
			path = DEFAULT_DATA_DIR / path.name

	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=2)


def query_tis_data(
	query_params: dict[str, Any] | None = None,
	cookies_file: str = DEFAULT_COOKIES_FILE,
	output_file: str | Path | None = DEFAULT_OUTPUT_FILE,
	debug: bool = False,
) -> Any:
	"""Query TIS student info.

	Note:
	- sid/password are kept only for compatibility.
	- Cookie source is always cookies_loader.load_cookies("tis", cookies_file).
	"""
	
	cookies = load_cookies("tis", cookies_file)
	if not cookies:
		print("没有读取到有效 TIS cookies")
		return None

	payload = {
		"page": 1,
		"limit": 100,
		"sort": "id",
		"order": "desc",
	}
	if query_params:
		payload.update(query_params)

	try:
		yx_mapping = _load_yx_mapping()
		sy_mapping = _load_sy_mapping()
		bj_mapping = _load_bj_mapping()

		session = requests.Session()
		session.headers.update(HEADERS)
		session.cookies.update(cookies)

		response = session.post(QUERY_URL, json=payload, timeout=30, allow_redirects=True)
		response.raise_for_status()
		raw_result = response.json()

		result = _normalize_result(raw_result, yx_mapping, sy_mapping, bj_mapping)

		if debug:
			print(f"查询成功: {QUERY_URL}")
			print(f"状态码: {response.status_code}")
			if isinstance(result, dict):
				print(f"返回字段数: {len(result)}")
			elif isinstance(result, list):
				print(f"返回条目数: {len(result)}")

		_save_result(result, output_file)
		'''保存json关闭'''
		return result
	except requests.RequestException as exc:
		print(f"请求失败: {exc}")
		return None
	except json.JSONDecodeError as exc:
		print(f"JSON 解析失败: {exc}")
		return None
	except Exception as exc:
		print(f"查询失败: {exc}")
		return None

