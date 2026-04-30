from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DENY = ["data/**", ".env", "*.log"]


@dataclass
class Step:
    name: str
    command: list[str]
    cwd: Path = ROOT
    env: dict[str, str] | None = None


def run_step(step: Step) -> bool:
    print(f"\n==> {step.name}")
    env = os.environ.copy()
    if step.env:
        env.update(step.env)
    proc = subprocess.run(step.command, cwd=str(step.cwd), env=env)
    if proc.returncode == 0:
        print(f"[PASS] {step.name}")
        return True
    print(f"[FAIL] {step.name} exit={proc.returncode}")
    return False


def python_cmd(*args: str) -> list[str]:
    return [sys.executable, *args]


def npm_cmd(*args: str) -> list[str]:
    executable = shutil.which("npm.cmd" if os.name == "nt" else "npm") or "npm"
    return [executable, *args]


def build_steps(args: argparse.Namespace) -> list[Step]:
    no_pyc = {"PYTHONDONTWRITEBYTECODE": "1"}
    import_check_env = {
        **no_pyc,
        "ZHICE_DB_PATH": str(Path(tempfile.gettempdir()) / "zhice_check_before_pr.db"),
    }
    steps = [
        Step("Python syntax check", python_cmd("scripts/check_python_syntax.py")),
    ]

    deny_patterns = [*DEFAULT_DENY, *args.deny]
    if args.allow or deny_patterns:
        path_command = python_cmd("scripts/check_changed_paths.py", "--list")
        if args.base:
            path_command.extend(["--base", args.base])
        for pattern in args.allow:
            path_command.extend(["--allow", pattern])
        for pattern in deny_patterns:
            path_command.extend(["--deny", pattern])
        steps.append(Step("Changed path check", path_command))

    steps.extend([
        Step(
            "Python import check",
            python_cmd("-c", "import apps.api.main; print('ok')"),
            env=import_check_env,
        ),
        Step("Mock leakage scan", python_cmd("scripts/check_no_mock.py")),
    ])

    if args.api:
        api_env = {}
        if args.api_base:
            api_env["ZHICE_API_BASE"] = args.api_base.rstrip("/")
        steps.extend([
            Step("API contract check", python_cmd("scripts/check_api_contract.py"), env=api_env),
            Step("Realtime source check", python_cmd("scripts/check_realtime_sources.py"), env=api_env),
        ])

    if args.lint:
        steps.append(Step("Web lint", npm_cmd("run", "lint"), cwd=ROOT / "apps" / "web"))

    if args.web:
        steps.append(Step("Web build", npm_cmd("run", "build"), cwd=ROOT / "apps" / "web"))

    if args.smoke:
        smoke_env = {}
        if args.api_base:
            smoke_env["ZHICE_SMOKE_API_BASE"] = args.api_base.rstrip("/")
        if args.web_base:
            smoke_env["ZHICE_SMOKE_WEB_BASE"] = args.web_base.rstrip("/")
        steps.append(Step("Smoke test", python_cmd("scripts/smoke_test.py"), env=smoke_env))

    return steps


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pre-PR checks for Zhice.")
    parser.add_argument("--api", action="store_true", help="Run checks that require a running API service.")
    parser.add_argument("--web", action="store_true", help="Run frontend build.")
    parser.add_argument("--lint", action="store_true", help="Run frontend lint. This may fail on historical lint debt.")
    parser.add_argument("--smoke", action="store_true", help="Run smoke tests against running API/Web services.")
    parser.add_argument("--api-base", default=os.environ.get("ZHICE_API_BASE", "http://127.0.0.1:8000"))
    parser.add_argument("--web-base", default=os.environ.get("ZHICE_SMOKE_WEB_BASE", "http://127.0.0.1:5173"))
    parser.add_argument("--keep-going", action="store_true", help="Continue after failures.")
    parser.add_argument("--base", help="Git base ref for changed path checks, for example origin/develop.")
    parser.add_argument("--allow", action="append", default=[], help="Allowed changed-path glob. Can be repeated.")
    parser.add_argument(
        "--deny",
        action="append",
        default=[],
        help="Additional forbidden changed-path glob. data/**, .env, and *.log are always denied.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    steps = build_steps(args)
    failed: list[str] = []
    for step in steps:
        ok = run_step(step)
        if not ok:
            failed.append(step.name)
            if not args.keep_going:
                break

    if failed:
        print("\nPre-PR checks failed:")
        for name in failed:
            print(f"- {name}")
        return 1

    print(f"\nPre-PR checks passed: {len(steps)} steps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
