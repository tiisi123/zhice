"""S02/T06 端到端 smoke —— web 路径 + 旧 API + 数据契约 (DATA_ENDPOINTS)

三段：
  1. check_web_paths：12 条前端 SPA 路径，确认 vite/preview 静态注入 root 元素
  2. check_api：旧 health + register + 4 鉴权后 GET（保持向后兼容）
  3. check_data_contract：DATA_ENDPOINTS（≥15 条）GET 后强制 D004 三字段契约
     • data_status ∈ {real, mock, fallback, unavailable, empty} （error 应是异常路径，
       smoke 跑 200 响应，不期望 error）
     • source 非空字符串
     • mock 是 bool

DATA_ENDPOINTS 选取来自 prototype/scripts/contract_endpoints.py SSOT 的代表样本（覆盖
KPL 实时×4 + KPL 历史×3 + sample/static×4 + eastmoney×2 + sentiment×2 等命名空间）。
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from http.client import BadStatusLine
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE = os.environ.get("ZHICE_SMOKE_API_BASE", "http://127.0.0.1:8000").rstrip("/")
WEB_BASE = os.environ.get("ZHICE_SMOKE_WEB_BASE", "http://127.0.0.1:5173").rstrip("/")

WEB_PATHS = [
    "/login",
    "/replay",
    "/intraday",
    "/sentiment",
    "/theme",
    "/hot-events",
    "/stock",
    "/strategy",
    "/recommend",
    "/dashboard",
    "/finance-report",
    "/feature-map",
]


# 契约 smoke 端点（path, expected_source_prefix）—— 命名空间用 prefix 匹配
# 选自 contract_endpoints.py SSOT 的代表样本。空字符串 expected 表示只校验 source 非空。
DATA_ENDPOINTS: list[tuple[str, str]] = [
    # KPL 实时 ×4
    ("/api/market/limit-up", "kpl"),
    ("/api/market/broken", "kpl"),
    ("/api/market/hot-stocks", "kpl"),
    ("/api/market/anomaly", "kpl"),
    # KPL 历史 / 复盘 ×3
    ("/api/market/summary", "kpl"),
    ("/api/market/ladder", "kpl"),
    ("/api/analysis/broken-cases", "kpl"),
    # KPL 衍生 ×2
    ("/api/longhu/seats", "kpl_longhu_bang"),
    ("/api/theme/list", "kpl"),
    # Sentiment ×2
    ("/api/market/sentiment-history", "kpl_sentiment"),
    ("/api/market/sentiment-phase", "kpl_sentiment"),
    # Eastmoney ×2
    ("/api/news/flash", "eastmoney_news"),
    ("/api/news/timeline", "eastmoney_news"),
    # Static / sample ×4
    ("/api/chain/list", "static_chain_registry"),
    ("/api/recommend/templates", "static_recommend_templates"),
    ("/api/research/announcements", "sample_research_announcements"),
    ("/api/growth/portfolio", "sample_portfolio"),
    ("/api/value/screen", "sample_financials"),
]

# data_status ∈ 该集合视为 smoke 通过（error 留给异常路径，不在 200 smoke 里出现）
SMOKE_ALLOWED_STATUS = {"real", "mock", "fallback", "unavailable", "empty"}


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def request(method: str, url: str, body: dict | None = None, token: str | None = None) -> tuple[int, str]:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as res:
            return res.status, res.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError, BadStatusLine, OSError) as e:
        return 0, str(e)


def check_web_paths() -> list[CheckResult]:
    results: list[CheckResult] = []
    for path in WEB_PATHS:
        status, text = request("GET", f"{WEB_BASE}{path}")
        ok = status == 200 and "root" in text
        results.append(CheckResult(f"WEB {path}", ok, f"status={status} bytes={len(text)}"))
    return results


def check_api() -> list[CheckResult]:
    results: list[CheckResult] = []
    status, text = request("GET", f"{API_BASE}/api/health")
    results.append(CheckResult("API /api/health", status == 200 and "ok" in text, f"status={status} body={text[:200]}"))

    phone = f"smoke{int(time.time())}"
    status, text = request(
        "POST",
        f"{API_BASE}/api/auth/register",
        {"phone": phone, "password": "smoke123456", "nickname": "Smoke测试"},
    )
    token = ""
    try:
        payload = json.loads(text)
        token = payload.get("token", "")
    except json.JSONDecodeError:
        pass
    results.append(CheckResult("API /api/auth/register", status == 200 and bool(token), f"status={status} phone={phone}"))

    if token:
        for path in ["/api/auth/me", "/api/recommend/templates", "/api/recommend/strategies", "/api/news/timeline?n=10"]:
            status, text = request("GET", f"{API_BASE}{path}", token=token)
            results.append(CheckResult(f"API {path}", status == 200, f"status={status} bytes={len(text)} body={text[:120]}"))
    return results


def _source_matches(actual: str, expected: str) -> bool:
    if not expected:
        return bool(actual)
    return actual == expected or actual.startswith(f"{expected}_")


def check_data_contract() -> list[CheckResult]:
    """对每条 DATA_ENDPOINTS 校验 D004 三字段（source / data_status / mock）。"""
    results: list[CheckResult] = []
    for path, expected_source in DATA_ENDPOINTS:
        status, text = request("GET", f"{API_BASE}{path}")
        if status != 200:
            results.append(
                CheckResult(f"DATA {path}", False, f"status={status} body={text[:120]}")
            )
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as e:
            results.append(CheckResult(f"DATA {path}", False, f"invalid json: {e}"))
            continue
        if not isinstance(payload, dict):
            results.append(CheckResult(f"DATA {path}", False, "response not a JSON object"))
            continue

        missing = [k for k in ("source", "data_status", "mock") if k not in payload]
        if missing:
            results.append(
                CheckResult(f"DATA {path}", False, f"missing keys={missing}")
            )
            continue

        source = str(payload.get("source") or "")
        data_status = payload.get("data_status")
        mock = payload.get("mock")

        if not source:
            results.append(CheckResult(f"DATA {path}", False, "source is empty"))
            continue
        if not _source_matches(source, expected_source):
            results.append(
                CheckResult(
                    f"DATA {path}",
                    False,
                    f"source={source!r} does not match expected={expected_source!r}",
                )
            )
            continue
        if data_status not in SMOKE_ALLOWED_STATUS:
            results.append(
                CheckResult(
                    f"DATA {path}",
                    False,
                    f"unexpected data_status={data_status!r}",
                )
            )
            continue
        if not isinstance(mock, bool):
            results.append(
                CheckResult(
                    f"DATA {path}",
                    False,
                    f"mock must be bool, got {type(mock).__name__}={mock!r}",
                )
            )
            continue
        # 一致性：mock=True ⟺ data_status='mock'
        if mock and data_status != "mock":
            results.append(
                CheckResult(
                    f"DATA {path}",
                    False,
                    f"consistency: mock=True but data_status={data_status!r}",
                )
            )
            continue
        if data_status == "mock" and not mock:
            results.append(
                CheckResult(
                    f"DATA {path}",
                    False,
                    f"consistency: data_status='mock' but mock={mock!r}",
                )
            )
            continue

        results.append(
            CheckResult(
                f"DATA {path}",
                True,
                f"source={source} data_status={data_status} mock={mock}",
            )
        )
    return results


def main() -> int:
    results = check_web_paths() + check_api() + check_data_contract()
    failed = [r for r in results if not r.ok]
    for r in results:
        mark = "PASS" if r.ok else "FAIL"
        print(f"[{mark}] {r.name} - {r.detail}")
    if failed:
        print(f"\nSmoke failed: {len(failed)}/{len(results)} checks failed", file=sys.stderr)
        return 1
    print(f"\nSmoke passed: {len(results)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
