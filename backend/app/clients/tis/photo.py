import base64
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import requests

try:
	from app.clients.cookies_loader import load_cookies
except ModuleNotFoundError:
	from clients.cookies_loader import load_cookies

try:
	from app.clients.tis.infor import query_tis_data
except ModuleNotFoundError:
	from clients.tis.infor import query_tis_data


BASE_URL = "https://tis.sustech.edu.cn"
INIT_SZXZP_URL = "/xjgl/xjxxgl/xsxxdate/initxszp"

DEFAULT_COOKIES_FILE = "clients/resources/cookies.json"
DEFAULT_OUTPUT_DIR = "clients/resources/photos"

HEADERS = {
	"User-Agent": (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
		"AppleWebKit/537.36 (KHTML, like Gecko) "
		"Chrome/91.0.4472.124 Safari/537.36"
	),
	"Referer": "https://tis.sustech.edu.cn/",
}


def _build_session(cookies: dict[str, str]) -> requests.Session:
	session = requests.Session()
	session.headers.update(HEADERS)
	session.cookies.update(cookies)
	return session


def get_tis_id(cookies_file: str = DEFAULT_COOKIES_FILE) -> str | None:
	"""Query TIS info and return the first available internal id."""
	data = query_tis_data(cookies_file=cookies_file, output_file=None)
	if not data:
		return None

	if isinstance(data, dict):
		value = data.get("id")
		return str(value) if value is not None else None

	if isinstance(data, list) and data:
		first = data[0]
		if isinstance(first, dict):
			value = first.get("id")
			return str(value) if value is not None else None

	return None


def fetch_rxzp_by_id(the_id: str | dict | set | list | tuple, cookies: dict) -> str | None:
    """
    用 id 请求 initszp 接口，返回 rxzp 路径（对 the_id 做强制规范化）
    """
    api = urljoin(BASE_URL, INIT_SZXZP_URL)
    
    # --- 规范化 the_id ---
    # 允许你不小心传了 {"id": "..."}、{"id", "..."} 等
    if isinstance(the_id, dict) and "id" in the_id:
        the_id = the_id["id"]
    elif isinstance(the_id, (set, list, tuple)):
        # 取第一个元素（集合会被遍历一次）
        if not the_id:
            print("the_id 是空集合/列表/元组，无法获取 id")
            return None
        the_id = next(iter(the_id))

    # 最终强制转成字符串
    the_id = str(the_id)

    payload = {"id": the_id}

    # 调试日志：确认没有 set 混入
    print(f"[fetch_rxzp_by_id] payload={payload} (types: id={type(the_id).__name__})")

    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        s.cookies.update(cookies)

        resp = s.post(api, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        rxzp = data.get("rxzp")
        if isinstance(rxzp, str) and rxzp.strip():
            print("获取 rxzp 成功:", rxzp)
            return rxzp
        print("返回没有 rxzp:", data)
        return None
    except Exception as e:
        print("fetch_rxzp_by_id 失败:", e)
        return None



def _infer_image_type(content_type: str, photo_path: str) -> str:
	if content_type:
		subtype = content_type.split(";")[0].strip().lower().split("/")[-1]
		if subtype == "jpeg":
			return "jpg"
		if subtype:
			return subtype

	suffix = Path(photo_path).suffix.lower().lstrip(".")
	return suffix or "jpg"


def download_student_photo(
	cookies_file: str = DEFAULT_COOKIES_FILE,
	output_dir: Optional[str] = DEFAULT_OUTPUT_DIR,
) -> Optional[dict[str, Any]]:
	"""
	下载学生照片并返回 Base64 信息。

	参数:
		rxzp_path: 可选。若已知照片路径可直接下载。
		cookies_file: cookies 文件路径。
		output_dir: 可选输出目录；传 None 表示不落盘。

	返回:
		成功时返回包含 base64、文件信息的字典；失败返回 None。
	"""
	cookies = load_cookies("tis", cookies_file)
	if not cookies:
		print("无法获取有效的TIS cookies")
		return None

	identity = get_tis_id(cookies_file=cookies_file)
	if not identity:
		print("无法获取内部 id，且 sid 为空，无法查询照片路径")
		return None
	photo_path = fetch_rxzp_by_id(identity, cookies)

	if not photo_path:
		print("无法获取照片路径")
		return None

	url = urljoin(BASE_URL, photo_path)
	try:
		session = _build_session(cookies)
		response = session.get(url, timeout=20, allow_redirects=True)
		response.raise_for_status()

		image_data = response.content
		image_type = _infer_image_type(response.headers.get("Content-Type", ""), photo_path)

		filename = Path(photo_path).name or f"student_photo.{image_type}"
		base64_string = base64.b64encode(image_data).decode("utf-8")

		saved_path: Optional[Path] = None
		if output_dir:
			out_dir = Path(output_dir)
			out_dir.mkdir(parents=True, exist_ok=True)
			saved_path = out_dir / filename
			with saved_path.open("wb") as f:
				f.write(image_data)

		return {
			"base64": base64_string,
			"filename": filename,
			"type": image_type,
		}
	except requests.RequestException as exc:
		print(f"下载失败: {exc}")
		return None
	except Exception as exc:
		print(f"处理失败: {exc}")
		return None

"""
python -c "from clients.tis.photo import download_student_photo; r=download_student_photo(); print(r is not None)"
"""