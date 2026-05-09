from __future__ import annotations

import json
import os
import sys
import sqlite3
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.auth.password import hash_password
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE = os.environ.get("ZHICE_API_BASE", "http://127.0.0.1:8000").rstrip("/")
DB_PATH = os.environ.get(
    "ZHICE_DB_PATH",
    str(ROOT / "data" / "zhice.db"),
)
_TEST_INVITE = "RT0CHK"

CHECKS = [
    ("/api/market/limit-up", "kpl", False),
    ("/api/market/broken", "kpl", False),
    ("/api/market/hot-stocks", "kpl", True),
    ("/api/market/anomaly", "kpl", True),
    ("/api/longhu/rank", "kpl_longhu_bang", False),
]
ALLOWED_STATUS = {"real", "empty", "fallback", "unavailable", "error", "mock"}


@dataclass
class Result:
    path: str
    ok: bool
    detail: str


def get_json(path: str) -> tuple[int, dict | None, str]:
    req = Request(f"{API_BASE}{path}", method="GET")
    try:
        with urlopen(req, timeout=20) as res:
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
    return actual == expected or actual.startswith(f"{expected}_")


def register_token() -> str | None:
    phone = "realtime_check_user"
    password = "secret123"
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute(
            "INSERT OR IGNORE INTO invite_codes (code, max_uses, used_count) VALUES (?, 10, 0)",
            (_TEST_INVITE,),
        )
        row = conn.execute("SELECT id FROM users WHERE phone=?", (phone,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO users(phone, password_hash, nickname, vip_level) VALUES (?,?,?,?)",
                (phone, hash_password(password), "RealtimeCheck", "pro"),
            )
        else:
            conn.execute("UPDATE users SET vip_level='pro' WHERE phone=?", (phone,))
        conn.commit()
        conn.close()
    except Exception:
        pass
    body = json.dumps(
        {
            "phone": phone,
            "password": password,
            "nickname": "RealtimeCheck",
            "invite_code": _TEST_INVITE,
            "terms_accepted": True,
        },
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
            return token
    except Exception:
        pass

    login_body = json.dumps(
        {"phone": phone, "password": password},
        ensure_ascii=False,
    ).encode("utf-8")
    login_req = Request(
        f"{API_BASE}/api/auth/login",
        data=login_body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(login_req, timeout=10) as login_res:
            login_payload = json.loads(login_res.read().decode("utf-8", errors="replace"))
            return login_payload.get("token") or None
    except Exception:
        return None


def get_json_auth(path: str, token: str | None = None) -> tuple[int, dict | None, str]:
    if not token:
        return get_json(path)
    req = Request(f"{API_BASE}{path}", method="GET", headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=20) as res:
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


def check(path: str, expected_source: str, token: str | None = None) -> Result:
    status, payload, raw = get_json_auth(path, token)
    if status != 200:
        return Result(path, False, f"status={status} body={raw[:160]}")
    if not isinstance(payload, dict):
        return Result(path, False, "response is not a JSON object")

    source = str(payload.get("source") or "")
    data_status = str(payload.get("data_status") or "")
    mock = payload.get("mock")
    count = payload.get("count", payload.get("total", len(payload.get("data") or payload.get("items") or [])))

    if not source_matches(source, expected_source):
        return Result(path, False, f"source={source!r}, expected={expected_source!r}")
    if mock is not False:
        return Result(path, False, f"mock must be false, got {mock!r}")
    if data_status not in ALLOWED_STATUS:
        return Result(path, False, f"invalid data_status={data_status!r}")
    if data_status in {"unavailable", "error", "mock"}:
        return Result(path, False, f"data_status={data_status} source={source} count={count}")

    return Result(path, True, f"source={source} data_status={data_status} count={count}")


def main() -> int:
    token = register_token() if any(auth for _, _, auth in CHECKS) else None
    results = [check(path, expected, token if auth else None) for path, expected, auth in CHECKS]
    for item in results:
        mark = "PASS" if item.ok else "FAIL"
        print(f"[{mark}] {item.path} - {item.detail}")
    failed = [item for item in results if not item.ok]
    if failed:
        print(f"\nRealtime source check failed: {len(failed)}/{len(results)} checks failed", file=sys.stderr)
        return 1
    print(f"\nRealtime source check passed: {len(results)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
