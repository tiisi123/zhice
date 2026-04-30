"""Subprocess-based smoke test for apps/api/config.py startup validation.

Each case spawns a fresh Python process with a curated environment and asserts
that ``from apps.api.config import settings`` either raises (production mode
with missing/invalid secrets) or succeeds (production mode with all secrets
set, or debug mode regardless). Run from the prototype/ directory:

    python scripts/check_startup_validation.py

Exit code 0 means every case passed; non-zero means at least one case failed.

Pydantic must be importable in the chosen interpreter — when it isn't (e.g.
inside an offline sandbox), the whole script self-skips with exit 0 and a
clear ``SKIP`` line on stderr so callers can distinguish "deps unavailable"
from "implementation broken".
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROTOTYPE_ROOT = Path(__file__).resolve().parent.parent
PROBE = "from apps.api.config import settings; print(settings.debug)"


def _run(env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Spawn a subprocess that imports settings under the given env overrides."""
    env = {k: v for k, v in os.environ.items() if k not in env_overrides}
    env.update(env_overrides)
    # PYTHONDONTWRITEBYTECODE keeps __pycache__ clean across cases; PYTHONPATH
    # ensures the apps/ package is importable when cwd resolution differs.
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    env.setdefault("PYTHONPATH", str(PROTOTYPE_ROOT))
    return subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=str(PROTOTYPE_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _missing_pydantic(result: subprocess.CompletedProcess[str]) -> bool:
    return (
        "ModuleNotFoundError" in result.stderr
        and "pydantic" in result.stderr.lower()
    )


def case_missing_all_keys() -> None:
    """Production + every critical secret empty → RuntimeError lists all three keys."""
    result = _run({
        "DEBUG": "false",
        "ZHICE_JWT_SECRET": "",
        "ZHICE_ADMIN_PASSWORD": "",
        "DATABASE_URL": "",
    })
    assert result.returncode != 0, (
        "expected non-zero exit, got 0; stdout=%r stderr=%r"
        % (result.stdout, result.stderr)
    )
    for key in ("ZHICE_JWT_SECRET", "ZHICE_ADMIN_PASSWORD", "DATABASE_URL"):
        assert key in result.stderr, (
            "expected %s in stderr, got: %s" % (key, result.stderr)
        )


def case_missing_one_key() -> None:
    """Production + only ZHICE_JWT_SECRET empty → RuntimeError names ZHICE_JWT_SECRET only."""
    result = _run({
        "DEBUG": "false",
        "ZHICE_JWT_SECRET": "",
        "ZHICE_ADMIN_PASSWORD": "admin-pw",
        "DATABASE_URL": "mysql+pymysql://u:p@h/d",
    })
    assert result.returncode != 0, (
        "expected non-zero, got 0; stderr=%r" % result.stderr
    )
    assert "ZHICE_JWT_SECRET" in result.stderr
    # The other two keys must NOT appear in the missing list (they were set).
    # We grep for the bullet "ZHICE_ADMIN_PASSWORD," appearing as a missing key —
    # checking presence of the bare key name is not enough because the message
    # template might mention it elsewhere; just assert it's not in the list.
    assert "ZHICE_ADMIN_PASSWORD," not in result.stderr
    assert "DATABASE_URL," not in result.stderr


def case_all_set() -> None:
    """Production + all secrets set + mysql url → exit 0."""
    result = _run({
        "DEBUG": "false",
        "ZHICE_JWT_SECRET": "test-jwt",
        "ZHICE_ADMIN_PASSWORD": "test-admin",
        "DATABASE_URL": "mysql+pymysql://u:p@h/d",
    })
    assert result.returncode == 0, (
        "expected exit 0, got %d; stderr=%r" % (result.returncode, result.stderr)
    )


def case_debug_lenient() -> None:
    """Debug mode + everything empty → exit 0 (warning only, no RuntimeError)."""
    result = _run({
        "DEBUG": "true",
        "ZHICE_JWT_SECRET": "",
        "ZHICE_ADMIN_PASSWORD": "",
        "DATABASE_URL": "",
    })
    assert result.returncode == 0, (
        "debug mode must not raise; got %d; stderr=%r"
        % (result.returncode, result.stderr)
    )


def case_whitespace_treated_as_missing() -> None:
    """Production + ZHICE_JWT_SECRET='   ' → still treated as missing."""
    result = _run({
        "DEBUG": "false",
        "ZHICE_JWT_SECRET": "   ",
        "ZHICE_ADMIN_PASSWORD": "ok",
        "DATABASE_URL": "mysql+pymysql://u:p@h/d",
    })
    assert result.returncode != 0, (
        "whitespace value must trigger validation; got 0; stderr=%r" % result.stderr
    )
    assert "ZHICE_JWT_SECRET" in result.stderr


def case_sqlite_rejected_in_production() -> None:
    """Production + sqlite scheme → RuntimeError mentioning DATABASE_URL/sqlite."""
    result = _run({
        "DEBUG": "false",
        "ZHICE_JWT_SECRET": "x",
        "ZHICE_ADMIN_PASSWORD": "y",
        "DATABASE_URL": "sqlite:///./test.db",
    })
    assert result.returncode != 0, (
        "sqlite scheme must be rejected in production; stderr=%r" % result.stderr
    )
    assert "sqlite" in result.stderr.lower()


def case_secret_value_not_echoed() -> None:
    """Validation error must NOT echo the actual secret value into stderr/stdout."""
    secret = "SUPER_SECRET_DO_NOT_LEAK_xKqL93"
    result = _run({
        "DEBUG": "false",
        "ZHICE_JWT_SECRET": secret,
        "ZHICE_ADMIN_PASSWORD": "",
        "DATABASE_URL": "",
    })
    assert result.returncode != 0
    assert secret not in result.stderr, "secret value leaked into stderr"
    assert secret not in result.stdout, "secret value leaked into stdout"


CASES = (
    case_missing_all_keys,
    case_missing_one_key,
    case_all_set,
    case_debug_lenient,
    case_whitespace_treated_as_missing,
    case_sqlite_rejected_in_production,
    case_secret_value_not_echoed,
)


def main() -> int:
    # Probe pydantic availability once so we can self-skip with a clear signal
    # in offline sandboxes (CI / staging will have it installed).
    probe = _run({"DEBUG": "true"})
    if _missing_pydantic(probe):
        print(
            "[SKIP] pydantic not installed in current interpreter "
            "(%s) — cannot exercise startup validation. "
            "Install requirements and retry." % sys.executable,
            file=sys.stderr,
        )
        return 0

    failures: list[tuple[str, str]] = []
    for case in CASES:
        try:
            case()
        except AssertionError as exc:
            failures.append((case.__name__, str(exc)))
            print("[FAIL] %s: %s" % (case.__name__, exc), file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — surface unexpected errors
            failures.append((case.__name__, repr(exc)))
            print("[ERROR] %s: %r" % (case.__name__, exc), file=sys.stderr)
        else:
            print("[PASS] %s" % case.__name__)

    total = len(CASES)
    if failures:
        print(
            "\n%d/%d cases FAILED" % (len(failures), total),
            file=sys.stderr,
        )
        return 1
    print("\nAll %d startup validation cases PASSED" % total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
