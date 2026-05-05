"""M003/S05 slice verification — Backtest endpoints (R011, R012).

Root-level wrapper: delegates to prototype/scripts/verify_m003_s05_backtest.py.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "prototype" / "scripts"
script = SCRIPTS_DIR / "verify_m003_s05_backtest.py"

if not script.exists():
    print(f"ERROR: {script} not found", file=sys.stderr)
    raise SystemExit(2)

result = subprocess.run(
    [sys.executable, str(script)],
    cwd=str(SCRIPTS_DIR.parent),
)
raise SystemExit(result.returncode)
