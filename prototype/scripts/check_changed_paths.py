from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def git_changed_files(base: str | None) -> list[str]:
    if base:
        command = ["git", "-c", "core.quotePath=false", "diff", "--name-only", f"{base}...HEAD"]
    else:
        command = ["git", "-c", "core.quotePath=false", "status", "--porcelain=v1", "-uall"]

    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if proc.returncode != 0:
        print(proc.stderr.strip(), file=sys.stderr)
        raise SystemExit(proc.returncode)

    files: list[str] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        if base:
            filename = line.strip()
        else:
            filename = line[3:].strip()
            if " -> " in filename:
                filename = filename.split(" -> ", 1)[1].strip()
            filename = filename.strip('"')
        if filename:
            files.append(filename.replace("\\", "/"))
    return sorted(set(files))


def matches_any(filename: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(filename, pattern) for pattern in patterns)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check changed files against allowed and forbidden globs.")
    parser.add_argument("--base", help="Compare against a git base ref, for example origin/develop.")
    parser.add_argument("--allow", action="append", default=[], help="Allowed glob. Can be repeated.")
    parser.add_argument("--deny", action="append", default=[], help="Forbidden glob. Can be repeated.")
    parser.add_argument("--list", action="store_true", help="Print changed files before checking.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    changed = git_changed_files(args.base)

    if args.list:
        print("Changed files:")
        for filename in changed:
            print(f"- {filename}")

    denied = [filename for filename in changed if matches_any(filename, args.deny)]
    outside_allow = [
        filename
        for filename in changed
        if args.allow and not matches_any(filename, args.allow)
    ]

    if denied or outside_allow:
        for filename in denied:
            print(f"[DENY] {filename}")
        for filename in outside_allow:
            print(f"[OUTSIDE_ALLOW] {filename}")
        print(
            f"\nChanged path check failed: {len(denied)} denied, {len(outside_allow)} outside allow",
            file=sys.stderr,
        )
        return 1

    print(f"Changed path check passed: {len(changed)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
