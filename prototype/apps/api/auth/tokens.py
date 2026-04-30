"""极简 HMAC-SHA256 签名令牌（JWT-lite），无需外部依赖。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

_raw_secret = os.getenv("ZHICE_JWT_SECRET", "")
if not _raw_secret:
    import secrets as _s
    _raw_secret = _s.token_hex(32)
    import logging as _log
    _log.getLogger(__name__).warning(
        "ZHICE_JWT_SECRET 未设置，已自动生成临时密钥（重启后所有 token 失效）。"
        "生产环境请在 .env 中设置 ZHICE_JWT_SECRET=<64位随机字符串>"
    )
_SECRET = _raw_secret.encode("utf-8")
_TTL = int(os.getenv("ZHICE_JWT_TTL", str(60 * 60 * 24 * 7)))  # 7 天


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def create_token(payload: dict[str, Any], ttl: int | None = None) -> str:
    body = dict(payload)
    body["iat"] = int(time.time())
    body["exp"] = int(time.time()) + (ttl if ttl is not None else _TTL)
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload_enc = _b64url(json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signing_input = f"{header}.{payload_enc}".encode("ascii")
    sig = hmac.new(_SECRET, signing_input, hashlib.sha256).digest()
    return f"{header}.{payload_enc}.{_b64url(sig)}"


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        header, payload_enc, sig = token.split(".")
    except ValueError:
        return None
    signing_input = f"{header}.{payload_enc}".encode("ascii")
    expected = hmac.new(_SECRET, signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url(expected), sig):
        return None
    try:
        payload = json.loads(_b64url_decode(payload_enc))
    except Exception:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload
