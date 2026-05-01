from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from apps.api.db import execute, query_one
from .service import get_user
from .tokens import decode_token

# VIP 配额（每日）。-1 表示不限
QUOTA_LIMITS = {
    "free": {"ai_chat": 3, "ai_report": 1, "backtest": 2},
    "standard": {"ai_chat": 50, "ai_report": 10, "backtest": 20},
    "pro": {"ai_chat": -1, "ai_report": -1, "backtest": -1},
}


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()


def optional_user(authorization: Optional[str] = Header(None)) -> dict | None:
    token = _extract_token(authorization)
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    uid = payload.get("sub")
    if not uid:
        return None
    return get_user(int(uid))


def current_user(authorization: Optional[str] = Header(None)) -> dict:
    user = optional_user(authorization)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或令牌失效")
    return user


def require_vip(min_level: str = "standard"):
    order = {"free": 0, "standard": 1, "pro": 2}

    def _dep(user: dict = Depends(current_user)):
        if order.get(user["vip_level"], 0) < order.get(min_level, 0):
            raise HTTPException(status_code=403, detail="升级会员可解锁完整内容")
        return user

    return _dep


def consume_quota(feature: str):
    """依赖工厂：消耗用户某功能配额，超限抛 429。"""

    def _dep(user: dict = Depends(current_user)):
        limit = QUOTA_LIMITS.get(user["vip_level"], QUOTA_LIMITS["free"]).get(feature, 0)
        if limit == -1:
            return user
        today = datetime.now().strftime("%Y-%m-%d")
        row = query_one(
            "SELECT used FROM user_quota WHERE user_id=? AND quota_date=? AND feature=?",
            (user["id"], today, feature),
        )
        used = row["used"] if row else 0
        if used >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"今日 {feature} 已达上限({limit})，升级 VIP 获得更多配额",
            )
        if row:
            execute(
                "UPDATE user_quota SET used = used + 1 WHERE user_id=? AND quota_date=? AND feature=?",
                (user["id"], today, feature),
            )
        else:
            execute(
                "INSERT INTO user_quota(user_id, quota_date, feature, used) VALUES (?,?,?,1)",
                (user["id"], today, feature),
            )
        return user

    return _dep
