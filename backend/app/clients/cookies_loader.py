import json
from pathlib import Path
from typing import Dict

try:
    from app.core import config
except ModuleNotFoundError:
    config = None

RESOURCE_DIR = Path(__file__).resolve().parent / "resources"
DEFAULT_COOKIES_FILE = RESOURCE_DIR / "cookies.json"


def load_cookies(service: str = "bb", cookies_file: str = str(DEFAULT_COOKIES_FILE)) -> Dict[str, str]:
    """Load service cookies from file. Supported services: bb, tis."""
    try:
        service_key = (service or "").strip().lower()
        if service_key not in {"bb", "tis"}:
            print("错误: service 只支持 bb 或 tis")
            return {}

        if cookies_file:
            path = Path(cookies_file)
        elif config is not None and hasattr(config, "COOKIES_FILE"):
            path = Path(config.COOKIES_FILE)
        else:
            path = DEFAULT_COOKIES_FILE

        if not path.exists():
            print(f"错误: 找不到cookies文件 {path}")
            return {}

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        service_cookies = data.get("services", {}).get(service_key, {}).get("cookies", {})
        if not service_cookies:
            print(f"警告: 在 {path} 中未找到{service_key} cookies")
            return {}

        if service_key == "bb":
            print(f"成功加载 {len(service_cookies)} 个Blackboard cookies")
        else:
            print(f"成功加载 {len(service_cookies)} 个TIS cookies")

        return service_cookies if isinstance(service_cookies, dict) else {}
    except FileNotFoundError:
        print(f"错误: 找不到cookies文件 {cookies_file}")
        return {}
    except json.JSONDecodeError as exc:
        print(f"错误: 解析cookies文件失败 - {exc}")
        return {}
    except Exception:
        return {}
