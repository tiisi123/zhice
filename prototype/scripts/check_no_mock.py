from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ["apps", "packages"]
SKIP_PARTS = {
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}
SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx"}

PATTERNS = [
    re.compile(r"\bMOCK_[A-Z0-9_]+\b"),
    re.compile(r'"mock"\s*:\s*true', re.IGNORECASE),
    re.compile(r"\bmock\s*:\s*true", re.IGNORECASE),
    re.compile(r"\bmock\s*=\s*True\b"),
]

ALLOWLIST = {
    "apps/web/src/components/MockBanner.tsx",
}


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if rel in ALLOWLIST:
        return True
    if path.suffix not in SUFFIXES:
        return True
    return any(part in SKIP_PARTS for part in path.parts)


def main() -> int:
    hits: list[tuple[str, int, str]] = []
    for dirname in SCAN_DIRS:
        base = ROOT / dirname
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if should_skip(path):
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, start=1):
                if any(pattern.search(line) for pattern in PATTERNS):
                    hits.append((path.relative_to(ROOT).as_posix(), lineno, line.strip()[:180]))

    if hits:
        for filename, lineno, line in hits:
            print(f"[FAIL] {filename}:{lineno} {line}")
        print(f"\nMock scan failed: {len(hits)} suspicious lines found", file=sys.stderr)
        return 1

    print("Mock scan passed: no MOCK_ or mock=true found in apps/packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

