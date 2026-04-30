"""KPL connector sentinel response detection (M001/S03/T07).

T02 introduced the convention that KPL realtime/history/merge ``_post`` returns a
small dict with an ``_error`` key when the call short-circuited (cookie missing)
or upstream returned an HTTP error. The facade ``KplClient`` records the most
recent sentinel state on ``last_error`` / ``last_http_code`` so route handlers
can convert it into a ``status='unavailable'`` contract response without
themselves touching the underlying client internals.

This module exposes three small helpers used by the four short-line routes
(``intraday`` / ``replay`` / ``longhu`` / ``theme``) to keep the detection
logic DRY:

- :func:`is_cookie_missing` — True when the response signals the operator has
  not configured KPL Cookie yet (or the encrypted secret could not be
  decrypted). The cookie_missing branch is **not** counted as an upstream
  failure (T05 ``consecutive_fail`` does not increment) because it is a
  known-operator-pending state, not a flaky network.

- :func:`is_upstream_error` — True when KPL responded with a 4xx / 5xx
  HTTP code. The ``http_code`` is preserved for surfacing in the admin UI.

- :func:`cookie_unavailable_message` — Returns the user-facing Chinese message
  for the response. The cookie_missing message points the operator at the
  ``/admin`` page (KPL Cookie tab) so they can self-serve recovery.

Routes pattern::

    from packages.connectors.kpl.sentinel import (
        is_cookie_missing, is_upstream_error, cookie_unavailable_message,
    )

    data = _kpl.get_concept_selected(trade_date) or []
    if _kpl.last_error:
        pseudo = {"_error": _kpl.last_error, "http_code": _kpl.last_http_code}
        return wrap_contract(
            [],
            source="kpl",
            status="unavailable",
            message=cookie_unavailable_message(pseudo),
            ...,
        )
    return wrap_contract(data, source="kpl", status="real", ...)
"""
from __future__ import annotations

from typing import Any, Mapping


COOKIE_MISSING_MESSAGE = (
    "KPL Cookie 未配置或已失效，请联系管理员在后台 /admin 录入"
)


def is_cookie_missing(resp: Any) -> bool:
    """Return True iff ``resp`` is a sentinel dict with ``_error='cookie_missing'``."""
    return isinstance(resp, Mapping) and resp.get("_error") == "cookie_missing"


def is_upstream_error(resp: Any) -> bool:
    """Return True iff ``resp`` is a sentinel dict with ``_error='kpl_upstream_error'``."""
    return isinstance(resp, Mapping) and resp.get("_error") == "kpl_upstream_error"


def cookie_unavailable_message(resp: Any) -> str:
    """Return a Chinese, redaction-safe message for a sentinel response.

    Cookie-missing returns the constant operator-action message
    (``COOKIE_MISSING_MESSAGE``). Upstream-error embeds ``http_code`` so the
    admin UI can show it. Anything else falls back to a generic message — the
    helper is intentionally lenient so callers can always pass it the latest
    raw response without isinstance gymnastics.
    """
    if is_cookie_missing(resp):
        return COOKIE_MISSING_MESSAGE
    if is_upstream_error(resp):
        http_code = resp.get("http_code") if isinstance(resp, Mapping) else None
        return f"KPL 上游不可达（http_code={http_code}）"
    return "数据源暂时不可用"


def from_client_state(client: Any) -> dict:
    """Synthesize a pseudo-sentinel dict from a facade client's ``last_error``.

    Routes layer convenience: ``KplClient`` tracks ``last_error`` and
    ``last_http_code`` after each KPL-touching call. This helper turns those
    two attributes back into the dict shape consumed by the helpers above.
    Returns an empty dict when no sentinel was recorded.
    """
    err = getattr(client, "last_error", None)
    if not err:
        return {}
    return {"_error": err, "http_code": getattr(client, "last_http_code", None)}
