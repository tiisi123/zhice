from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["DEBUG"] = "True"
os.environ.setdefault("ZHICE_JWT_SECRET", "test-secret-key-for-ci")
os.environ.setdefault("ZHICE_ADMIN_PASSWORD", "testadmin")
os.environ.setdefault("DATABASE_URL", "sqlite:///data/zhice.db")
os.environ.setdefault("ENCRYPTION_KEY", "_KdpjcJ4aDTICVpivJaELzNYQtGJs0syi5aevtQqXrM=")

from apps.api.routes import theme  # noqa: E402


def _status(resp: dict[str, Any]) -> dict[str, Any]:
    data = resp.get("data")
    count = resp.get("count") or resp.get("total")
    if count is None:
        count = len(data) if isinstance(data, list) else 1 if data else 0
    return {
        "source": resp.get("source"),
        "data_status": resp.get("data_status"),
        "message": resp.get("message"),
        "count": count,
    }


def build_matrix(trade_date: str) -> dict[str, Any]:
    matrix: dict[str, Any] = {"trade_date": trade_date, "checks": [], "bugs": []}

    library = theme.theme_library(date=trade_date)
    library_status = _status(library)
    rows = library.get("data") if isinstance(library, dict) else []
    rows = rows if isinstance(rows, list) else []
    matrix["checks"].append({"endpoint": "GET /api/theme/library", **library_status})
    if library_status["data_status"] in {"empty", "unavailable"}:
        matrix["bugs"].append("题材库列表没有可展示数据；需要刷新 kpl_theme_library.json 或配置旧 kpl_home_theme_mes 采集源。")

    if rows:
        first = rows[0]
        detail = theme.theme_library_detail(str(first.get("theme_id")), date=trade_date)
        detail_status = _status(detail)
        payload = detail.get("data") if isinstance(detail, dict) else {}
        members = (payload or {}).get("theme_sub_detail") if isinstance(payload, dict) else []
        matrix["checks"].append({
            "endpoint": f"GET /api/theme/library/{first.get('theme_id')}",
            **detail_status,
            "theme_name": first.get("theme_name"),
            "member_count": len(members or []),
            "quote_match_status": (payload or {}).get("quote_match_status") if isinstance(payload, dict) else None,
            "market_match_status": ((payload or {}).get("market_match") or {}).get("match_status") if isinstance(payload, dict) else None,
        })
        if detail_status["data_status"] in {"empty", "unavailable"}:
            matrix["bugs"].append(f"题材详情不可用：{first.get('theme_name')}。")
        if isinstance(payload, dict) and payload.get("market_match", {}).get("match_status") == "unmatched":
            matrix["bugs"].append(f"题材未匹配到板块强度：{first.get('theme_name')}。")
        if members and payload.get("quote_match_status") == "missing":
            matrix["bugs"].append(f"题材成员未匹配到 KPL 5000+ 行情：{first.get('theme_name')}。")

    sectors = theme.sector_list(date=trade_date)
    matrix["checks"].append({"endpoint": "GET /api/theme/sectors", **_status(sectors)})
    return matrix


def main() -> int:
    trade_date = os.environ.get("QA_TRADE_DATE") or datetime.now().strftime("%Y-%m-%d")
    matrix = build_matrix(trade_date)
    print(json.dumps(matrix, ensure_ascii=False, indent=2))
    return 1 if matrix["bugs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
