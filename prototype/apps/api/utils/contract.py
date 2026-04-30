"""S02/T01 D004 数据契约 helper（参见 .gsd/DECISIONS.md::D004）

`wrap_contract` 是 28 路由响应统一为 `{data, source, data_status, mock, message, updated_at}` 的共享入口。

D004 锁定 6 值 enum：`real | mock | fallback | unavailable | empty | error`
一致性约束：mock=True ⟺ data_status='mock'（违反时 raise ValueError，让契约违规在 unit 层暴露而非到
check_api_contract.py 才发现）

auto-empty 兜底：status='real' && not data → data_status='empty'，让前端不需要再次判空。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


ALLOWED_STATUS: frozenset[str] = frozenset(
    {"real", "mock", "fallback", "unavailable", "empty", "error"}
)


def wrap_contract(
    data: Any,
    *,
    source: str,
    status: str = "real",
    mock: bool = False,
    message: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """把路由返回的数据包装成 D004 契约响应。

    Args:
        data: 路由实际负载（list / dict / scalar 都可）。
        source: 数据源 namespace（"kpl" / "tushare" / "eastmoney" 等），不暴露 endpoint URL / token。
        status: D004 6 值之一。默认 'real'。
        mock: 是否演示数据。必须与 status='mock' 互为充要条件。
        message: 业务可见错误描述（不携带堆栈或敏感参数）。
        **extra: 路由额外字段（如 trade_date / count / prev_date）。

    Returns:
        dict：`{data, source, data_status, mock, message, updated_at, **extra}`。

    Raises:
        ValueError: status 不在 ALLOWED_STATUS / mock 与 status='mock' 不一致。
    """
    if status not in ALLOWED_STATUS:
        raise ValueError(
            f"data_status={status!r} 不在 D004 ALLOWED_STATUS 6 值集合：{sorted(ALLOWED_STATUS)}"
        )
    if mock and status != "mock":
        raise ValueError(
            f"契约违规：mock=True 但 data_status={status!r}（D004 要求 mock=True ⟺ data_status='mock'）"
        )
    if status == "mock" and not mock:
        raise ValueError(
            "契约违规：data_status='mock' 但 mock=False（D004 要求 mock=True ⟺ data_status='mock'）"
        )

    if status == "real" and not data:
        data_status = "empty"
    else:
        data_status = status

    return {
        "data": data,
        "source": source,
        "data_status": data_status,
        "mock": mock,
        "message": message,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **extra,
    }
