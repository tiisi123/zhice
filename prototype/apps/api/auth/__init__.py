"""用户认证与授权模块。"""
from fastapi import HTTPException

from .service import (
    register_user,
    authenticate,
    get_user,
    update_style,
    set_vip,
    hash_password,
    verify_password,
)
from .tokens import create_token, decode_token
from .deps import current_user, optional_user, require_vip, consume_quota


def require_admin(user: dict) -> None:
    """Raise 403 unless ``user`` carries the M001/S03 admin twin-field marker.

    The legacy admin gate is the pair (``vip_level == 'pro'`` AND
    ``phone == 'admin'``) which payment.py used inline at two call sites.
    Centralizing it here means new admin endpoints (T04 admin routes) and
    the existing payment-side admin endpoints share one authoritative check
    — there is exactly one place to revisit when the gate evolves (e.g. when
    we add a real ``role`` column).
    """
    if user.get("vip_level") != "pro" or user.get("phone") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")


__all__ = [
    "register_user",
    "authenticate",
    "get_user",
    "update_style",
    "set_vip",
    "hash_password",
    "verify_password",
    "create_token",
    "decode_token",
    "current_user",
    "optional_user",
    "require_vip",
    "require_admin",
    "consume_quota",
]
