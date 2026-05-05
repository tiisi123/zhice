"""Root-level wrapper: delegates to prototype/scripts/check_api_contract.py."""
import subprocess
import sys
from pathlib import Path

PROTO_SCRIPTS = Path(__file__).resolve().parent.parent / "prototype" / "scripts"
script = PROTO_SCRIPTS / "check_api_contract.py"

if not script.exists():
    print(f"ERROR: {script} not found", file=sys.stderr)
    raise SystemExit(2)

result = subprocess.run(
    [sys.executable, str(script)],
    cwd=str(PROTO_SCRIPTS),
)
raise SystemExit(result.returncode)
