from __future__ import annotations

from datetime import datetime, timedelta

from apps.api.db import execute, query_one, query_all
from apps.api.auth.password import hash_password, verify_password


def register_user(phone: str, password: str, nickname: str = "") -> dict:
    phone = phone.strip()
    if not phone or len(phone) < 2:
        raise ValueError("账号至少 2 个字符")
    if len(password) < 6:
        raise ValueError("密码至少 6 位")
    existing = query_one("SELECT id FROM users WHERE phone = ?", (phone,))
    if existing:
        raise ValueError("该手机号已注册")
    uid = execute(
        "INSERT INTO users(phone, password_hash, nickname) VALUES (?,?,?)",
        (phone, hash_password(password), nickname or f"用户{phone[-4:]}"),
    )
    return get_user(uid)  # type: ignore[return-value]


def authenticate(phone: str, password: str) -> dict | None:
    row = query_one("SELECT * FROM users WHERE phone = ?", (phone.strip(),))
    if not row:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return _public_user(row)


def get_user(user_id: int) -> dict | None:
    row = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    return _public_user(row) if row else None


def update_style(user_id: int, style: str) -> None:
    execute("UPDATE users SET style = ? WHERE id = ?", (style, user_id))


def set_vip(user_id: int, plan: str, days: int) -> dict | None:
    expire = datetime.now() + timedelta(days=days)
    execute(
        "UPDATE users SET vip_level = ?, vip_expire_at = ? WHERE id = ?",
        (plan, expire.strftime("%Y-%m-%d %H:%M:%S"), user_id),
    )
    return get_user(user_id)


def _public_user(row: dict) -> dict:
    # 从 dict 里脱敏
    exp = row.get("vip_expire_at")
    level = row.get("vip_level", "free") or "free"
    if exp:
        try:
            if datetime.strptime(exp, "%Y-%m-%d %H:%M:%S") < datetime.now():
                level = "free"
        except Exception:
            pass
    return {
        "id": row["id"],
        "phone": row["phone"],
        "nickname": row.get("nickname", ""),
        "vip_level": level,
        "vip_expire_at": exp,
        "style": row.get("style", "short"),
        "created_at": row.get("created_at"),
    }
