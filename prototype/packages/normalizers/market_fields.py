from __future__ import annotations


def normalize_change_rate(value) -> float:
    """Normalize stock change rate to percentage points.

    Upstream sources may use either ratio values (0.1 = 10%) or percentage
    points (10.0 = 10%). UI and API contracts use percentage points.
    """
    try:
        rate = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if -1 <= rate <= 1 and rate != 0:
        rate *= 100
    return round(rate, 2)
