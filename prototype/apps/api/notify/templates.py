"""Chinese SMTP email body templates (M001/S03/T06).

Pure-string formatters consumed by ``apps.api.services.kpl_health`` —
they never touch the network and never raise, so ``send_alert`` only has
to worry about real SMTP failures.

Bodies intentionally exclude the cookie value, the SMTP password, and
any other secret. Operators get: probe kind, HTTP code (when known),
last-OK timestamp, and the exact admin-UI steps to refresh the cookie.
"""
from __future__ import annotations

import datetime


_SIGNATURE = "—— 智策系统 v1（自动告警，请勿直接回复）"


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def cookie_failure_email_body(
    probe_kind: str,
    http_code: int | None,
    last_ok_at: str | None,
    last_error: str,
) -> str:
    """Return the Chinese body sent on the FIRST consecutive probe failure."""
    http_line = f"- HTTP 状态码：{http_code}" if http_code is not None else "- HTTP 状态码：未返回（网络/解析异常）"
    last_ok_line = f"- 上次成功探测：{last_ok_at}" if last_ok_at else "- 上次成功探测：尚无记录（首次探测即失败）"
    return (
        f"# 【智策】KPL {probe_kind} 健康探测失败\n"
        "\n"
        f"探测时间：{_now_str()}\n"
        f"- 失败原因：{last_error}\n"
        f"{http_line}\n"
        f"{last_ok_line}\n"
        "\n"
        "## 业主操作指引\n"
        "\n"
        "1. 登录后台 `/admin` 页面（业主账号）；\n"
        "2. 切换到「KPL Cookie」标签页；\n"
        "3. 从浏览器抓包工具或开盘啦 PC 客户端复制最新 Cookie；\n"
        "4. 粘贴到输入框 → 点击「保存」；\n"
        "5. 点击「立即探测」，30 秒内健康灯应转绿。\n"
        "\n"
        "如 Cookie 已过期：请打开开盘啦 PC 客户端 → 登录账号 → 用浏览器开发者工具 "
        "（F12 → Network）抓取任意接口请求头中的 `Cookie` 字段，整段复制。\n"
        "\n"
        "短线/复盘/龙虎榜页面在 Cookie 修复前会显示「数据源不可用」红色徽章；"
        "用户体验不会被静默降级，请尽快处理。\n"
        "\n"
        f"{_SIGNATURE}\n"
    )


def cookie_recovery_email_body(probe_kind: str) -> str:
    """Return the Chinese body sent when a previously-failing probe recovers."""
    return (
        f"# 【智策】KPL {probe_kind} 已恢复正常\n"
        "\n"
        f"恢复时间：{_now_str()}\n"
        "- 健康探测已通过，admin 后台健康灯已转绿。\n"
        "- 短线/复盘/龙虎榜页面已恢复实时数据展示。\n"
        "\n"
        "本邮件用于关闭红色警觉，无需操作。\n"
        "\n"
        f"{_SIGNATURE}\n"
    )
