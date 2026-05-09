"""M008/S07 data QA matrix.

Runs representative product API routes through FastAPI TestClient and classifies
each result as:
- d004: normal data contract response
- auth_required: 401/403 control response, not business-empty data
- control: non-data health/control response
- defect: unexpected 5xx, invalid shape, invalid D004 consistency, or unclassified status

The script is intentionally HTTP-level. It avoids direct route calls so FastAPI
Query defaults, auth dependencies, and exception handlers behave like product
usage.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["DEBUG"] = "True"
os.environ.setdefault("ZHICE_JWT_SECRET", "local-dev-secret-for-zhice")
os.environ.setdefault("ZHICE_ADMIN_PASSWORD", "localadmin")
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite:///{ROOT / 'data' / 'zhice.db'}",
)
os.environ.setdefault("ENCRYPTION_KEY", "_KdpjcJ4aDTICVpivJaELzNYQtGJs0syi5aevtQqXrM=")

from fastapi.testclient import TestClient  # noqa: E402

from apps.api.main import app  # noqa: E402


ALLOWED_STATUS = {"real", "mock", "fallback", "unavailable", "empty", "error"}
REQUIRED_D004_KEYS = {"data", "source", "data_status", "mock", "message"}


@dataclass(frozen=True)
class MatrixEndpoint:
    page: str
    method: Literal["GET", "POST"]
    path: str
    body: dict[str, Any] | None = None
    allow_auth: bool = False
    control: bool = False


@dataclass
class MatrixResult:
    page: str
    method: str
    path: str
    http_status: int
    kind: str
    ok: bool
    source: str = ""
    data_status: str = ""
    mock: bool | None = None
    count: int | None = None
    message: str = ""
    detail: str = ""


ENDPOINTS: list[MatrixEndpoint] = [
    MatrixEndpoint("health", "GET", "/api/health", control=True),
    MatrixEndpoint("intraday", "GET", "/api/market/limit-up"),
    MatrixEndpoint("intraday", "GET", "/api/market/broken"),
    MatrixEndpoint("intraday", "GET", "/api/market/hot-stocks", allow_auth=True),
    MatrixEndpoint("intraday", "GET", "/api/market/anomaly", allow_auth=True),
    MatrixEndpoint("replay", "GET", "/api/market/summary", allow_auth=True),
    MatrixEndpoint("replay", "GET", "/api/market/ladder"),
    MatrixEndpoint("replay", "GET", "/api/market/sectors"),
    MatrixEndpoint("replay", "GET", "/api/market/capital-flow"),
    MatrixEndpoint("replay", "GET", "/api/market/rotation"),
    MatrixEndpoint("replay", "GET", "/api/market/next-day-strategy", allow_auth=True),
    MatrixEndpoint("theme", "GET", "/api/theme/list"),
    MatrixEndpoint("theme", "GET", "/api/theme/sectors"),
    MatrixEndpoint("theme", "GET", "/api/theme/cycle-batch"),
    MatrixEndpoint("stock", "GET", "/api/stock/600519"),
    MatrixEndpoint("longhu", "GET", "/api/longhu/rank"),
    MatrixEndpoint("longhu", "GET", "/api/longhu/seats"),
    MatrixEndpoint("value", "GET", "/api/value/screen"),
    MatrixEndpoint("value", "GET", "/api/value/financial/600519"),
    MatrixEndpoint("value", "GET", "/api/value/reports/600519"),
    MatrixEndpoint("value", "GET", "/api/value/research/600519"),
    MatrixEndpoint("growth", "GET", "/api/growth/macro"),
    MatrixEndpoint("growth", "GET", "/api/growth/prosperity"),
    MatrixEndpoint("growth", "GET", "/api/growth/portfolio", allow_auth=True),
    MatrixEndpoint("etf", "GET", "/api/etf/rotation/dashboard"),
    MatrixEndpoint("etf", "GET", "/api/etf/rotation-signals"),
    MatrixEndpoint("backtest", "GET", "/api/backtest/board-strategy"),
    MatrixEndpoint("backtest", "GET", "/api/backtest/etf-rotation"),
    MatrixEndpoint("ai", "GET", "/api/ai/headline"),
    MatrixEndpoint("ai", "GET", "/api/ai/replay-report", allow_auth=True),
    MatrixEndpoint("ai", "POST", "/api/ai/agent/board-trading", body={}),
    MatrixEndpoint("ai", "POST", "/api/ai/agent/etf-rotation", body={}),
]


def _count(payload: dict[str, Any]) -> int | None:
    for key in ("count", "total", "raw_count"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
    for key in ("data", "items", "rank", "stocks", "reports", "industries", "indicators"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("items", "rank", "stocks", "reports", "industries", "indicators"):
            value = data.get(key)
            if isinstance(value, list):
                return len(value)
    return None


def _classify(ep: MatrixEndpoint, status_code: int, payload: Any) -> MatrixResult:
    if not isinstance(payload, dict):
        return MatrixResult(
            ep.page, ep.method, ep.path, status_code, "defect", False,
            detail=f"response is {type(payload).__name__}, expected JSON object",
        )

    message = str(payload.get("message") or payload.get("detail") or "")
    if ep.control:
        return MatrixResult(ep.page, ep.method, ep.path, status_code, "control", status_code < 500, message=message)

    if status_code in (401, 403):
        return MatrixResult(
            ep.page,
            ep.method,
            ep.path,
            status_code,
            "auth_required",
            ep.allow_auth,
            source="auth",
            data_status="error",
            mock=False,
            message=message,
            detail="" if ep.allow_auth else "auth response was not declared allow_auth",
        )

    if status_code >= 500:
        return MatrixResult(ep.page, ep.method, ep.path, status_code, "defect", False, message=message)
    if status_code != 200:
        return MatrixResult(ep.page, ep.method, ep.path, status_code, "defect", False, message=message)

    missing = sorted(REQUIRED_D004_KEYS - set(payload))
    if missing:
        return MatrixResult(
            ep.page, ep.method, ep.path, status_code, "defect", False,
            message=message, detail=f"missing D004 keys: {missing}",
        )

    source = str(payload.get("source") or "")
    data_status = str(payload.get("data_status") or "")
    mock = payload.get("mock")
    ok = True
    detail = ""
    if not source:
        ok, detail = False, "source is empty"
    elif data_status not in ALLOWED_STATUS:
        ok, detail = False, f"invalid data_status={data_status!r}"
    elif not isinstance(mock, bool):
        ok, detail = False, f"mock is {type(mock).__name__}, expected bool"
    elif mock and data_status != "mock":
        ok, detail = False, "mock=True but data_status is not mock"
    elif data_status == "mock" and mock is not True:
        ok, detail = False, "data_status=mock but mock is not True"

    return MatrixResult(
        ep.page,
        ep.method,
        ep.path,
        status_code,
        "d004" if ok else "defect",
        ok,
        source=source,
        data_status=data_status,
        mock=mock if isinstance(mock, bool) else None,
        count=_count(payload),
        message=message,
        detail=detail,
    )


def run_matrix() -> list[MatrixResult]:
    client = TestClient(app)
    results: list[MatrixResult] = []
    for ep in ENDPOINTS:
        try:
            if ep.method == "POST":
                response = client.post(ep.path, json=ep.body or {})
            else:
                response = client.get(ep.path)
            try:
                payload = response.json()
            except Exception:
                payload = {"detail": response.text}
            results.append(_classify(ep, response.status_code, payload))
        except Exception as exc:
            results.append(
                MatrixResult(
                    ep.page,
                    ep.method,
                    ep.path,
                    0,
                    "defect",
                    False,
                    detail=f"request raised: {exc!r}",
                )
            )
    return results


def main() -> int:
    results = run_matrix()
    for result in results:
        print(json.dumps(asdict(result), ensure_ascii=False))
    failed = [item for item in results if not item.ok]
    summary = {
        "total": len(results),
        "failed": len(failed),
        "by_kind": {
            kind: sum(1 for item in results if item.kind == kind)
            for kind in sorted({item.kind for item in results})
        },
    }
    print(json.dumps({"summary": summary}, ensure_ascii=False), file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
