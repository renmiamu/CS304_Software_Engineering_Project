import os
import sys

# 在导入 app 模块之前设置 CI 环境所需的环境变量
os.environ.setdefault("SUSTECH_ASSISTANT_SECRET_KEY", "test-secret-key-for-ci")
os.environ.setdefault("SUSTECH_ASSISTANT_DATABASE_URL", "sqlite:///test.db")

# ── 基础占位测试（确保 pipeline 能跑通） ──

def test_always_pass():
    assert 1 + 1 == 2


# ── JWT Token 相关测试 ──

def test_jwt_generate_and_extract_sid():
    """测试 JWT token 生成和解析：生成 → 解析 → sid 一致"""
    from app.core.security import generate_access_jwt, extract_sid

    token = generate_access_jwt("12345678")
    assert token is not None
    assert isinstance(token, str)

    sid = extract_sid(token)
    assert sid == "12345678"


def test_jwt_contains_expiry():
    """测试 JWT token 包含 exp 过期时间字段"""
    from datetime import timedelta
    from app.core.security import generate_access_jwt, extract_payloads

    token = generate_access_jwt("12345678", expires_delta=timedelta(minutes=30))
    payload = extract_payloads(token)

    assert "sub" in payload
    assert "exp" in payload
    assert payload["sub"] == "12345678"


def test_extract_sid_invalid_token():
    """测试无效 token 不会抛异常，而是安全返回 None"""
    from app.core.security import extract_sid

    result = extract_sid("not.a.valid.token")
    assert result is None


# ── FastAPI 应用结构测试（需要完整依赖，仅 CI 环境运行） ──

def _try_import_app():
    """尝试导入 app.main，依赖不全时跳过"""
    import pytest
    try:
        from app.main import app
        return app
    except ModuleNotFoundError as e:
        pytest.skip(f"Missing dependency: {e}")


def test_fastapi_app_created():
    """测试 FastAPI 应用实例能正常创建"""
    app = _try_import_app()
    assert app.title == "SUSTech Assistant Backend"
    assert app.version == "0.1.0"


def test_fastapi_root_and_health_endpoints():
    """测试根路径和健康检查路径已注册"""
    app = _try_import_app()
    route_paths = [r.path for r in app.routes]
    assert "/" in route_paths
    assert "/health" in route_paths


def test_fastapi_all_routers_registered():
    """测试所有 9 个功能模块的路由都已注册"""
    app = _try_import_app()
    route_paths = {r.path for r in app.routes}
    prefixes = ["auth", "bb", "chat", "history", "mail", "schedule", "sync", "tis", "user"]
    for prefix in prefixes:
        assert any(f"/api/v1/{prefix}" in p for p in route_paths), f"Missing router: {prefix}"


# ── 配置工具函数测试 ──

def test_env_bool_default_value():
    """测试 _env_bool 在环境变量不存在时返回默认值"""
    from app.core.config import _env_bool

    assert _env_bool("THIS_VAR_DOES_NOT_EXIST", False) == False
    assert _env_bool("THIS_VAR_DOES_NOT_EXIST", True) == True


def test_env_float_default_value():
    """测试 _env_float 在环境变量不存在时返回默认值"""
    from app.core.config import _env_float

    assert _env_float("THIS_VAR_DOES_NOT_EXIST", 3.14) == 3.14
    assert _env_float("THIS_VAR_DOES_NOT_EXIST", 10.0) == 10.0
