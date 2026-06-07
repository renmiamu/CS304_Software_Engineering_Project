"""
Blackboard日历数据爬取脚本
从Blackboard获取个人日历数据
"""

import json
import time
import requests
from typing import Any, Dict, List, Optional

try:
    from app.clients.cookies_loader import load_cookies
except ModuleNotFoundError:
    from clients.cookies_loader import load_cookies

BASE_URL = "https://bb.sustech.edu.cn/webapps/calendar/calendarData/selectedCalendarEvents"
DEFAULT_WINDOW_DAYS = 30
DEFAULT_COOKIES_FILE = "clients/resources/cookies.json"
DEFAULT_CALENDAR_OUTPUT_FILE = "clients/resources/bb_calendar.json"
KEPT_FIELDS = {"color", "userCreated", "calendarName", "end", "title", "eventType"}


def _default_time_range_ms(days: int = DEFAULT_WINDOW_DAYS) -> tuple[int, int]:
    now = time.time()
    return int((now - days * 24 * 3600) * 1000), int((now + days * 24 * 3600) * 1000)


def _build_headers() -> Dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://bb.sustech.edu.cn/webapps/calendar/calendar.jsp",
    }


def get_calendar_data(
    cookies: Dict[str, str],
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
) -> Optional[Any]:
    """
    获取Blackboard日历数据
    
    Args:
        cookies: Blackboard cookies
        start_timestamp: 开始时间戳（毫秒）
        end_timestamp: 结束时间戳（毫秒）
    
    Returns:
        Any: 日历数据，失败时返回None
    """
    if not cookies:
        return None

    # 如果没有提供时间戳，使用当前时间前后30天
    if start_timestamp is None or end_timestamp is None:
        default_start, default_end = _default_time_range_ms()
        start_timestamp = default_start if start_timestamp is None else start_timestamp
        end_timestamp = default_end if end_timestamp is None else end_timestamp

    params = {
        "start": start_timestamp,
        "end": end_timestamp,
        "course_id": "",
        "mode": "personal",
    }

    try:
        response = requests.get(
            BASE_URL,
            params=params,
            headers=_build_headers(),
            cookies=cookies,
            timeout=30,
        )

        if response.status_code != 200:
            return None

        return response.json()
    except requests.exceptions.RequestException:
        return None
    except ValueError:
        return None


def process_calendar_data(calendar_data: Any) -> List[Dict[str, Any]]:
    """
    处理日历数据，只保留指定字段:
    color, userCreated, calendarName, end, title, eventType
    """
    if not calendar_data:
        return []

    if isinstance(calendar_data, str):
        try:
            calendar_data = json.loads(calendar_data)
        except ValueError:
            return []

    if not isinstance(calendar_data, list):
        if isinstance(calendar_data, dict):
            calendar_data = [calendar_data]
        else:
            return []

    processed_events: List[Dict[str, Any]] = []
    for event in calendar_data:
        if not isinstance(event, dict):
            continue
        filtered = {k: v for k, v in event.items() if k in KEPT_FIELDS and v not in (None, "")}
        processed_events.append(filtered)

    return processed_events


def get_bb_calendar(
    cookies_file: str = DEFAULT_COOKIES_FILE,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    获取Blackboard日历数据
    
    Args:
        cookies_file: cookies文件路径
        start_timestamp: 开始时间戳（毫秒）
        end_timestamp: 结束时间戳（毫秒）
    
    Returns:
        List[Dict]: 处理后的日历数据，失败时返回None
    """
    cookies = load_cookies("bb", cookies_file)
    if not cookies:
        return None

    # 获取日历数据
    calendar_data = get_calendar_data(cookies, start_timestamp, end_timestamp)
    if not calendar_data:
        return None

    # 处理数据
    return process_calendar_data(calendar_data)

# def save_bb_calendar_json(
#     output_path: str = DEFAULT_CALENDAR_OUTPUT_FILE,
#     cookies_file: str = DEFAULT_COOKIES_FILE,
#     start_timestamp: Optional[int] = None,
#     end_timestamp: Optional[int] = None,
# ) -> bool:
#     """获取并保存BB日历JSON"""
#     data = get_bb_calendar(
#         cookies_file=cookies_file,
#         start_timestamp=start_timestamp,
#         end_timestamp=end_timestamp,
#     )
#     if not data:
#         print("无数据，未写入。")
#         return False

#     import os

#     os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
#     with open(output_path, "w", encoding="utf-8") as f:
#         json.dump(data, f, ensure_ascii=False, indent=2)
#     print(f"已保存到 {output_path}")
#     return True