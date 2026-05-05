"""S02/T06 数据契约 runtime checker —— 强制三字段 + D004 6 值 enum + mock⟺status 一致性

校验每条 `CONTRACT_ENDPOINTS` 路径返回的 JSON 必须满足：
  • 必含三字段：source（非空字符串）/ data_status（D004 6 值之一）/ mock（bool）
  • 一致性：mock=True ⟺ data_status='mock'（互为充要条件）
  • source 命名空间：actual == expected_source 或 actual.startswith(f"{expected_source}_")；
    expected_source 为 "" 时跳过具体值校验（仅要求非空）

EXEMPT_ENDPOINTS 显式跳过（打印 [SKIP] + 豁免理由）；带路径参数的端点（含 `{`）也跳过
（runtime 校验需要 fixture，留给 smoke_test.py 在专用 fixture 上做）。

AUTH_REQUIRED_PATHS 在调用前先 register 一个临时用户拿 token，使用 Bearer 头调用——
让 lab/* 等需 JWT 的端点能在 CI 真起 uvicorn 后被覆盖。

SSOT：`prototype/scripts/contract_endpoints.py`
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contract_endpoints import (  # noqa: E402  (sys.path 修改后导入)
    AUTH_REQUIRED_PATHS,
    CONTRACT_ENDPOINTS,
    EXEMPT_ENDPOINTS,
)


API_BASE = os.environ.get("ZHICE_API_BASE", "http://127.0.0.1:8000").rstrip("/")
DB_PATH = os.environ.get(
    "ZHICE_DB_PATH",
    str(Path(__file__).resolve().parents[1] / "data" / "zhice.db"),
)
_TEST_INVITE = "CC0CHK"

# D004 数据契约 6 值 enum（与 packages/shared/types.py / apps/web/src/api/types.ts 一一对应）
ALLOWED_STATUS = {"real", "mock", "fallback", "unavailable", "empty", "error"}

# 契约必需三字段（顶层）
REQUIRED_KEYS = {"source", "data_status", "mock"}


@dataclass
class Result:
    path: str
    ok: bool
    detail: str
    skipped: bool = False


POST_ENDPOINTS: set[str] = {
    "/api/ai/agent/board-trading",
    "/api/ai/agent/etf-rotation",
}


def get_json(path: str, token: str | None = None) -> tuple[int, dict | None, str]:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    encoded_path = quote(path, safe="/:?=&%")
    req = Request(f"{API_BASE}{encoded_path}", method="GET", headers=headers)
    try:
        with urlopen(req, timeout=15) as res:
            text = res.read().decode("utf-8", errors="replace")
            return res.status, json.loads(text), text
    except HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(text), text
        except json.JSONDecodeError:
            return e.code, None, text
    except (URLError, TimeoutError) as e:
        return 0, None, str(e)
    except json.JSONDecodeError as e:
        return 200, None, f"invalid json: {e}"


def post_json(path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict | None, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = json.dumps(body or {}).encode()
    req = Request(f"{API_BASE}{path}", data=payload, method="POST", headers=headers)
    try:
        with urlopen(req, timeout=15) as res:
            text = res.read().decode("utf-8", errors="replace")
            return res.status, json.loads(text), text
    except HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(text), text
        except json.JSONDecodeError:
            return e.code, None, text
    except (URLError, TimeoutError) as e:
        return 0, None, str(e)
    except json.JSONDecodeError as e:
        return 200, None, f"invalid json: {e}"


def source_matches(actual: str, expected: str) -> bool:
    """expected 为空 → 只要 actual 非空即可；否则前缀匹配。"""
    if not expected:
        return bool(actual)
    return actual == expected or actual.startswith(f"{expected}_")


def register_token() -> str | None:
    """Inject invite code into DB, register a temp user, upgrade to VIP pro, return JWT."""
    phone = f"contract_check_{int(time.time())}"
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute(
            "INSERT OR IGNORE INTO invite_codes (code, max_uses, used_count) VALUES (?, 10, 0)",
            (_TEST_INVITE,),
        )
        conn.commit()
        conn.close()
    except Exception:
        return None
    body = json.dumps(
        {"phone": phone, "password": "secret123", "nickname": "ContractCheck",
         "invite_code": _TEST_INVITE},
        ensure_ascii=False,
    ).encode("utf-8")
    req = Request(
        f"{API_BASE}/api/auth/register",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=10) as res:
            payload = json.loads(res.read().decode("utf-8", errors="replace"))
            token = payload.get("token") or None
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    if token:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            conn.execute("UPDATE users SET vip_level='pro' WHERE phone=?", (phone,))
            conn.commit()
            conn.close()
        except Exception:
            pass
    return token


def check_endpoint(path: str, expected_source: str, token: str | None) -> Result:
    if path in POST_ENDPOINTS:
        status, payload, raw = post_json(path, body={}, token=token)
    else:
        status, payload, raw = get_json(path, token=token)
    if status != 200:
        return Result(path, False, f"status={status} body={raw[:160]}")
    if not isinstance(payload, dict):
        return Result(path, False, "response is not a JSON object")

    missing = sorted(REQUIRED_KEYS - set(payload.keys()))
    if missing:
        return Result(path, False, f"missing required keys={missing}")

    data_status = payload.get("data_status")
    if data_status not in ALLOWED_STATUS:
        return Result(
            path,
            False,
            f"invalid data_status={data_status!r} (allowed={sorted(ALLOWED_STATUS)})",
        )

    mock = payload.get("mock")
    if not isinstance(mock, bool):
        return Result(path, False, f"mock must be bool, got {type(mock).__name__}={mock!r}")

    # D004 一致性：mock=True ⟺ data_status='mock'
    if mock and data_status != "mock":
        return Result(
            path,
            False,
            f"consistency violation: mock=True but data_status={data_status!r} (D004 要求 mock=True ⟺ data_status='mock')",
        )
    if data_status == "mock" and not mock:
        return Result(
            path,
            False,
            f"consistency violation: data_status='mock' but mock={mock!r} (D004 要求 mock=True ⟺ data_status='mock')",
        )

    source = str(payload.get("source") or "")
    if not source:
        return Result(path, False, "source must not be empty string")
    if not source_matches(source, expected_source):
        return Result(
            path,
            False,
            f"source={source!r} does not match expected={expected_source!r}",
        )

    return Result(path, True, f"source={source} data_status={data_status} mock={mock}")


def _cleanup_test_user() -> None:
    """Remove injected invite code and contract_check_* user rows."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute("DELETE FROM invite_codes WHERE code=?", (_TEST_INVITE,))
        conn.execute("DELETE FROM users WHERE phone LIKE 'contract_check_%'")
        conn.commit()
        conn.close()
    except Exception:
        pass


def main() -> int:
    exempt_paths = {p for p, _ in EXEMPT_ENDPOINTS}
    exempt_reasons = dict(EXEMPT_ENDPOINTS)

    token = register_token() if any(p in AUTH_REQUIRED_PATHS for p, _ in CONTRACT_ENDPOINTS) else None

    results: list[Result] = []
    skipped_count = 0
    try:
        for path, expected_source in CONTRACT_ENDPOINTS:
            if path in exempt_paths:
                print(f"[SKIP] {path} - exempt: {exempt_reasons[path]}")
                skipped_count += 1
                continue
            if "{" in path:
                print(f"[SKIP] {path} - parameterized path (验证留给 smoke_test 专用 fixture)")
                skipped_count += 1
                continue
            result = check_endpoint(path, expected_source, token)
            results.append(result)
            mark = "PASS" if result.ok else "FAIL"
            print(f"[{mark}] {result.path} - {result.detail}")
    finally:
        _cleanup_test_user()

    failed = [r for r in results if not r.ok]
    total = len(results)
    if failed:
        print(
            f"\nAPI contract failed: {len(failed)}/{total} checks failed "
            f"(skipped {skipped_count})",
            file=sys.stderr,
        )
        return 1
    print(f"\nAPI contract passed: {total} checks (skipped {skipped_count})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
