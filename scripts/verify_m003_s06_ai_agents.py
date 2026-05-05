"""Root-level wrapper for M003/S06 AI Agent verification.

Delegates to prototype/scripts/verify_m003_s06_ai_agents.py with correct
sys.path so imports resolve from prototype/ directory.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent / ".." / "prototype" / "scripts"
PROTO_DIR = Path(__file__).resolve().parent / ".." / "prototype"

sys.path.insert(0, str(PROTO_DIR))
os.chdir(PROTO_DIR)

from scripts.verify_m003_s06_ai_agents import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
