from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from passlib.context import CryptContext
import jwt
from . import config

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login')

def generate_jwt(data: dict, expires_delta: timedelta | None = None):
    """生成JWT令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=120)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, str(config.SECRET_KEY), config.JWT_ENCODE_ALGORITHM)
    return encoded_jwt

def generate_access_jwt(sid: str, expires_delta: timedelta | None = None):
    """
    :param sid: 学号
    :param expires_delta: token 有效期
    :return: JWT 字符串
    """
    return generate_jwt(data={"sub": sid}, expires_delta=expires_delta)

def extract_payloads(token: str):
    payload = jwt.decode(token, str(config.SECRET_KEY), algorithms=[config.JWT_ENCODE_ALGORITHM])
    return payload

def extract_sid(token: str) -> str | None:
    """
    Extract sid from a JWT.
    :param token: JWT.
    :return: username: extracted username.
    """
    try:
        payload = extract_payloads(token)
    except InvalidTokenError:
        return None
    return payload.get("sub")


def get_current_sid(token: str = Depends(oauth2_scheme)) -> str:
    """从 Bearer token 中提取当前用户 sid。"""
    sid = extract_sid(token)
    if sid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return sid


def get_current_user_id(sid: str = Depends(get_current_sid)) -> int:
    """将 sid 转为数据库 user_id（当前项目中两者一致）。"""
    try:
        return int(sid)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid sid in token") from exc