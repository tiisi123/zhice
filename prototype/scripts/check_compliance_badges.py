#!/usr/bin/env python3
"""Static check: ≥ 24 files must import AIBadge from src/components/AIBadge."""
import subprocess, sys, pathlib

WEB_SRC = pathlib.Path(__file__).resolve().parent.parent / "apps" / "web" / "src"
THRESHOLD = 24

result = subprocess.run(
    ["grep", "-rl", "from.*components/AIBadge", str(WEB_SRC)],
    capture_output=True, text=True,
)
files = [f for f in result.stdout.strip().splitlines() if f]

print(f"AIBadge imported in {len(files)} files (threshold ≥ {THRESHOLD}):")
for f in sorted(files):
    print(f"  {pathlib.Path(f).relative_to(WEB_SRC)}")

if len(files) >= THRESHOLD:
    print(f"\n✅ PASS — {len(files)} ≥ {THRESHOLD}")
    sys.exit(0)
else:
    print(f"\n❌ FAIL — {len(files)} < {THRESHOLD}")
    sys.exit(1)
