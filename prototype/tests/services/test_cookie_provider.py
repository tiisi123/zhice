"""Unit tests for apps.api.services.cookie_provider — Fernet + 30s cache + DB CRUD.

Covers (S03/T03 Negative Tests + Must-Haves):
  - encrypt → decrypt round-trip preserves the plaintext (incl. CJK)
  - decrypt('') and decrypt(invalid) return '' without raising
  - get_kpl_cookie cache hit: 2 calls < TTL → 1 SELECT only
  - set_kpl_cookie invalidates cache: subsequent get returns the new value
  - get_kpl_cookie_metadata returns has_cookie booleans, never the secret value
  - DB SELECT exception → falls back to cached value (or '' on cold cache)

Tests do NOT touch a real database. ``apps.api.db`` is monkey-patched per-test
so the ORM/MySQL stack is never loaded, keeping the suite < 1s in CI.

Module-level Fernet init reads ``settings.encryption_key`` once at import; the
``cookie_provider_module`` fixture sets ENCRYPTION_KEY before importing and
reloads both ``apps.api.config`` and ``apps.api.services.cookie_provider`` so
each test gets a fresh, deterministic Fernet instance and an empty cache.
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet


@pytest.fixture
def cookie_provider_module(monkeypatch):
    """Reload cookie_provider with a known Fernet key + empty cache.

    DEBUG=True bypasses ``validate_required_secrets`` for the unrelated keys
    (ZHICE_JWT_SECRET / DATABASE_URL); the test only exercises the
    encryption_key path.
    """
    test_key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", test_key)
    monkeypatch.setenv("DEBUG", "True")

    from apps.api import config as config_module

    importlib.reload(config_module)

    from apps.api.services import cookie_provider as cp

    importlib.reload(cp)
    cp._reset_cache_for_tests()
    return cp


# ---------------------------------------------------------------------------
# encrypt / decrypt round-trip (Negative Tests #3, #4, plus the empty input)
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_roundtrip(cookie_provider_module):
    cp = cookie_provider_module
    plain = "foo bar 中文 cookie=AbC123;path=/"
    cipher = cp.encrypt(plain)
    assert cipher != plain  # actually encrypted
    assert cp.decrypt(cipher) == plain


def test_decrypt_invalid_token_returns_empty(cookie_provider_module):
    cp = cookie_provider_module
    # 32 random chars — passes Fernet's base64 length sniff but fails MAC.
    bogus = "x" * 32
    assert cp.decrypt(bogus) == ""


def test_decrypt_empty_string_returns_empty(cookie_provider_module):
    cp = cookie_provider_module
    assert cp.decrypt("") == ""


def test_decrypt_with_different_key_returns_empty(cookie_provider_module, monkeypatch):
    """Round-trip with a *different* Fernet key must NOT leak the plaintext."""
    cp = cookie_provider_module
    cipher_from_other_key = Fernet(Fernet.generate_key()).encrypt(b"sneaky").decode()
    # Our module-level Fernet uses a different key from the fixture above.
    assert cp.decrypt(cipher_from_other_key) == ""


# ---------------------------------------------------------------------------
# get_kpl_cookie — cache hit / DB error fallback
# ---------------------------------------------------------------------------


def test_get_kpl_cookie_cache_hit_runs_db_once(cookie_provider_module, monkeypatch):
    cp = cookie_provider_module
    cipher = cp.encrypt("session=ABC")

    mock_query_one = MagicMock(return_value={"secret_value": cipher})
    # Patch into the apps.api.db module so the local import inside
    # get_kpl_cookie picks up the mock.
    import apps.api.db as db

    monkeypatch.setattr(db, "query_one", mock_query_one)

    assert cp.get_kpl_cookie() == "session=ABC"
    assert cp.get_kpl_cookie() == "session=ABC"
    assert cp.get_kpl_cookie() == "session=ABC"
    assert mock_query_one.call_count == 1, "30s cache should serve the 2nd/3rd call"


def test_get_kpl_cookie_db_error_falls_back_to_cache(cookie_provider_module, monkeypatch):
    """DB outage mid-session should keep returning the last known cookie."""
    cp = cookie_provider_module
    cipher = cp.encrypt("warm=cache")

    import apps.api.db as db

    # First call: DB returns the cipher, cache primed.
    monkeypatch.setattr(db, "query_one", MagicMock(return_value={"secret_value": cipher}))
    assert cp.get_kpl_cookie() == "warm=cache"

    # Force cache TTL expiry, then make DB raise.
    cp._reset_cache_for_tests()
    # Re-prime cache via a successful call so we have something to fall back to.
    assert cp.get_kpl_cookie() == "warm=cache"

    # Now expire the cache and break the DB.
    cp._CACHE["kpl_cookie"] = (cp._CACHE["kpl_cookie"][0], 0.0)  # already expired

    def _boom(*_args, **_kwargs):
        raise RuntimeError("MySQL gone")

    monkeypatch.setattr(db, "query_one", _boom)
    assert cp.get_kpl_cookie() == "warm=cache", "should fall back to cached value"


def test_get_kpl_cookie_db_error_cold_cache_returns_empty(cookie_provider_module, monkeypatch):
    cp = cookie_provider_module

    def _boom(*_args, **_kwargs):
        raise RuntimeError("MySQL gone")

    import apps.api.db as db

    monkeypatch.setattr(db, "query_one", _boom)
    assert cp.get_kpl_cookie() == ""


def test_get_kpl_cookie_missing_row_returns_empty(cookie_provider_module, monkeypatch):
    """Pre-migration / missing seed row → '' (no crash, no exception)."""
    cp = cookie_provider_module
    import apps.api.db as db

    monkeypatch.setattr(db, "query_one", MagicMock(return_value=None))
    assert cp.get_kpl_cookie() == ""


# ---------------------------------------------------------------------------
# set_kpl_cookie — encrypts + UPDATEs + invalidates cache
# ---------------------------------------------------------------------------


def test_set_kpl_cookie_invalidates_cache(cookie_provider_module, monkeypatch):
    cp = cookie_provider_module

    mock_execute = MagicMock(return_value=1)
    import apps.api.db as db

    monkeypatch.setattr(db, "execute", mock_execute)
    # Pre-populate cache with stale value.
    cp._CACHE["kpl_cookie"] = ("OLD_VALUE", 1e18)  # very-far expiry

    cp.set_kpl_cookie("NEW_VALUE", updated_by=42)

    assert mock_execute.call_count == 1
    # set_kpl_cookie must rewrite the cache so the very next get returns NEW.
    assert cp.get_kpl_cookie() == "NEW_VALUE"

    # The persisted value must be ciphertext, not plaintext.
    sql_call = mock_execute.call_args
    args = sql_call[0]
    assert "UPDATE system_secrets" in args[0]
    persisted_cipher = args[1][0]
    assert persisted_cipher != "NEW_VALUE", "DB must store ciphertext, not plaintext"
    assert cp.decrypt(persisted_cipher) == "NEW_VALUE"
    # updated_by must be threaded through.
    assert args[1][1] == 42


def test_encrypt_raises_when_fernet_uninitialized(cookie_provider_module, monkeypatch):
    """If Fernet is None (debug-only path), encrypt() must raise — not return plaintext."""
    cp = cookie_provider_module
    monkeypatch.setattr(cp, "_fernet", None)
    with pytest.raises(RuntimeError, match="Fernet"):
        cp.encrypt("anything")


# ---------------------------------------------------------------------------
# get_kpl_cookie_metadata — never returns the secret value
# ---------------------------------------------------------------------------


def test_get_kpl_cookie_metadata_no_secret(cookie_provider_module, monkeypatch):
    cp = cookie_provider_module
    import apps.api.db as db

    monkeypatch.setattr(db, "query_one", MagicMock(return_value=None))

    meta = cp.get_kpl_cookie_metadata()
    assert meta == {"has_cookie": False, "last_updated_at": None, "updated_by": None}


def test_get_kpl_cookie_metadata_has_cookie_true(cookie_provider_module, monkeypatch):
    cp = cookie_provider_module
    import apps.api.db as db

    monkeypatch.setattr(
        db,
        "query_one",
        MagicMock(
            return_value={
                "secret_value": "ciphertext_blob_here",
                "updated_at": "2026-05-01 02:00:00",
                "updated_by": 7,
            }
        ),
    )

    meta = cp.get_kpl_cookie_metadata()
    assert meta == {
        "has_cookie": True,
        "last_updated_at": "2026-05-01 02:00:00",
        "updated_by": 7,
    }
    # Critical: secret_value MUST NOT be in the metadata response.
    assert "secret_value" not in meta


def test_get_kpl_cookie_metadata_db_error_returns_safe_default(cookie_provider_module, monkeypatch):
    cp = cookie_provider_module

    def _boom(*_a, **_k):
        raise RuntimeError("MySQL gone")

    import apps.api.db as db

    monkeypatch.setattr(db, "query_one", _boom)
    meta = cp.get_kpl_cookie_metadata()
    assert meta == {"has_cookie": False, "last_updated_at": None, "updated_by": None}


# ---------------------------------------------------------------------------
# Logger redaction — set_kpl_cookie must NEVER log the plaintext or ciphertext
# ---------------------------------------------------------------------------


def test_set_kpl_cookie_logger_redaction(cookie_provider_module, monkeypatch, caplog):
    cp = cookie_provider_module
    import apps.api.db as db

    monkeypatch.setattr(db, "execute", MagicMock(return_value=1))

    secret_marker = "DO-NOT-LOG-ME-secret-cookie-value"
    with caplog.at_level("INFO", logger="zhice.api.services.cookie_provider"):
        cp.set_kpl_cookie(secret_marker, updated_by=99)

    full_log = "\n".join(r.message for r in caplog.records)
    assert secret_marker not in full_log, "logger must NEVER print the cookie plaintext"
    assert "user_id=99" in full_log
    assert f"len={len(secret_marker)}" in full_log
