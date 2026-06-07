import re
import urllib.parse as up
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

try:
    from app.clients.cookies_loader import load_cookies
except ModuleNotFoundError:
    from clients.cookies_loader import load_cookies

BB_BASE_URL = "https://bb.sustech.edu.cn/"
PORTAL_AJAX = "https://bb.sustech.edu.cn/webapps/portal/execute/tabs/tabAction"
PARAMS = {
    "action": "refreshAjaxModule",
    "modId": "_3_1",
    "tabId": "_1_1",
}
DEFAULT_COOKIES_FILE = "clients/resources/cookies.json"

TERM_ALIASES = {
    "2026春": {"2026春", "Spring 2026"},
    "Spring 2026": {"2026春", "Spring 2026"},
}

def extract_course_id(url: str) -> str | None:
    u = up.unquote(url)
    m = re.search(r"[?&]course_id=(_\d+_\d+)", u)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=(_\d+_\d+)", u)
    if m:
        return m.group(1)
    m = re.search(r"/ultra/(?:course|courses)/(_\d+_\d+)", u)
    if m:
        return m.group(1)
    return None


def _extract_embedded_html(response_text: str) -> str:
    m = re.search(r"<contents[^>]*>([\s\S]*?)</contents>", response_text, re.I)
    html = m.group(1) if m else response_text
    stripped = html.strip()
    if stripped.startswith("<![CDATA[") and stripped.endswith("]]>"):
        return stripped[9:-3]
    return html


def _term_match(title: str, term_filter: Optional[str]) -> bool:
    if not term_filter:
        return True
    if term_filter in title:
        return True
    aliases = TERM_ALIASES.get(term_filter, {term_filter})
    return any(alias in title for alias in aliases)


def get_bb_courses(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    term_filter: Optional[str] = "2026春"
) -> List[Dict[str, str]]:
    """
    获取Blackboard课程列表
    
    Args:
        cookies_file: cookies文件路径
        term_filter: 学期过滤条件
        
    Returns:
        课程列表
    """
    cookies = load_cookies("bb", cookies_file)
    if not cookies:
        return []

    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
    })
    s.cookies.update(cookies)

    try:
        r = s.post(PORTAL_AJAX, data=PARAMS, timeout=20)
        r.raise_for_status()
    except requests.RequestException:
        return []

    html = _extract_embedded_html(r.text)

    soup = BeautifulSoup(html, "html.parser")
    results: List[Dict[str, str]] = []

    for a in soup.find_all("a", href=True):
        title = (a.get_text() or "").strip()
        href = up.urljoin(BB_BASE_URL, a["href"].strip())
        cid = extract_course_id(href)

        if cid and title:
            results.append({"title": title, "course_id": cid, "url": href})

    seen: set[str] = set()
    unique_results: List[Dict[str, str]] = []
    for course in results:
        if course["course_id"] not in seen:
            seen.add(course["course_id"])
            unique_results.append(course)

    return [course for course in unique_results if _term_match(course["title"], term_filter)]


# def save_courses_to_file(courses: List[Dict[str, str]], output_file: str = "data/courses.json") -> bool:
#     """
#     保存课程列表到文件
    
#     Args:
#         courses: 课程列表
#         output_file: 输出文件名
        
#     Returns:
#         是否保存成功
#     """
#     try:
#         Path(output_file).write_text(json.dumps(courses, ensure_ascii=False, indent=2), encoding="utf-8")
#         print(f"课程列表已保存到: {output_file}")
#         return True
#     except Exception as e:
#         print(f"保存课程列表失败: {e}")
#         return False

"""
from clients.bb.course import get_bb_courses; d=get_bb_courses();
print('type=', type(d).__name__); print('count=', len(d) if isinstance(d, list) else None); 
print('preview=', d[:5] if isinstance(d, list) else d)
"""
