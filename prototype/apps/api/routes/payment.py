"""U-03 支付通道（邀请码 + 微信支付占位）。

首期上线使用邀请码制开通 VIP，由管理员生成邀请码分发给用户。
微信支付保留占位接口，后续接入真实支付。
"""
from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from apps.api.auth import current_user, require_admin, set_vip
from apps.api.db import execute, query_one, query_all

logger = logging.getLogger(__name__)

INVITE_CHARS = "ACDEFGHJKMNPQRSTUVWXYZ2345679"
_INVITE_LEN = 6
_INVITE_MAX_RETRIES = 5
router = APIRouter()

PLANS = {
    "standard_month": {"plan": "standard", "days": 30, "price": 9900, "name": "标准版·月"},
    "standard_year": {"plan": "standard", "days": 365, "price": 99000, "name": "标准版·年"},
    "pro_month": {"plan": "pro", "days": 30, "price": 29900, "name": "专业版·月"},
    "pro_year": {"plan": "pro", "days": 365, "price": 299000, "name": "专业版·年"},
}


class CreateOrderIn(BaseModel):
    plan_key: str
    pay_method: str = "wechat"


@router.get("/plans")
def list_plans():
    return [{"key": k, **v} for k, v in PLANS.items()]


@router.post("/order")
def create_order(inp: CreateOrderIn, user: dict = Depends(current_user)):
    from apps.api.config import settings
    if not settings.debug:
        raise HTTPException(status_code=403, detail="在线支付尚未接入真实通道，生产环境仅支持邀请码开通")
    plan = PLANS.get(inp.plan_key)
    if not plan:
        raise HTTPException(status_code=400, detail="未知套餐")
    order_no = f"ZC{int(time.time())}{secrets.randbelow(10000):04d}"
    execute(
        "INSERT INTO orders(order_no, user_id, plan, amount, status, pay_method) VALUES (?,?,?,?,?,?)",
        (order_no, user["id"], inp.plan_key, plan["price"], "pending", inp.pay_method),
    )
    qr_text = f"weixin://wxpay/bizpayurl?pr=mock_{order_no}"
    return {
        "order_no": order_no,
        "amount": plan["price"],
        "amount_yuan": plan["price"] / 100,
        "plan_name": plan["name"],
        "qr_text": qr_text,
        "expire_in": 600,
    }


@router.get("/order/{order_no}")
def query_order(order_no: str, user: dict = Depends(current_user)):
    row = query_one(
        "SELECT * FROM orders WHERE order_no=? AND user_id=?", (order_no, user["id"])
    )
    if not row:
        raise HTTPException(status_code=404, detail="订单不存在")
    return row


# ==================== 邀请码系统 ====================

class RedeemInput(BaseModel):
    code: str
    payment_terms_accepted: bool = False


@router.post("/redeem")
def redeem_invite_code(inp: RedeemInput, user: dict = Depends(current_user)):
    """用户兑换邀请码开通/续费 VIP。"""
    code = inp.code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="请输入邀请码")

    row = query_one("SELECT * FROM invite_codes WHERE code = ?", (code,))
    if not row:
        raise HTTPException(status_code=404, detail="邀请码无效")

    if row["expires_at"]:
        try:
            if datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S") < datetime.now():
                raise HTTPException(status_code=400, detail="邀请码已过期")
        except ValueError:
            pass

    if row["used_count"] >= row["max_uses"]:
        raise HTTPException(status_code=400, detail="邀请码已被使用")

    already = query_one(
        "SELECT id FROM invite_usage WHERE code = ? AND user_id = ?",
        (code, user["id"]),
    )
    if already:
        raise HTTPException(status_code=400, detail="您已使用过该邀请码")

    execute(
        "UPDATE invite_codes SET used_count = used_count + 1 WHERE code = ?",
        (code,),
    )
    execute(
        "INSERT INTO invite_usage(code, user_id) VALUES (?, ?)",
        (code, user["id"]),
    )

    updated = set_vip(user["id"], row["plan"], row["days"])

    if inp.payment_terms_accepted:
        execute(
            "UPDATE users SET payment_terms_accepted_at = ? WHERE id = ?",
            (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), user["id"]),
        )

    logger.info("invite_code redeemed: code=%s user=%s plan=%s days=%d",
                code, user["id"], row["plan"], row["days"])
    return {
        "ok": True,
        "plan": row["plan"],
        "days": row["days"],
        "message": f"已开通 {row['plan'].upper()} 会员 {row['days']} 天",
        "user": updated,
    }


# ==================== 管理员生成邀请码 ====================

class GenerateCodesInput(BaseModel):
    plan: str = "standard"
    days: int = 30
    count: int = 1
    max_uses: int = 1


@router.post("/admin/generate-codes")
def generate_invite_codes(inp: GenerateCodesInput, user: dict = Depends(current_user)):
    """管理员批量生成邀请码。"""
    require_admin(user)
    if inp.plan not in ("standard", "pro"):
        raise HTTPException(status_code=400, detail="plan 必须为 standard 或 pro")
    if inp.count < 1 or inp.count > 100:
        raise HTTPException(status_code=400, detail="count 范围 1-100")
    if inp.days < 1 or inp.days > 3650:
        raise HTTPException(status_code=400, detail="days 范围 1-3650")

    codes = []
    for _ in range(inp.count):
        for attempt in range(_INVITE_MAX_RETRIES):
            code = "".join(secrets.choice(INVITE_CHARS) for _ in range(_INVITE_LEN))
            try:
                execute(
                    "INSERT INTO invite_codes(code, plan, days, max_uses, created_by) VALUES (?,?,?,?,?)",
                    (code, inp.plan, inp.days, inp.max_uses, user["id"]),
                )
                codes.append(code)
                break
            except Exception:
                if attempt == _INVITE_MAX_RETRIES - 1:
                    raise ValueError(f"邀请码生成失败：{_INVITE_MAX_RETRIES} 次唯一性冲突")
    logger.info("admin generated %d invite codes (len=%d): plan=%s days=%d",
                inp.count, _INVITE_LEN, inp.plan, inp.days)
    return {"codes": codes, "plan": inp.plan, "days": inp.days}


@router.get("/admin/codes")
def list_invite_codes(user: dict = Depends(current_user)):
    """管理员查看所有邀请码。"""
    require_admin(user)
    rows = query_all("SELECT * FROM invite_codes ORDER BY created_at DESC LIMIT 200")
    return {"codes": rows}


# ==================== Mock 支付（仅 Debug 环境） ====================

class MockPayIn(BaseModel):
    order_no: str


@router.post("/mock-pay")
def mock_pay(inp: MockPayIn, user: dict = Depends(current_user)):
    """开发/演示环境下模拟支付成功回调。"""
    from apps.api.config import settings
    if not settings.debug:
        raise HTTPException(status_code=403, detail="Mock 支付仅限开发环境")

    row = query_one(
        "SELECT * FROM orders WHERE order_no=? AND user_id=?", (inp.order_no, user["id"])
    )
    if not row:
        raise HTTPException(status_code=404, detail="订单不存在")
    if row["status"] == "paid":
        return {"ok": True, "already_paid": True}
    plan = PLANS.get(row["plan"])
    if not plan:
        raise HTTPException(status_code=400, detail="套餐已下架")
    execute(
        "UPDATE orders SET status='paid', paid_at=CURRENT_TIMESTAMP WHERE order_no=?",
        (inp.order_no,),
    )
    updated = set_vip(user["id"], plan["plan"], plan["days"])
    return {"ok": True, "user": updated}
