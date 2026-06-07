"""Blackboard 成绩抓取模块（简化版）。"""

import json
import re
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

try:
	from app.clients.bb.course import get_bb_courses
	from app.clients.cookies_loader import load_cookies
except ModuleNotFoundError:
	from clients.bb.course import get_bb_courses
	from clients.cookies_loader import load_cookies


BB_BASE_URL = "https://bb.sustech.edu.cn"
DEFAULT_COOKIES_FILE = "clients/resources/cookies.json"
DEFAULT_TERM_FILTER = "2026春"

_MONTH_WORDS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_TIME_WORDS = ("am", "pm", ":")


def _parse_grade_text(raw: str) -> Optional[str]:
	if not raw:
		return None

	text = " ".join(raw.split())
	lowered = text.lower().strip()
	if lowered in {"", "-", "–", "—"}:
		return None

	if any(word in lowered for word in _MONTH_WORDS):
		return None
	if any(word in lowered for word in _TIME_WORDS):
		return None
	if re.search(r"\b20\d{2}\b", lowered):
		return None

	fraction = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", lowered)
	if fraction:
		return f"{float(fraction.group(1)):.2f}/{float(fraction.group(2)):.2f}"

	if re.fullmatch(r"[abcdf][+-]?", lowered):
		return lowered.upper()

	if re.fullmatch(r"\d+(?:\.\d+)?", lowered):
		score = float(lowered)
		return f"{score:.1f}/100" if score <= 100 else f"{score:.1f}"

	return None


def _clean_item_name(raw: str) -> str:
	if not raw:
		return ""

	cleaned = re.sub(
		r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},\s+20\d{2}\b",
		"",
		raw,
		flags=re.IGNORECASE,
	)
	cleaned = re.sub(r"\b\d{1,2}:\d{2}\s*(?:AM|PM)\b", "", cleaned, flags=re.IGNORECASE)
	cleaned = re.sub(r"\b(graded|submitted|needs grading|upcoming)\b", "", cleaned, flags=re.IGNORECASE)
	cleaned = re.sub(r"\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?", "", cleaned)
	return " ".join(cleaned.split()).strip()


def extract_structured_grades(html_content: bytes, course_id: str) -> List[Dict[str, Any]]:
	"""从单个课程成绩页面提取结构化成绩。"""
	soup = BeautifulSoup(html_content, "html.parser")

	row_nodes: List[Any] = []
	for div in soup.find_all("div", {"class": "gradeTableNew"}):
		row_nodes.extend(div.find_all(["div", "tr"]))

	if not row_nodes:
		tables = soup.find_all("table", class_="gradeTable") or soup.find_all("table")
		for table in tables:
			row_nodes.extend(table.find_all("tr"))

	results: List[Dict[str, Any]] = []
	seen_names: set[str] = set()

	for row in row_nodes:
		cells = row.find_all(["div", "td", "th"])
		if len(cells) < 2:
			continue

		texts = [cell.get_text(" ", strip=True) for cell in cells]
		if not any(texts):
			continue

		item_name = _clean_item_name(texts[0])
		if not item_name or item_name in seen_names:
			continue

		grade_value: Optional[str] = None
		for candidate in texts[1:]:
			parsed = _parse_grade_text(candidate)
			if parsed:
				grade_value = parsed
				break

		if not grade_value:
			continue

		seen_names.add(item_name)
		results.append(
			{
				"course_id": course_id,
				"item_name": item_name,
				"full_grade": grade_value,
			}
		)

	return results


def crawl_bb_grades(
	cookies_file: str = DEFAULT_COOKIES_FILE,
	term_filter: Optional[str] = DEFAULT_TERM_FILTER,
) -> List[Dict[str, Any]]:
	"""抓取 Blackboard 成绩并返回结构化列表。"""
	cookies = load_cookies("bb", cookies_file)
	if not cookies:
		return []

	courses = get_bb_courses(cookies_file=cookies_file, term_filter=term_filter)
	if not courses:
		return []

	session = requests.Session()
	session.cookies.update(cookies)
	session.headers.update(
		{
			"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
			"User-Agent": (
				"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
				"AppleWebKit/537.36 (KHTML, like Gecko) "
				"Chrome/120.0.0.0 Safari/537.36"
			),
		}
	)

	course_id_to_name = {
		course["course_id"]: (course.get("title") or course.get("name") or course["course_id"])
		for course in courses
		if course.get("course_id")
	}

	all_grades: List[Dict[str, Any]] = []
	for course_id, course_name in course_id_to_name.items():
		url = f"{BB_BASE_URL}/webapps/bb-mygrades-BBLEARN/myGrades?course_id={course_id}&stream_name=mygrades"
		try:
			response = session.get(url, timeout=15)
			response.raise_for_status()
		except requests.RequestException:
			continue

		parsed_grades = extract_structured_grades(response.content, course_id)
		for item in parsed_grades:
			item["course_name"] = course_name
		all_grades.extend(parsed_grades)

	return all_grades


