from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from apps.api.utils.contract import wrap_contract
from packages.features.etf import build_rotation_dashboard

router = APIRouter()

# D004 mapping for ETF rotation data_mode (status, sample_flag):
#   live   → ('real',     False)
#   hybrid → ('fallback', False)
#   sample → ('mock',     sample-flag-on)
_MODE_TO_D004 = {
    "live": ("real", False),
    "hybrid": ("fallback", False),
    "sample": ("mock", True),
}


@router.get("/rotation/dashboard")
def etf_rotation_dashboard(
    source: Optional[str] = Query(None),
    mode: str = Query("auto", description="auto/live/sample"),
):
    try:
        data = build_rotation_dashboard(source_code=source, mode=mode)
        for key in ("interview_profile", "recommended_pool", "integration_plan", "assumptions"):
            data.pop(key, None)
        status, mock_flag = _MODE_TO_D004.get(data.get("data_mode", "sample"), ("mock", True))
        extras = {
            k: v for k, v in data.items()
            if k not in ("source", "data_status", "mock", "message", "updated_at")
        }
        return wrap_contract(
            data,
            source=data.get("data_source", "sample_engine"),
            status=status,
            mock=mock_flag,
            message=data.get("data_note", ""),
            **extras,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ETF轮动看板数据获取失败: {str(e)}")
