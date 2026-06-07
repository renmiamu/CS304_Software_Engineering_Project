from app.services.core.retrieval import retrieve_content
from app.services.web_search.procss_web_search import store_and_query_snippets
from app.services.agent.text2sql_tool import execute_text2sql_tool
from app.services.agent import text2sql_tool as text2sql_module
from app.services.mail_service import send_mail_service
from app.schemas.text2sql import Text2SQLRequest
from app.core.database import get_db_sync
import json
from openai import OpenAI
import os
import re
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

_AGENT_CONFIRMATION_TTL_SECONDS = 300
_PENDING_MAIL_CONFIRMATIONS = {}
_PENDING_FILE_CONFIRMATIONS = {}

_DEFAULT_WORKSPACE_ROOT = Path(os.getenv("AGENT_FILE_WORKSPACE_ROOT", Path(__file__).resolve().parents[4])).resolve()
_USER_FILE_WORKSPACES = {}
_FILE_TOOL_MAX_READ_BYTES = int(os.getenv("AGENT_FILE_MAX_READ_BYTES", "200000"))
_FILE_TOOL_MAX_WRITE_BYTES = int(os.getenv("AGENT_FILE_MAX_WRITE_BYTES", "200000"))
_FILE_TOOL_BLOCKED_PARTS = {
    ".git",
    ".agent-trash",
    ".nuxt",
    ".output",
    "__pycache__",
    "node_modules",
    "nltk_data",
}
_FILE_TOOL_BLOCKED_NAMES = {
    ".env",
    "test.db",
}
_FILE_TOOL_ALLOWED_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".yaml",
    ".yml",
}

def _build_llm_client(model_name: str) -> OpenAI:
    """
    按模型名称选择对应供应商配置，避免 API key 与 base_url 不匹配。
    - deepseek-*：优先 DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL
    - 其他模型：使用 DASHSCOPE_API_KEY / DASHSCOPE_BASE_URL
    """
    if model_name.startswith("deepseek"):
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1"
    else:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        base_url = os.getenv("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"

    if not api_key:
        raise RuntimeError(f"Missing API key for model: {model_name}")

    return OpenAI(api_key=api_key, base_url=base_url)

def extract_json_content(input_str):
    """
    提取字符串中第一个"["和最后一个"]"之间的内容（包括中括号）
    
    Args:
        input_str (str): 需要处理的输入字符串
    
    Returns:
        str or None: 提取的JSON内容，如果没有匹配则返回None
    """
    # 使用正则表达式匹配第一个"["到最后一个"]"之间的内容
    # [\s\S]* 匹配任意字符（包括换行符）
    pattern = r'(\[[\s\S]*\])'
    match = re.search(pattern, input_str)
    
    # 如果匹配成功，返回匹配的内容；否则返回None
    return match.group(1) if match else None


def extract_json_object_content(input_str):
    """
    提取字符串中第一个"{"和最后一个"}"之间的内容（包括花括号）
    """
    pattern = r'(\{[\s\S]*\})'
    match = re.search(pattern, input_str)
    return match.group(1) if match else None

def middle_json_model(prompt):
    planner_model = os.getenv("AGENT_PLANNER_MODEL", "deepseek-chat")
    client = _build_llm_client(planner_model)
    completion = client.chat.completions.create(
        model=planner_model,
        messages=[
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': prompt}],
        response_format={"type": "json_object"}
        )
        
    return completion.choices[0].message.content


def _build_text2sql_schema_summary() -> str:
    lines = []
    for table_name, fields in text2sql_module.ALLOWED_ENTITY_TABLES.items():
        lines.append(f"- {table_name}: {', '.join(fields)}")
    return "\n".join(lines)


def _build_text2sql_permission_summary(user_id: str) -> str:
    return f"""
权限边界：
- 当前用户 user_id = {user_id}
- 只允许访问以下表：{", ".join(text2sql_module.ALLOWED_ENTITY_TABLES.keys())}
- users / credits / deadlines：只能读取当前 user_id 对应的数据
- schedules：只能读取或修改通过 user_schedule_association 关联到当前 user_id 的日程
- 绝不允许生成跨用户查询，不允许访问未列出的表和列
- 允许的写操作只有：create_schedule / update_schedule / delete_schedule
- 所有写操作第一次都必须输出 confirm=false，等待用户确认后才能真正执行
""".strip()


def _generate_text2sql_request_from_query(query: str, user_id: str):
    schema_summary = _build_text2sql_schema_summary()
    permission_summary = _build_text2sql_permission_summary(user_id)
    current_date = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""
你是一个 Text2SQL 规划器，但你不能直接输出 SQL。你的任务是：
1. 根据用户自然语言理解要查询或修改什么
2. 只能基于给定表名、列名和权限边界，输出一个结构化 JSON 对象
3. 输出必须可被后端安全执行

今天日期：{current_date}

可用表和列：
{schema_summary}

{permission_summary}

允许的 operation：
- schema
- select_entities
- create_schedule
- update_schedule
- delete_schedule

输出 JSON 格式：
{{
  "operation": "schema|select_entities|create_schedule|update_schedule|delete_schedule",
  "filters": {{}},
  "data": {{}},
  "limit": 20,
  "confirm": false,
  "confirmation_id": null
}}

规则：
- 查询个人资料/学分/DDL/课程安排时，使用 select_entities
- 查询时把目标表写到 filters.table
- 如果问题提到“本周/这周/今天/明天/后天/未来7天”，优先写入 filters.relative_date
- 如果问题提到课程名、老师、地点、星期几、是否完成等，请尽量映射到 filters 或 data
- schedules.weekday 必须输出整数 1-7，周一=1，周二=2，...，周六=6，周日=7；不要输出 Monday/Saturday 这类英文字符串
- 对 schedules 的新增、修改、删除，必须使用 create_schedule / update_schedule / delete_schedule
- 写操作第一次必须输出 confirm=false
- 如果用户想修改或删除某个 schedule，优先提取 schedule_id；如果没有明确 schedule_id，也可以把 name/weekday/start_time 等放进 data，由后端进一步校验
- 不要生成多余字段，不要输出解释文字，不要输出 markdown，只输出 JSON 对象

用户请求：
{query}
""".strip()

    result = middle_json_model(prompt)
    json_object = extract_json_object_content(result)
    if not json_object:
        raise ValueError("模型没有返回有效的 Text2SQL JSON 对象")
    try:
        payload = json.loads(json_object)
    except Exception as exc:
        raise ValueError("模型返回的 Text2SQL JSON 无法解析") from exc
    if not isinstance(payload, dict):
        raise ValueError("模型返回的 Text2SQL 结果不是 JSON 对象")
    return payload

# rag搜索
def rag(query: str, index_name: str):
    rag_results = retrieve_content(index_name, query)

    return rag_results

# 网页搜索
def web_search_answer(query):
    # 简化版本：直接使用搜索结果，不进行向量化处理
    try:
        from app.services.web_search.web_search import serper_search, process_search_results
        
        # 直接获取搜索结果
        search_results = serper_search(query)
        snippets, related_questions = process_search_results(search_results)
        
        # 直接返回搜索结果，不需要向量化和相似度计算
        return snippets
        
    except Exception as e:
        print(f"网络搜索失败: {e}")
        return f"网络搜索暂时不可用，错误信息: {str(e)}"


def _cleanup_mail_confirmations():
    now = datetime.utcnow()
    expired_ids = [
        confirmation_id
        for confirmation_id, record in _PENDING_MAIL_CONFIRMATIONS.items()
        if record["expires_at"] <= now
    ]
    for confirmation_id in expired_ids:
        _PENDING_MAIL_CONFIRMATIONS.pop(confirmation_id, None)


def _create_mail_confirmation(user_id: int, payload: dict):
    _cleanup_mail_confirmations()
    confirmation_id = str(uuid4())
    _PENDING_MAIL_CONFIRMATIONS[confirmation_id] = {
        "user_id": user_id,
        "payload": payload,
        "expires_at": datetime.utcnow() + timedelta(seconds=_AGENT_CONFIRMATION_TTL_SECONDS),
    }
    return confirmation_id


def _validate_mail_confirmation(user_id: int, payload: dict, confirmation_id: str):
    _cleanup_mail_confirmations()
    record = _PENDING_MAIL_CONFIRMATIONS.get(confirmation_id)
    if not record:
        raise ValueError("confirmation_id 无效或已过期")
    if record["user_id"] != user_id:
        raise ValueError("confirmation_id 不属于当前用户")
    if record["payload"] != payload:
        raise ValueError("待确认邮件内容已变化，请重新确认")
    _PENDING_MAIL_CONFIRMATIONS.pop(confirmation_id, None)


def _get_latest_pending_mail_confirmation(user_id: int):
    _cleanup_mail_confirmations()
    pending = [
        {
            "confirmation_id": confirmation_id,
            **record,
        }
        for confirmation_id, record in _PENDING_MAIL_CONFIRMATIONS.items()
        if record["user_id"] == user_id
    ]
    if not pending:
        return None
    pending.sort(key=lambda item: item["expires_at"], reverse=True)
    return pending[0]


def _consume_mail_confirmation(confirmation_id: str):
    return _PENDING_MAIL_CONFIRMATIONS.pop(confirmation_id, None)


def _get_latest_pending_sql_confirmation(user_id: int):
    text2sql_module._cleanup_confirmations()
    pending = [
        {
            "confirmation_id": confirmation_id,
            **record,
        }
        for confirmation_id, record in text2sql_module._PENDING_CONFIRMATIONS.items()
        if record["user_id"] == user_id
    ]
    if not pending:
        return None
    pending.sort(key=lambda item: item["expires_at"], reverse=True)
    return pending[0]


def _consume_sql_confirmation(confirmation_id: str):
    return text2sql_module._PENDING_CONFIRMATIONS.pop(confirmation_id, None)


def _cleanup_file_confirmations():
    now = datetime.utcnow()
    expired_ids = [
        confirmation_id
        for confirmation_id, record in _PENDING_FILE_CONFIRMATIONS.items()
        if record["expires_at"] <= now
    ]
    for confirmation_id in expired_ids:
        _PENDING_FILE_CONFIRMATIONS.pop(confirmation_id, None)


def _create_file_confirmation(user_id: int, payload: dict):
    _cleanup_file_confirmations()
    confirmation_id = str(uuid4())
    _PENDING_FILE_CONFIRMATIONS[confirmation_id] = {
        "user_id": user_id,
        "payload": payload,
        "expires_at": datetime.utcnow() + timedelta(seconds=_AGENT_CONFIRMATION_TTL_SECONDS),
    }
    return confirmation_id


def _consume_file_confirmation(confirmation_id: str):
    return _PENDING_FILE_CONFIRMATIONS.pop(confirmation_id, None)


def _get_latest_pending_file_confirmation(user_id: int):
    _cleanup_file_confirmations()
    pending = [
        {
            "confirmation_id": confirmation_id,
            **record,
        }
        for confirmation_id, record in _PENDING_FILE_CONFIRMATIONS.items()
        if record["user_id"] == user_id
    ]
    if not pending:
        return None
    pending.sort(key=lambda item: item["expires_at"], reverse=True)
    return pending[0]


def get_file_workspace(user_id: str) -> str:
    return str(_USER_FILE_WORKSPACES.get(str(user_id), _DEFAULT_WORKSPACE_ROOT))


def set_file_workspace(user_id: str, workspace_path: str) -> dict:
    if not isinstance(workspace_path, str) or not workspace_path.strip():
        raise ValueError("workspace 路径不能为空")
    if "\x00" in workspace_path:
        raise ValueError("workspace 路径包含非法字符")

    path = Path(workspace_path).expanduser().resolve()
    if not path.exists():
        raise ValueError("workspace 路径不存在")
    if not path.is_dir():
        raise ValueError("workspace 必须是目录")

    _USER_FILE_WORKSPACES[str(user_id)] = path
    return {
        "success": True,
        "workspace_root": str(path),
        "message": "文件工具 workspace 已更新",
    }


def _workspace_from_payload(payload: dict) -> Path:
    workspace_root = payload.get("_workspace_root")
    if workspace_root:
        path = Path(workspace_root).resolve()
        if not path.exists() or not path.is_dir():
            raise ValueError("待确认操作对应的 workspace 已不存在")
        return path
    return _DEFAULT_WORKSPACE_ROOT


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _resolve_workspace_path(relative_path: str, workspace_root: Path) -> Path:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("文件路径不能为空")
    if "\x00" in relative_path:
        raise ValueError("文件路径包含非法字符")

    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise ValueError("只允许使用项目内相对路径")

    target = (workspace_root / candidate).resolve()
    if target != workspace_root and workspace_root not in target.parents:
        raise ValueError("文件路径超出当前 workspace")
    return target


def _validate_file_path(path: Path, workspace_root: Path, require_existing: bool = True, require_text_suffix: bool = True):
    relative_parts = path.relative_to(workspace_root).parts
    if any(part in _FILE_TOOL_BLOCKED_PARTS for part in relative_parts):
        raise ValueError("该路径位于禁止访问的目录中")
    if path.name in _FILE_TOOL_BLOCKED_NAMES:
        raise ValueError("该文件禁止通过 agent 访问")
    if require_existing and not path.exists():
        raise ValueError("文件不存在")
    if path.exists() and not path.is_file():
        raise ValueError("只允许操作普通文件")
    if require_text_suffix and path.suffix.lower() not in _FILE_TOOL_ALLOWED_SUFFIXES:
        raise ValueError("该文件类型不在允许的文本文件白名单中")


def _read_text_file(path: Path, workspace_root: Path) -> str:
    _validate_file_path(path, workspace_root)
    size = path.stat().st_size
    if size > _FILE_TOOL_MAX_READ_BYTES:
        raise ValueError(f"文件过大，超过读取限制 { _FILE_TOOL_MAX_READ_BYTES } bytes")
    return path.read_text(encoding="utf-8")


def _normalize_file_tool_payload(action_payload):
    payload = action_payload
    if isinstance(action_payload, str):
        try:
            payload = json.loads(action_payload)
        except Exception as exc:
            raise ValueError("文件工具参数必须是 JSON 对象") from exc
    if not isinstance(payload, dict):
        raise ValueError("文件工具参数格式错误")
    return payload


def _apply_file_payload(payload: dict):
    operation = payload.get("operation")
    workspace_root = _workspace_from_payload(payload)
    path = _resolve_workspace_path(payload.get("path", ""), workspace_root)
    _validate_file_path(path, workspace_root, require_existing=operation != "propose_write")

    if operation == "propose_delete":
        if payload.get("base_hash") and payload["base_hash"] != _file_sha256(path):
            raise ValueError("文件已被其他操作修改，请重新生成删除方案")

        relative_path = path.relative_to(workspace_root)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        trash_path = workspace_root / ".agent-trash" / relative_path.parent / f"{relative_path.name}.{timestamp}.bak"
        trash_path.parent.mkdir(parents=True, exist_ok=True)
        path.replace(trash_path)
        return f"已将 {relative_path.as_posix()} 移动到 {trash_path.relative_to(workspace_root).as_posix()}"

    if operation == "propose_write":
        content = payload.get("content")
        if not isinstance(content, str):
            raise ValueError("propose_write 需要 content 字符串")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"已写入文件 {path.relative_to(workspace_root).as_posix()}"

    old_content = _read_text_file(path, workspace_root)

    if payload.get("base_hash") and payload["base_hash"] != _file_sha256(path):
        raise ValueError("文件已被其他操作修改，请重新生成修改方案")

    if operation == "propose_append":
        content = payload.get("content")
        if not isinstance(content, str):
            raise ValueError("propose_append 需要 content 字符串")
        separator = "" if not old_content or old_content.endswith("\n") else "\n"
        path.write_text(old_content + separator + content, encoding="utf-8")
        return f"已追加内容到 {path.relative_to(workspace_root).as_posix()}"

    if operation == "propose_replace":
        old_text = payload.get("old_text")
        new_text = payload.get("new_text")
        if not isinstance(old_text, str) or not isinstance(new_text, str):
            raise ValueError("propose_replace 需要 old_text 和 new_text 字符串")
        if old_text not in old_content:
            raise ValueError("未找到要替换的原文，文件可能已变化")
        path.write_text(old_content.replace(old_text, new_text, 1), encoding="utf-8")
        return f"已替换 {path.relative_to(workspace_root).as_posix()} 中的内容"

    raise ValueError(f"不支持的文件写操作: {operation}")


def file_agent_tool(action_payload, user_id: str):
    """
    Agent 文件工具：只允许访问项目 workspace 内的白名单文本文件。

    支持 operation:
    - list_files: {"operation": "list_files", "path": ".", "limit": 80}
    - read_file: {"operation": "read_file", "path": "README.md"}
    - propose_write: {"operation": "propose_write", "path": "README.md", "content": "..."}
    - propose_append: {"operation": "propose_append", "path": "README.md", "content": "..."}
    - propose_replace: {"operation": "propose_replace", "path": "README.md", "old_text": "...", "new_text": "..."}
    - propose_delete: {"operation": "propose_delete", "path": "docs/old.md"}
    """
    try:
        payload = _normalize_file_tool_payload(action_payload)
        operation = payload.get("operation")
        workspace_root = Path(get_file_workspace(user_id)).resolve()

        if operation == "list_files":
            root = _resolve_workspace_path(payload.get("path", "."), workspace_root)
            if not root.exists() or not root.is_dir():
                raise ValueError("list_files 的 path 必须是已存在目录")
            if any(part in _FILE_TOOL_BLOCKED_PARTS for part in root.relative_to(workspace_root).parts):
                raise ValueError("该目录禁止访问")

            limit = min(int(payload.get("limit", 80)), 200)
            files = []
            for item in root.rglob("*"):
                relative = item.relative_to(workspace_root)
                if any(part in _FILE_TOOL_BLOCKED_PARTS for part in relative.parts):
                    continue
                if item.is_file() and item.name not in _FILE_TOOL_BLOCKED_NAMES:
                    files.append(relative.as_posix())
                if len(files) >= limit:
                    break
            return {
                "success": True,
                "operation": operation,
                "workspace_root": str(workspace_root),
                "files": files,
            }

        if operation == "read_file":
            path = _resolve_workspace_path(payload.get("path", ""), workspace_root)
            content = _read_text_file(path, workspace_root)
            return {
                "success": True,
                "operation": operation,
                "workspace_root": str(workspace_root),
                "path": path.relative_to(workspace_root).as_posix(),
                "content": content,
                "sha256": _file_sha256(path),
            }

        if operation in {"propose_write", "propose_append", "propose_replace", "propose_delete"}:
            path = _resolve_workspace_path(payload.get("path", ""), workspace_root)
            _validate_file_path(path, workspace_root, require_existing=operation != "propose_write")

            if operation == "propose_write":
                content = payload.get("content", "")
                if not isinstance(content, str):
                    raise ValueError("propose_write 需要 content 字符串")
                base_hash = _file_sha256(path) if path.exists() else None
                preview = content[:1000]
            elif operation == "propose_append":
                content = payload.get("content", "")
                if not isinstance(content, str):
                    raise ValueError("propose_append 需要 content 字符串")
                base_hash = _file_sha256(path)
                preview = content[:1000]
            elif operation == "propose_replace":
                old_text = payload.get("old_text", "")
                new_text = payload.get("new_text", "")
                if not isinstance(old_text, str) or not isinstance(new_text, str):
                    raise ValueError("propose_replace 需要 old_text 和 new_text 字符串")
                if old_text not in _read_text_file(path, workspace_root):
                    raise ValueError("未找到要替换的原文")
                base_hash = _file_sha256(path)
                preview = f"Replace:\n{old_text[:500]}\n\nWith:\n{new_text[:500]}"
            else:
                base_hash = _file_sha256(path)
                preview = f"Delete file: {path.relative_to(workspace_root).as_posix()}"

            serialized_size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            if serialized_size > _FILE_TOOL_MAX_WRITE_BYTES:
                raise ValueError(f"修改内容过大，超过写入限制 { _FILE_TOOL_MAX_WRITE_BYTES } bytes")

            pending_payload = {
                **payload,
                "base_hash": base_hash,
                "path": path.relative_to(workspace_root).as_posix(),
                "_workspace_root": str(workspace_root),
            }
            confirmation_id = _create_file_confirmation(int(user_id), pending_payload)
            return {
                "success": True,
                "message": "文件修改需要用户确认",
                "requires_confirmation": True,
                "confirmation_id": confirmation_id,
                "operation": operation,
                "workspace_root": str(workspace_root),
                "path": pending_payload["path"],
                "preview": preview,
            }

        return {
            "success": False,
            "message": f"不支持的文件工具操作: {operation}",
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"文件工具执行失败: {str(e)}",
        }


def _is_confirm_intent(query: str) -> bool:
    normalized = query.strip().lower()
    phrases = [
        "确认", "确认发送", "同意发送", "批准发送", "发送吧", "可以发送",
        "yes", "confirm", "approve", "send it"
    ]
    return any(phrase in normalized for phrase in phrases)


def _is_reject_intent(query: str) -> bool:
    normalized = query.strip().lower()
    phrases = [
        "取消", "不要发送", "拒绝", "先别发", "不发送",
        "cancel", "reject", "do not send", "don't send"
    ]
    return any(phrase in normalized for phrase in phrases)


def _build_approval_from_result(action_name: str, prompt, result: dict):
    if not isinstance(result, dict) or not result.get("requires_confirmation"):
        return None

    confirmation_id = result.get("confirmation_id")
    if not confirmation_id:
        return None

    if action_name == "邮件发送工具":
        to_addresses = result.get("to_addresses") or []
        subject = result.get("subject") or "(无主题)"
        description = f'即将向 {", ".join(to_addresses) if to_addresses else "指定收件人"} 发送主题为“{subject}”的邮件。'
        return {
            "id": confirmation_id,
            "title": "确认发送邮件",
            "description": description,
            "target": "mail_send",
            "riskLevel": "high",
            "state": "pending",
        }

    if action_name == "SQL工具":
        operation = ""
        if isinstance(prompt, dict):
            operation = prompt.get("operation", "")
        description = f"即将执行数据库写操作：{operation or 'schedule 修改'}。"
        return {
            "id": confirmation_id,
            "title": "确认关键操作",
            "description": description,
            "target": "sql_write",
            "riskLevel": "high",
            "state": "pending",
        }

    if action_name == "文件工具":
        operation = result.get("operation", "")
        path = result.get("path", "")
        description = f"即将执行文件操作：{operation}，目标文件：{path}。"
        return {
            "id": confirmation_id,
            "title": "确认修改本地文件",
            "description": description,
            "target": "file_write",
            "riskLevel": "high",
            "state": "pending",
        }

    return None


def resolve_agent_approval(action_id: str, approved: bool, user_id: str):
    mail_record = _PENDING_MAIL_CONFIRMATIONS.get(action_id)
    if mail_record and mail_record.get("user_id") == int(user_id):
        if not approved:
            _consume_mail_confirmation(action_id)
            return {
                "success": True,
                "action_id": action_id,
                "state": "rejected",
                "message": "已取消待发送邮件，本次不会执行发送。",
                "target": "mail_send",
            }

        payload = {
            **mail_record["payload"],
            "confirm": True,
            "confirmation_id": action_id,
        }
        result = mail_agent_tool(payload, user_id)
        return {
            "success": bool(result.get("success")),
            "action_id": action_id,
            "state": "approved" if result.get("success") else "pending",
            "message": result["message"] if not result.get("success") else f'已发送邮件，主题为“{result.get("subject", "")}”。',
            "target": "mail_send",
            "result": result,
        }

    sql_record = text2sql_module._PENDING_CONFIRMATIONS.get(action_id)
    if sql_record and sql_record.get("user_id") == int(user_id):
        if not approved:
            _consume_sql_confirmation(action_id)
            return {
                "success": True,
                "action_id": action_id,
                "state": "rejected",
                "message": "已取消待执行的关键操作，本次不会修改数据。",
                "target": "sql_write",
            }

        payload = {
            "operation": sql_record["operation"],
            "filters": sql_record["filters"],
            "data": sql_record["data"],
            "confirm": True,
            "confirmation_id": action_id,
        }
        result = sql_agent_tool(payload, user_id)
        return {
            "success": bool(result.get("success")),
            "action_id": action_id,
            "state": "approved" if result.get("success") else "pending",
            "message": result["message"] if not result.get("success") else "已根据你的确认执行关键操作。",
            "target": "sql_write",
            "result": result,
        }

    file_record = _PENDING_FILE_CONFIRMATIONS.get(action_id)
    if file_record and file_record.get("user_id") == int(user_id):
        if not approved:
            _consume_file_confirmation(action_id)
            return {
                "success": True,
                "action_id": action_id,
                "state": "rejected",
                "message": "已取消待执行的文件修改，本次不会改动本地文件。",
                "target": "file_write",
            }

        record = _consume_file_confirmation(action_id)
        try:
            message = _apply_file_payload(record["payload"])
            return {
                "success": True,
                "action_id": action_id,
                "state": "approved",
                "message": message,
                "target": "file_write",
            }
        except Exception as e:
            return {
                "success": False,
                "action_id": action_id,
                "state": "pending",
                "message": f"文件修改失败: {str(e)}",
                "target": "file_write",
            }

    return {
        "success": False,
        "action_id": action_id,
        "state": "pending",
        "message": "未找到对应的待确认操作，可能已过期或已处理。",
        "target": "unknown",
    }


def sql_agent_tool(action_payload, user_id: str):
    """
    Agent SQL工具：仅允许查询当前用户的entities数据，并在执行schedule增删改前要求确认。

    action_payload 期望格式（dict 或 JSON 字符串）：
    {
      "operation": "schema|select_entities|create_schedule|update_schedule|delete_schedule",
      "filters": {...},
      "data": {...},
      "limit": 20,
      "confirm": false,
      "confirmation_id": null
    }
    """
    payload = action_payload
    if isinstance(action_payload, str):
        stripped_payload = action_payload.strip()
        if stripped_payload.startswith("{"):
            try:
                payload = json.loads(stripped_payload)
            except Exception:
                return {
                    "success": False,
                    "message": "SQL工具参数中的 JSON 字符串无法解析",
                }
        else:
            try:
                payload = _generate_text2sql_request_from_query(stripped_payload, user_id)
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Text2SQL 生成失败: {str(e)}",
                }

    if not isinstance(payload, dict):
        return {
            "success": False,
            "message": "SQL工具参数格式错误",
        }

    db = get_db_sync()
    try:
        req = Text2SQLRequest(**payload)
        result = execute_text2sql_tool(db=db, user_id=int(user_id), request=req)
        response = result.model_dump()
        response["generated_request"] = req.model_dump()
        return response
    except Exception as e:
        return {
            "success": False,
            "message": f"SQL工具执行失败: {str(e)}",
        }
    finally:
        db.close()


def mail_agent_tool(action_payload, user_id: str):
    """
    Agent 邮件发送工具：使用当前已登录邮箱直接发送邮件。

    action_payload 期望格式（dict 或 JSON 字符串）：
    {
      "to_addresses": ["xx@example.com"],
      "cc_addresses": [],
      "bcc_addresses": [],
      "subject": "邮件主题",
      "body": "纯文本正文",
      "html_body": null,
      "confirm": false,
      "confirmation_id": null
    }
    """
    payload = action_payload
    if isinstance(action_payload, str):
        try:
            payload = json.loads(action_payload)
        except Exception:
            return {
                "success": False,
                "message": "邮件工具参数必须是JSON对象或可解析JSON字符串",
            }

    if not isinstance(payload, dict):
        return {
            "success": False,
            "message": "邮件工具参数格式错误",
        }

    normalized_payload = {
        "to_addresses": payload.get("to_addresses", []),
        "cc_addresses": payload.get("cc_addresses", []),
        "bcc_addresses": payload.get("bcc_addresses", []),
        "subject": payload.get("subject", ""),
        "body": payload.get("body"),
        "html_body": payload.get("html_body"),
    }
    confirm = bool(payload.get("confirm", False))
    confirmation_id = payload.get("confirmation_id")

    try:
        if not confirm:
            new_confirmation_id = _create_mail_confirmation(int(user_id), normalized_payload)
            return {
                "success": True,
                "message": "邮件发送需要用户确认",
                "requires_confirmation": True,
                "confirmation_id": new_confirmation_id,
                **normalized_payload,
            }

        if not confirmation_id:
            return {
                "success": False,
                "message": "邮件发送缺少 confirmation_id，无法执行确认发送",
            }

        _validate_mail_confirmation(int(user_id), normalized_payload, confirmation_id)
        result = send_mail_service(
            user_id=int(user_id),
            to_addresses=normalized_payload["to_addresses"],
            cc_addresses=normalized_payload["cc_addresses"],
            bcc_addresses=normalized_payload["bcc_addresses"],
            subject=normalized_payload["subject"],
            body=normalized_payload["body"],
            html_body=normalized_payload["html_body"],
        )
        return {
            "success": True,
            "message": "邮件发送成功",
            **result,
        }
    except Exception as e:
        detail = getattr(e, "detail", None)
        return {
            "success": False,
            "message": f"邮件发送失败: {detail or str(e)}",
        }

#规划模块plan
def agent_plan(query):
    prompt='''
    # 南科大智能助手Agent的Plan模块

你是一个专业的南方科技大学（南科大）智能助手的规划模块。你的任务是：
1. 分析用户的查询:{0}
2. 基于已有的信息，决定使用哪个工具来查询或执行任务（本地文档搜索、网络搜索、SQL工具、邮件发送工具、文件工具）
3. 将用户的原始查询拆解或延伸为1-2个相关问题，以获取更全面的信息


## 可用工具
1. **本地文档搜索**：搜索南科大相关本地资料，可能包含：
     - 学校概况与院系介绍
     - 本科生/研究生培养方案
     - 课程与选课规则
     - 校历与考试安排
     - 教务流程与办事指南
     - 奖助学金与资助政策
     - 住宿、校园生活与后勤服务
     - 国际交流与科研项目
     - 常见问题与联系方式

2. **网络搜索**：在互联网上搜索相关信息

3. **SQL工具**：访问数据库中的个人信息（严格按当前user_id权限）
    - 只读查询：entities 相关表（users/credits/deadlines/schedules/user_schedule_association）
    - 日程管理：可对 schedules 做增删改，但必须先返回 requires_confirmation 和 confirmation_id，再由用户明确确认后执行

4. **邮件发送工具**：使用当前已登录的邮箱账号发送邮件
    - 仅当用户明确表达“发送邮件/发邮件/回复邮件”等执行意图时使用
    - 需要尽量从用户原始请求中提取收件人、主题、正文
    - 如果用户没有明确要求发送，而只是让你润色邮件内容、拟邮件草稿，则不要调用该工具
    - 邮件发送属于高风险动作，首次规划时必须设置 confirm=false，由系统进入待确认状态；只有在用户后续明确确认后，才可设置 confirm=true 并附上 confirmation_id

5. **文件工具**：读取或修改项目工作区内的文本文件
    - 读取文件：使用 {{"operation":"read_file","path":"README.md"}}
    - 列出文件：使用 {{"operation":"list_files","path":".","limit":80}}
    - 追加内容：使用 {{"operation":"propose_append","path":"README.md","content":"要追加的内容"}}
    - 覆盖写入：使用 {{"operation":"propose_write","path":"README.md","content":"完整新文件内容"}}
    - 替换片段：使用 {{"operation":"propose_replace","path":"README.md","old_text":"原文","new_text":"新文"}}
    - 删除文件：使用 {{"operation":"propose_delete","path":"docs/old.md"}}
    - 文件修改和删除属于高风险动作，系统会要求用户确认后才会真正执行

## 工具选择规则
- 当查询明确涉及南科大校内制度、课程、校历、办事流程等信息时，优先使用**本地文档搜索**
- 当查询涉及用户个人课表/日程/学分/DDL等个人数据库信息时，使用**SQL工具**
- 当查询明确要求发送邮件、回复邮件、代发邮件，并且请求中已经提供足够的收件人/主题/正文信息时，使用**邮件发送工具**
- 当查询明确要求读取、总结、检查或修改项目文件（如 README.md、报告、代码文件）时，使用**文件工具**
- 当查询涉及以下情况时，使用**网络搜索**：
    - 最新新闻、公告、社会动态
    - 与其他高校的横向对比
    - 本地资料未覆盖的信息
    - 需要实时更新的数据（如最新政策、竞赛通知等）

## prompt延伸的规则
- 本地检索的查询扩展侧重于校内信息的准确补全
- 网络检索的查询扩展侧重于本地无法检索到的信息

## 输出格式
你的输出应该是一个JSON格式的列表，每个项目包含：
1. `action_name`：工具名称（"本地文档搜索"或"网络搜索"或"SQL工具"或"邮件发送工具"或"文件工具"）
2. `prompts`：
    - 对本地文档搜索/网络搜索：问题列表，第一个是原始查询，后面是拆解或延伸的问题
    - 对SQL工具：每个元素直接写成要执行的自然语言子任务，不要自己拼 JSON，交给 SQL工具内部的 schema-aware text2sql 模块处理
    - 对邮件发送工具：每个元素必须是一个JSON对象，字段为 to_addresses/cc_addresses/bcc_addresses/subject/body/html_body/confirm/confirmation_id
    - 对文件工具：每个元素必须是一个JSON对象，字段至少包含 operation；读文件用 read_file，修改文件用 propose_append/propose_write/propose_replace，删除文件用 propose_delete
[
  {{
    "action_name": "工具名称",
    "prompts": [
      "原始查询",
      "拆解/延伸问题1",
      "拆解/延伸问题2",
      "拆解/延伸问题3"
    ]
  }}
]


## 示例

### 示例1：关于课程信息的查询
用户：南科大这学期选课时间是什么时候？

输出：
[
  {{
    "action_name": "本地文档搜索",
    "prompts": [
            "南科大这学期选课时间是什么时候？",
            "南科大选课系统开放和关闭的具体时间是？",
            "南科大退补选阶段的时间安排是什么？"
    ]
  }}
]


### 示例2：关于高校对比的查询
用户：南科大和上科大在人工智能方向培养有什么区别？

输出：
[
  {{
    "action_name": "本地文档搜索",
    "prompts": [
            "南科大人工智能相关专业的培养特色是什么？",
            "南科大人工智能方向课程和科研资源有哪些？"
    ]
  }},
  {{
    "action_name": "网络搜索",
    "prompts": [
            "上科大人工智能方向培养特色",
            "南科大与上科大人工智能培养对比",
            "上科大人工智能课程与科研资源"
    ]
  }}
]


### 示例3：关于日常问题
用户：你好
这种情况下都不需要调用，则输出为None

### 示例4：关于个人日程（SQL工具）
用户：帮我看看我这周的课程安排
输出：
[
    {{
        "action_name": "SQL工具",
        "prompts": [
            "帮我查询当前用户这周的课程安排"
        ]
    }}
]

### 示例5：关于修改日程（SQL工具）
用户：把我周三下午的软件工程课地点改成理学院302
输出：
[
  {{
    "action_name": "SQL工具",
    "prompts": [
      "把当前用户周三下午的软件工程课地点改成理学院302"
    ]
  }}
]

### 示例5：发送邮件
用户：帮我发邮件给 teacher@sustech.edu.cn，主题是请假申请，正文是老师您好，我因为发烧今天无法到课，想请假一天，谢谢。
输出：
[
  {{
    "action_name": "邮件发送工具",
    "prompts": [
      {{
        "to_addresses": ["teacher@sustech.edu.cn"],
        "cc_addresses": [],
        "bcc_addresses": [],
        "subject": "请假申请",
        "body": "老师您好，我因为发烧今天无法到课，想请假一天，谢谢。",
        "html_body": null,
        "confirm": false,
        "confirmation_id": null
      }}
    ]
  }}
]

### 示例6：读取项目文件
用户：读取 README.md 并总结内容
输出：
[
  {{
    "action_name": "文件工具",
    "prompts": [
      {{
        "operation": "read_file",
        "path": "README.md"
      }}
    ]
  }}
]

### 示例7：追加项目文件内容
用户：在 README.md 末尾追加一行“CI/CD is configured with GitHub Actions.”
输出：
[
  {{
    "action_name": "文件工具",
    "prompts": [
      {{
        "operation": "propose_append",
        "path": "README.md",
        "content": "CI/CD is configured with GitHub Actions."
      }}
    ]
  }}
]

### 示例8：删除项目文件
用户：删除 docs/old.md
输出：
[
  {{
    "action_name": "文件工具",
    "prompts": [
      {{
        "operation": "propose_delete",
        "path": "docs/old.md"
      }}
    ]
  }}
]

只需要输出JSON的部分，前后不要输出任何信息

'''.format(query)
    result=(middle_json_model(prompt))
    print(result)
    json_list=extract_json_content(result)
    try:
        structure_output=json.loads(json_list)
    except:
        structure_output = None

    return structure_output
        
    

#任务状态state
def adjust_format(original_data):
    """
    调整数据格式，使每个action_name只搭配一个prompt
    
    参数:
    original_data (list): 原始数据，每个action_name对应多个prompts
    
    返回:
    list: 调整后的数据，每个action_name只对应一个prompt
    """
    adjusted_data = []
    
    for item in original_data:
        action_name = item['action_name']
        prompts = item['prompts']
        
        # 为每个prompt创建一个新的字典
        for prompt in prompts:
            adjusted_item = {
                'action_name': action_name,
                'prompt': prompt
            }
            adjusted_data.append(adjusted_item)
    
    return adjusted_data


def normalize_actions(planned_actions):
    """
    将 planner / reflection 的输出统一转换为 process_actions 可执行的格式：
    [{"action_name": "...", "prompt": "..."}]
    """
    if not planned_actions:
        return []

    normalized_actions = []
    for item in planned_actions:
        action_name = item.get("action_name")
        if not action_name:
            continue

        prompts = item.get("prompts")
        if prompts is None:
            prompt = item.get("prompt")
            if prompt:
                normalized_actions.append({
                    "action_name": action_name,
                    "prompt": prompt,
                })
            continue

        if isinstance(prompts, list):
            for prompt in prompts:
                normalized_actions.append({
                    "action_name": action_name,
                    "prompt": prompt,
                })
        else:
            normalized_actions.append({
                "action_name": action_name,
                "prompt": prompts,
            })

    return normalized_actions


def reflection(user_query,memory_global):
    prompt='''
    你是一个专业的南方科技大学（南科大）智能助手规划模块。你的任务是：
1. 分析用户的查询:{0}
2. 基于已有的信息，是否还需要延伸再进行查询

##目前已有的信息:
{1}


## 可用工具
1. **本地文档搜索**：搜索南科大相关本地资料（课程、校历、教务、办事流程、校园服务等）

2. **网络搜索**：在互联网上搜索相关信息

3. **SQL工具**：访问当前用户个人数据库信息，处理个人日程查询或日程增删改（写操作需确认）

注意：不要在反思阶段调用邮件发送工具，也不要在反思阶段调用任何需要确认的关键写操作，避免重复执行或重复创建待确认项。
注意：反思阶段也不要再构造 SQL JSON，若需要 SQL工具，只输出简单自然语言子任务。

## 工具选择规则
- 当查询明确涉及南科大校内信息时，优先使用**本地文档搜索**
- 当查询明确涉及当前用户个人课表/DDL/学分/日程安排时，优先使用**SQL工具**
- 当查询涉及以下情况时，使用**网络搜索**：
    - 与其他高校或机构的对比
    - 最新新闻公告或公开资讯
    - 本地资料未覆盖的信息
    - 需要实时数据

## prompt延伸的规则
- 本地检索的查询扩展侧重于校内信息的精确补全
- 网络检索的查询扩展侧重于本地无法检索到的信息

###重要！
至多再扩展不超过3个查询，如果需要扩展则按照下面的输出格式输出，如果不需要则返回None




## 输出格式
你的输出应该是一个JSON格式的列表，每个项目包含：
1. `action_name`：工具名称（"本地文档搜索"或"网络搜索"）
2. `prompts`：一个扩展的问题，如果是网络检索，prompt应避免依赖校内私有术语；如果是本地检索，prompt应聚焦南科大校内问题，检索内容一定是一个简单问题，不包含对比
[
  {{
    "action_name": "工具名称",
    "prompts":'查询内容'
  }}
  ...
]

    '''.format(user_query,memory_global)
    result=(middle_json_model(prompt))
    # print(result)
    json_list=extract_json_content(result)
    try:
        structure_output=json.loads(json_list)
    except:
        structure_output = None

    return structure_output
        
    

def deduplicate_memory_global(memory):
    """
    对最终的memory进行全局去重，根据所有结果中的content_with_weight字段去重
    
    Args:
        memory: 记忆列表，每个元素包含"提问"和"结果"字段
        
    Returns:
        deduplicated_memory: 去重后的记忆列表
    """
    if not isinstance(memory, list):
        return memory
    
    # 用于跟踪已见过的content_with_weight
    seen_content = set()
    deduplicated_memory = []
    
    for memory_item in memory:
        if not isinstance(memory_item, dict) or '结果' not in memory_item:
            # 如果不是预期的结构，直接添加
            deduplicated_memory.append(memory_item)
            continue
            
        result = memory_item['结果']
        
        # 如果结果是列表，需要检查每个元素的content_with_weight
        if isinstance(result, list):
            deduplicated_result = []
            for item in result:
                if isinstance(item, dict) and 'content_with_weight' in item:
                    content = item['content_with_weight'].strip()  # 去除首尾空格
                    content_hash = hash(content)  # 使用hash来比较，避免长字符串比较问题
                    
                    if content_hash not in seen_content:
                        seen_content.add(content_hash)
                        deduplicated_result.append(item)
                    else:
                        # 如果已见过，打印调试信息
                        print(f"发现重复内容，已过滤: id={item.get('id', 'unknown')}, 内容前50字符: {content[:50]}")
                else:
                    # 如果没有content_with_weight字段，直接添加
                    deduplicated_result.append(item)
            
            # 创建新的memory_item，使用去重后的结果
            new_memory_item = {
                "提问": memory_item['提问'],
                "结果": deduplicated_result
            }
            deduplicated_memory.append(new_memory_item)
        else:
            # 如果结果不是列表，直接添加
            deduplicated_memory.append(memory_item)
    
    return deduplicated_memory


#执行模块tools,依次执行actions内的动作，根据action_name判断执行函数web_search_answer()，还是rag()
def process_actions(actions, user_id: str):
    """
    处理动作列表函数
    
    Args:
        actions: 动作列表，每个动作包含action_name和prompt
        
    Returns:
        memory: 包含每次调用结果的记忆列表
    """
    memory = []
    approvals = []
    
    # 依次处理每个动作
    for action in actions:
        action_name = action['action_name']
        prompt = action['prompt']
        
        print(f'正在执行{action_name}: "{prompt}"')
        
        try:
            # 根据动作类型调用相应的函数
            if action_name == '本地文档搜索':
                result = rag(prompt, user_id)
            elif action_name == '网络搜索':
                result = web_search_answer(prompt)
            elif action_name == 'SQL工具':
                result = sql_agent_tool(prompt, user_id)
            elif action_name == '邮件发送工具':
                result = mail_agent_tool(prompt, user_id)
            elif action_name == '文件工具':
                result = file_agent_tool(prompt, user_id)
            else:
                result = f"未知的动作类型: {action_name}"

            approval = _build_approval_from_result(action_name, prompt, result)
            if approval:
                approvals.append(approval)
            
            # 将结果添加到记忆中
            memory_item = {
                "提问": prompt,
                "结果": result
            }
            memory.append(memory_item)
            
            # 输出结果
            print(f"提问：{prompt}")
            print(f"结果：{result}")
            print("-------------------")
            
        except Exception as e:
            # 如果执行失败，打印详细错误信息，继续下一轮循环
            print(f"--------{action_name}检索失败，错误详情: {str(e)}-----------")
            import traceback
            print(f"完整错误堆栈: {traceback.format_exc()}")
            continue
    
    print("所有执行动作已完成，结果已添加到memory中。")
    
    # 对最终的memory进行全局去重
    # 统计去重前的总结果数量
    total_before = sum(len(item['结果']) if isinstance(item['结果'], list) else 1 for item in memory)
    
    deduplicated_memory = deduplicate_memory_global(memory)
    
    # 统计去重后的总结果数量
    total_after = sum(len(item['结果']) if isinstance(item['结果'], list) else 1 for item in deduplicated_memory)
    
    print(f"去重前memory数量: {len(memory)}, 去重后memory数量: {len(deduplicated_memory)}")
    print(f"去重前总结果数量: {total_before}, 去重后总结果数量: {total_after}, 过滤了 {total_before - total_after} 个重复项")
    
    return deduplicated_memory, approvals


# 初始化OpenAI客户端
def final_answer(user_query: str, user_id: str):
    answer_model = os.getenv("AGENT_ANSWER_MODEL", "deepseek-reasoner")
    client = _build_llm_client(answer_model)

    pending_mail_confirmation = _get_latest_pending_mail_confirmation(int(user_id))
    pending_sql_confirmation = _get_latest_pending_sql_confirmation(int(user_id))
    pending_file_confirmation = _get_latest_pending_file_confirmation(int(user_id))
    if pending_mail_confirmation and _is_confirm_intent(user_query):
        payload = {
            **pending_mail_confirmation["payload"],
            "confirm": True,
            "confirmation_id": pending_mail_confirmation["confirmation_id"],
        }
        result = mail_agent_tool(payload, user_id)
        message = {
            "role": "assistant",
            "content": result["message"] if not result.get("success") else (
                f'已根据你的确认发送邮件，主题为“{result.get("subject", "")}”。'
            ),
            "thinking": False,
        }
        json_message = json.dumps(message)
        yield f"event: message\ndata: {json_message}\n\n"
        yield "event: end\ndata: [DONE]\n\n"
        return

    if pending_mail_confirmation and _is_reject_intent(user_query):
        _consume_mail_confirmation(pending_mail_confirmation["confirmation_id"])
        message = {
            "role": "assistant",
            "content": "已取消待发送邮件，本次不会执行发送。",
            "thinking": False,
        }
        json_message = json.dumps(message)
        yield f"event: message\ndata: {json_message}\n\n"
        yield "event: end\ndata: [DONE]\n\n"
        return

    if pending_sql_confirmation and _is_confirm_intent(user_query):
        payload = {
            "operation": pending_sql_confirmation["operation"],
            "filters": pending_sql_confirmation["filters"],
            "data": pending_sql_confirmation["data"],
            "confirm": True,
            "confirmation_id": pending_sql_confirmation["confirmation_id"],
        }
        result = sql_agent_tool(payload, user_id)
        message = {
            "role": "assistant",
            "content": result["message"] if not result.get("success") else "已根据你的确认执行关键操作。",
            "thinking": False,
        }
        json_message = json.dumps(message)
        yield f"event: message\ndata: {json_message}\n\n"
        yield "event: end\ndata: [DONE]\n\n"
        return

    if pending_sql_confirmation and _is_reject_intent(user_query):
        _consume_sql_confirmation(pending_sql_confirmation["confirmation_id"])
        message = {
            "role": "assistant",
            "content": "已取消待执行的关键操作，本次不会修改数据。",
            "thinking": False,
        }
        json_message = json.dumps(message)
        yield f"event: message\ndata: {json_message}\n\n"
        yield "event: end\ndata: [DONE]\n\n"
        return

    if pending_file_confirmation and _is_confirm_intent(user_query):
        record = _consume_file_confirmation(pending_file_confirmation["confirmation_id"])
        try:
            content = _apply_file_payload(record["payload"])
        except Exception as e:
            content = f"文件修改失败: {str(e)}"
        message = {
            "role": "assistant",
            "content": content,
            "thinking": False,
        }
        json_message = json.dumps(message)
        yield f"event: message\ndata: {json_message}\n\n"
        yield "event: end\ndata: [DONE]\n\n"
        return

    if pending_file_confirmation and _is_reject_intent(user_query):
        _consume_file_confirmation(pending_file_confirmation["confirmation_id"])
        message = {
            "role": "assistant",
            "content": "已取消待执行的文件修改，本次不会改动本地文件。",
            "thinking": False,
        }
        json_message = json.dumps(message)
        yield f"event: message\ndata: {json_message}\n\n"
        yield "event: end\ndata: [DONE]\n\n"
        return

    action_tool=agent_plan(user_query)
    print("action_tool")
    print(action_tool)

    actions = normalize_actions(action_tool)

    for action in actions:
        action_name = action['action_name']
        prompt = action['prompt']
        message = {
            "role": "agent",
            "content": f'正在执行{action_name}: "{prompt}"'
        }

        json_message = json.dumps(message)
        yield f"event: message\ndata: {json_message}\n\n"

    memory_new, approvals = process_actions(actions, user_id)

    memory_global=[]
    memory_global.extend(memory_new)

    for approval in approvals:
        approval_message = {
            "approval": approval,
        }
        json_message = json.dumps(approval_message)
        yield f"event: message\ndata: {json_message}\n\n"

    # 已有待确认关键操作时，不再继续反思补查，避免引入无关查询或重复操作
    has_pending_approvals = any(approval.get("state") == "pending" for approval in approvals)

    # 反思模块
    action_reflect = None if has_pending_approvals else reflection(user_query, memory_global)
    if action_reflect:
        print("回顾内容，进行反思...")
        reflect_actions = normalize_actions(action_reflect)

        for action in reflect_actions:
            action_name = action['action_name']
            prompt = action['prompt']
            message = {
                "role": "agent",
                "content": f'正在执行反思后的{action_name}: "{prompt}"'
            }

            json_message = json.dumps(message)
            yield f"event: message\ndata: {json_message}\n\n"

        memory_new, reflect_approvals = process_actions(reflect_actions, user_id)
        memory_global.extend(memory_new)
        approvals.extend(reflect_approvals)

        for approval in reflect_approvals:
            approval_message = {
                "approval": approval,
            }
            json_message = json.dumps(approval_message)
            yield f"event: message\ndata: {json_message}\n\n"
        
    final_prompt=f'''
        你是南方科技大学（南科大）智能助手，负责根据用户问题和提供的参考内容生成回答。请严格按照以下要求生成回答：
        优先基于提供的参考内容回答；若参考内容不足，可明确说明后再结合通用知识补充
        回答风格应专业、清晰、友好，适合校园信息咨询场景
        如果涉及校历、政策、流程、联系方式等信息，请提醒用户以官方最新通知为准
        
        参考内容：
        {memory_global}
        
        用户问题：{user_query}
    
    '''

    print(final_prompt)    
    print('-'*130)
    
    # 创建聊天完成请求
    completion = client.chat.completions.create(
        model=answer_model,
        messages=[
            {"role": "user", "content": final_prompt}
        ],
        stream=True,
        # 解除以下注释会在最后一个chunk返回Token使用量
        # stream_options={
        #     "include_usage": True
        # }
    )
    
    print("\n" + "=" * 20 + "思考过程" + "=" * 20 + "\n")
    
    for chunk in completion:
        if chunk.choices[0].finish_reason == "stop":

            # 结束时发送 [DONE] 事件
            yield "event: end\ndata: [DONE]\n\n"
            break
        else:
            # 实时输出消息
            delta = chunk.choices[0].delta
            if delta.content:
                message = {
                    "role": "assistant",
                    "content": delta.content,
                    "thinking": False,
                }
                json_message = json.dumps(message)
                yield f"event: message\ndata: {json_message}\n\n"
            else :
                message = {
                    "role": "assistant",
                    "content": delta.reasoning_content,
                    "thinking": True,
                }
                json_message = json.dumps(message)
                yield f"event: message\ndata: {json_message}\n\n"
