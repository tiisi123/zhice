from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from apps.api.auth import (
    authenticate,
    create_token,
    current_user,
    register_user,
    update_style,
)
from apps.api.auth.deps import QUOTA_LIMITS

router = APIRouter()

# 登录限流：每 IP+phone 每 5 分钟最多 8 次失败
_LOGIN_FAILS: dict[str, deque[float]] = defaultdict(deque)
_LOGIN_LOCK = Lock()
_LOGIN_WINDOW = 300.0
_LOGIN_MAX = 8

# 注册限流：每 IP 每小时最多 5 次
_REG_HITS: dict[str, deque[float]] = defaultdict(deque)
_REG_WINDOW = 3600.0
_REG_MAX = 5

_PHONE_RE = re.compile(r"^[A-Za-z0-9_\-\.]{2,32}$")


def _check_rate(bucket: dict, key: str, window: float, limit: int) -> bool:
    now = time.time()
    with _LOGIN_LOCK:
        dq = bucket[key]
        while dq and now - dq[0] > window:
            dq.popleft()
        if len(dq) >= limit:
            return False
        return True


def _record(bucket: dict, key: str) -> None:
    with _LOGIN_LOCK:
        bucket[key].append(time.time())


class RegisterIn(BaseModel):
    phone: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=6, max_length=64)
    nickname: str = Field(default="", max_length=32)

    @field_validator("phone")
    @classmethod
    def _phone_fmt(cls, v: str) -> str:
        v = v.strip()
        if not _PHONE_RE.match(v):
            raise ValueError("账号仅支持字母/数字/下划线/连字符（2-32 位）")
        return v


class LoginIn(BaseModel):
    phone: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=1, max_length=64)


class StyleIn(BaseModel):
    style: str


@router.post("/register")
def register(inp: RegisterIn, request: Request):
    ip = request.client.host if request.client else "?"
    if not _check_rate(_REG_HITS, ip, _REG_WINDOW, _REG_MAX):
        raise HTTPException(status_code=429, detail="注册过于频繁，请稍后再试")
    _record(_REG_HITS, ip)
    try:
        user = register_user(inp.phone, inp.password, inp.nickname)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = create_token({"sub": str(user["id"]), "phone": user["phone"]})
    return {"user": user, "token": token}


@router.post("/login")
def login(inp: LoginIn, request: Request):
    ip = request.client.host if request.client else "?"
    key = f"{ip}|{inp.phone}"
    if not _check_rate(_LOGIN_FAILS, key, _LOGIN_WINDOW, _LOGIN_MAX):
        raise HTTPException(status_code=429, detail="登录尝试过多，请 5 分钟后再试")
    user = authenticate(inp.phone, inp.password)
    if not user:
        _record(_LOGIN_FAILS, key)
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    token = create_token({"sub": str(user["id"]), "phone": user["phone"]})
    return {"user": user, "token": token}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {"user": user, "quota": QUOTA_LIMITS.get(user["vip_level"], QUOTA_LIMITS["free"])}


@router.post("/style")
def set_style(inp: StyleIn, user: dict = Depends(current_user)):
    if inp.style not in {"short", "hot", "growth", "value"}:
        raise HTTPException(status_code=400, detail="未知风格")
    update_style(user["id"], inp.style)
    return {"ok": True, "style": inp.style}
