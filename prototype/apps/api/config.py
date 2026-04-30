from __future__ import annotations

from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # KPL
    kpl_user_id: str = ""
    kpl_token: str = ""
    kpl_device_id: str = ""
    kpl_version: str = "10.1.1"
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


settings = Settings()
