from __future__ import annotations

import logging
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

_logger = logging.getLogger("zhice.api.config")

_ALLOWED_DB_SCHEMES = {"mysql", "mysql+pymysql"}


class Settings(BaseSettings):
    # KPL
    kpl_user_id: str = ""
    kpl_token: str = ""
    kpl_device_id: str = "a59f30e2-5978-3ab5-ac32-d6ae2cc89fd5"
    kpl_version: str = "5.17.0.0"
    kpl_cookie: str = ""  # c1 共享 cookie；T03 之后由 cookie_provider 替代
    kpl_realtime_host: str = "https://apphwhq.longhuvip.com/w1/api/index.php"
    kpl_history_host: str = "https://apphis.longhuvip.com/w1/api/index.php"
    kpl_merge_host: str = "https://applhb.longhuvip.com/w1/api/index.php"

    # XGT
    xgt_host: str = "https://flash-api.xuangubao.com.cn"

    # THS (Phase 3)
    ths_cookie: str = ""

    # DFCF (Phase 4)
    dfcf_cookie: str = ""

    # JYGS (Phase 4)
    jygs_token: str = ""
    jygs_session: str = ""

    # TuShare (Phase ETF-Live)
    tushare_token: str = ""
    tushare_host: str = "https://api.tushare.pro"

    # Database
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = ""
    db_password: str = ""
    db_name: str = "zhice"

    # SSH Tunnel
    ssh_host: str = ""
    ssh_user: str = ""
    ssh_password: str = ""

    # AI (Phase 2)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"

    # App
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Critical deployment secrets — validated on startup when debug=False.
    # Empty defaults so debug-mode imports still succeed; production raises
    # RuntimeError via validate_required_secrets when any of these is unset.
    zhice_jwt_secret: str = ""
    zhice_admin_password: str = ""
    database_url: str = ""

    # T03 (M001/S03): Fernet 32-byte url-safe base64 key (cryptography.fernet
    # .Fernet.generate_key()). Required in production — empty key means we
    # cannot decrypt the persisted KPL Cookie, blocking every short-line route.
    encryption_key: str = ""

    # T04 (M001/S03): SMTP credentials for cookie-failure alert mail. NOT
    # added to validate_required_secrets — SMTP is allowed to fall back
    # gracefully (M001-CONTEXT decision: alert mail failure should not block
    # API startup). Empty smtp_host disables alert send entirely.
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_pass: str = ""

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            text = v.strip().lower()
            if text in {"1", "true", "yes", "on", "debug", "dev", "development"}:
                return True
            if text in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return bool(v)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def validate_required_secrets(self) -> "Settings":
        """Block startup when critical deployment env vars are unset in production.

        Production (debug=False): raises RuntimeError listing every missing key by
        name (no values are echoed). DATABASE_URL must use a MySQL scheme — sqlite
        fallback is forbidden to prevent silent downgrades. Debug mode logs a
        warning instead so local development is unblocked.
        """
        required = (
            ("ZHICE_JWT_SECRET", self.zhice_jwt_secret),
            ("ZHICE_ADMIN_PASSWORD", self.zhice_admin_password),
            ("DATABASE_URL", self.database_url),
            ("ENCRYPTION_KEY", self.encryption_key),
        )
        missing = [name for name, value in required if not value.strip()]

        if self.debug:
            if missing:
                _logger.warning(
                    "DEBUG 模式：以下 env 未设置（生产模式将阻断启动）：%s",
                    ", ".join(missing),
                )
            return self

        if missing:
            raise RuntimeError(
                "启动校验失败：以下关键环境变量未设置或为空："
                + ", ".join(missing)
                + "。请在 .env / docker-compose env 中设置；"
                "ZHICE_JWT_SECRET 可用 openssl rand -hex 32 生成。"
            )

        scheme = self.database_url.split("://", 1)[0].strip().lower()
        if scheme not in _ALLOWED_DB_SCHEMES:
            raise RuntimeError(
                "启动校验失败：DATABASE_URL scheme '"
                + scheme
                + "' 不被支持。生产模式不允许 SQLite，"
                "请配置 MySQL 连接串（如 mysql+pymysql://user:pass@host/db）。"
            )

        return self


settings = Settings()
