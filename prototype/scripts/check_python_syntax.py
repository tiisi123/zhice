from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ["apps", "packages", "scripts"]
SKIP_PARTS = {
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "dist",
    "node_modules",
}


def should_skip(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def main() -> int:
    failures: list[tuple[str, str]] = []
    checked = 0

    for dirname in SCAN_DIRS:
        base = ROOT / dirname
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if should_skip(path):
                continue
            rel = path.relative_to(ROOT).as_posix()
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=rel)
            except SyntaxError as exc:
                failures.append((rel, f"{exc.msg} at line {exc.lineno}"))
            except OSError as exc:
                failures.append((rel, str(exc)))
            else:
                checked += 1

    if failures:
        for filename, error in failures:
            print(f"[FAIL] {filename}: {error}")
        print(f"\nPython syntax check failed: {len(failures)} files", file=sys.stderr)
        return 1

    print(f"Python syntax check passed: {checked} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
