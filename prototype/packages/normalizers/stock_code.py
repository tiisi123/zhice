from __future__ import annotations

import re


def normalize(code: str) -> str:
    digits = re.sub(r"[^0-9]", "", code)
    return digits[-6:].zfill(6) if digits else ""


def to_prefixed(code: str) -> str:
    c = normalize(code)
    if c.startswith(("6", "9")):
        return f"SH{c}"
    return f"SZ{c}"


def to_dotted(code: str) -> str:
    c = normalize(code)
    if c.startswith(("6", "9")):
        return f"{c}.SH"
    return f"{c}.SZ"


def strip_prefix(code: str) -> str:
    return normalize(code)
