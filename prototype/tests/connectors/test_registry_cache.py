"""Tests for registry.py import-path fix and KPL cache-clear hook.

Covers:
  (a) _read_kpl_cookie imports from apps.api.services.cookie_provider (not the old path)
  (b) clear_kpl_caches resets all 3 lru_cache factories
  (c) set_kpl_cookie triggers clear_kpl_caches after DB write
  (d) source-code grep confirms no old import path remains
"""
from __future__ import annotations

import importlib
import pathlib
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet


@pytest.fixture
def _env_debug(monkeypatch):
    """Set DEBUG=True + ENCRYPTION_KEY so config.Settings loads without error."""
    monkeypatch.setenv("DEBUG", "True")
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    from apps.api import config as config_module
    importlib.reload(config_module)


@pytest.fixture
def registry_fresh(_env_debug):
    """Reload registry so lru_cache singletons are empty."""
    from packages.connectors import registry as reg
    importlib.reload(reg)
    yield reg
    reg.clear_kpl_caches()


@pytest.fixture
def cookie_provider_fresh(_env_debug):
    """Reload cookie_provider so it picks up fresh config + Fernet."""
    from apps.api.services import cookie_provider as cp
    importlib.reload(cp)
    cp._reset_cache_for_tests()
    return cp


def test_read_kpl_cookie_imports_from_services_path(registry_fresh, _env_debug):
    """_read_kpl_cookie should resolve against apps.api.services.cookie_provider."""
    from apps.api.services import cookie_provider as cp
    importlib.reload(cp)
    with patch.object(cp, "get_kpl_cookie", return_value="test-cookie") as mock_get:
        with patch.dict(
            "sys.modules",
            {"apps.api.services.cookie_provider": cp},
        ):
            importlib.reload(registry_fresh.__class__.__module__ if False else __import__("packages.connectors.registry"))
            from packages.connectors.registry import _read_kpl_cookie
            result = _read_kpl_cookie()
    assert result == "test-cookie"


def test_clear_kpl_caches_resets_all_three(registry_fresh):
    """After clear_kpl_caches(), subsequent calls to get_kpl* create new objects."""
    reg = registry_fresh
    mock_settings = MagicMock()
    mock_settings.kpl_user_id = "u"
    mock_settings.kpl_token = "t"
    mock_settings.kpl_device_id = "d"
    mock_settings.kpl_version = "5.17.0.0"

    with patch("apps.api.config.settings", mock_settings), patch(
        "packages.connectors.registry._read_kpl_cookie", return_value="c"
    ):
        a1 = reg.get_kpl()
        a2 = reg.get_kpl()
        assert a1 is a2

        b1 = reg.get_kpl_realtime()
        assert b1 is reg.get_kpl_realtime()

        c1 = reg.get_kpl_history()
        assert c1 is reg.get_kpl_history()

        reg.clear_kpl_caches()

        a3 = reg.get_kpl()
        assert a3 is not a1

        b3 = reg.get_kpl_realtime()
        assert b3 is not b1

        c3 = reg.get_kpl_history()
        assert c3 is not c1


def test_set_kpl_cookie_calls_clear_kpl_caches(cookie_provider_fresh, monkeypatch):
    """set_kpl_cookie should call clear_kpl_caches after successful DB write."""
    cp = cookie_provider_fresh
    from apps.api import db
    monkeypatch.setattr(db, "execute", MagicMock())

    with patch(
        "packages.connectors.registry.clear_kpl_caches"
    ) as mock_clear:
        cp.set_kpl_cookie("new-cookie", updated_by=1)
        mock_clear.assert_called_once()


def test_no_old_import_path_in_registry_source():
    """registry.py must not contain 'from apps.api.cookie_provider' (without .services.)."""
    registry_path = (
        pathlib.Path(__file__).resolve().parents[2]
        / "packages"
        / "connectors"
        / "registry.py"
    )
    source = registry_path.read_text()
    old_pattern = "from apps.api.cookie_provider"
    hits = [
        line.strip()
        for line in source.splitlines()
        if old_pattern in line and "services" not in line
    ]
    assert hits == [], f"Old import path still present: {hits}"
