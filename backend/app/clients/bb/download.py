import json
import os
import re
from typing import Dict, List, Optional
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
	from app.clients.bb.course import get_bb_courses
	from app.clients.cookies_loader import load_cookies
except ModuleNotFoundError:
	from clients.bb.course import get_bb_courses
	from clients.cookies_loader import load_cookies


DEFAULT_COOKIES_FILE = "clients/resources/cookies.json"
DEFAULT_TERM_FILTER = "2026春"
FILE_EXTENSIONS = {
	".pdf",
	".ppt",
	".pptx",
	".doc",
	".docx",
	".zip",
	".rar",
	".7z",
	".png",
	".jpg",
	".jpeg",
	".mp4",
	".txt",
	".xlsx",
	".xls",
}


def clean_filename(name: str) -> str:
	safe = re.sub(r"[<>:\"/\\|?*]", "_", name)
	safe = re.sub(r"\s+", " ", safe).strip().strip(".")
	return safe or "unnamed"


def _build_session(cookies: Dict[str, str]) -> requests.Session:
	session = requests.Session()
	session.cookies.update(cookies)
	session.headers.update(
		{
			"User-Agent": (
				"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
				"AppleWebKit/537.36 (KHTML, like Gecko) "
				"Chrome/91.0.4472.124 Safari/537.36"
			)
		}
	)
	return session


def _looks_like_file_url(url: str) -> bool:
	if not url:
		return False
	parsed = urlparse(url)
	path = parsed.path.lower()
	if any(path.endswith(ext) for ext in FILE_EXTENSIONS):
		return True
	query = parsed.query.lower()
	if any(flag in query for flag in ("download", "attachment", "file")):
		return True
	return "bbcswebdav" in url.lower()


def _build_filename(url: str, link_text: str = "") -> str:
	if link_text:
		text_name = clean_filename(link_text)
		ext = os.path.splitext(urlparse(url).path)[1].lower()
		if ext and not text_name.lower().endswith(ext):
			text_name = f"{text_name}{ext}"
		return text_name

	path_name = os.path.basename(urlparse(url).path)
	return clean_filename(unquote(path_name or "unnamed"))


def _extract_file_links(session: requests.Session, page_url: str) -> List[Dict[str, str]]:
	try:
		response = session.get(page_url, timeout=20)
		response.raise_for_status()
	except requests.RequestException:
		return []

	soup = BeautifulSoup(response.text, "html.parser")
	seen: set[str] = set()
	links: List[Dict[str, str]] = []

	for anchor in soup.find_all("a", href=True):
		full_url = urljoin(response.url, anchor["href"].strip())
		if not _looks_like_file_url(full_url) or full_url in seen:
			continue
		seen.add(full_url)
		links.append(
			{
				"url": full_url,
				"text": (anchor.get_text() or "").strip(),
			}
		)
	return links


def _extract_content_pages(session: requests.Session, course_url: str) -> List[Dict[str, str]]:
	try:
		response = session.get(course_url, timeout=20, allow_redirects=True)
		response.raise_for_status()
	except requests.RequestException:
		return []

	soup = BeautifulSoup(response.text, "html.parser")
	seen: set[str] = set()
	pages: List[Dict[str, str]] = []

	for anchor in soup.find_all("a", href=True):
		href = anchor["href"].lower()
		if not any(token in href for token in ("listcontent", "content", "coursecontent")):
			continue

		page_url = urljoin(response.url, anchor["href"].strip())
		if page_url in seen:
			continue

		seen.add(page_url)
		pages.append(
			{
				"url": page_url,
				"name": (anchor.get_text() or "").strip() or "课程内容",
			}
		)

	return pages


def crawl_bb_files(
	cookies_file: str = DEFAULT_COOKIES_FILE,
	term_filter: Optional[str] = DEFAULT_TERM_FILTER,
) -> str:
	"""收集课程文件链接并返回 JSON 字符串。"""
	courses = get_bb_courses(cookies_file=cookies_file, term_filter=term_filter)
	if not courses:
		return "[]"

	cookies = load_cookies("bb", cookies_file)
	if not cookies:
		return "[]"

	session = _build_session(cookies)
	all_files: List[Dict[str, str]] = []
	seen_pairs: set[tuple[str, str]] = set()

	for course in courses:
		course_name = course.get("title", "")
		course_url = course.get("url", "")
		if not course_name or not course_url:
			continue

		content_pages = _extract_content_pages(session, course_url)
		for page in content_pages:
			file_links = _extract_file_links(session, page["url"])
			for item in file_links:
				key = (course_name, item["url"])
				if key in seen_pairs:
					continue
				seen_pairs.add(key)
				all_files.append(
					{
						"course": course_name,
						"content": page["name"],
						"file_url": item["url"],
						"file_name": _build_filename(item["url"], item["text"]),
					}
				)

	return json.dumps(all_files, ensure_ascii=False, indent=2)

"""
python  -c "from clients.bb.download import crawl_bb_files
>> print(crawl_bb_files()) "
"""