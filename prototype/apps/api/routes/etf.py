from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from packages.features.etf import build_rotation_dashboard

router = APIRouter()


def _status_from_mode(data: dict) -> tuple[str, bool]:
    mode = data.get("data_mode", "sample")
    if mode == "live":
        return "ok", False
    if mode == "hybrid":
        return "partial", False
    return "stale", True


@router.get("/rotation/dashboard")
def etf_rotation_dashboard(
    source: Optional[str] = Query(None),
    mode: str = Query("auto", description="auto/live/sample"),
):
    try:
        data = build_rotation_dashboard(source_code=source, mode=mode)
        for key in ("interview_profile", "recommended_pool", "integration_plan", "assumptions"):
            data.pop(key, None)
        data_status, sample_mode = _status_from_mode(data)
        data.update({
            "source": data.get("data_source", "sample_engine"),
            "data_status": data_status,
            "mock": sample_mode,
            "message": data.get("data_note", ""),
        })
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ETF轮动看板数据获取失败: {str(e)}")
