from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - handled by dependency installation
    BaseSettings = object
    SettingsConfigDict = dict


def _load_yaml_config() -> Dict[str, Any]:
    """Load YAML configuration files and flatten into env-var-style keys.

    Loading order (later values override earlier ones):
      1. config/default.yaml (always loaded if it exists)
      2. File specified by CONFIG_FILE environment variable
    """
    try:
        import yaml
    except ImportError:
        return {}

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    flat: Dict[str, Any] = {}

    # Mapping from nested YAML paths to Settings field names
    yaml_key_map = {
        "server.host": "server_host",
        "server.port": "server_port",
        "server.cors_origins": "backend_cors_origins",
        "database.type": "database_type",
        "database.sqlite_path": "database_sqlite_path",
        "database.mysql_host": "database_mysql_host",
        "database.mysql_port": "database_mysql_port",
        "database.mysql_user": "database_mysql_user",
        "database.mysql_password": "database_mysql_password",
        "database.mysql_database": "database_mysql_database",
        "security.secret_key": "secret_key",
        "security.fernet_key": "fernet_key",
        "scheduler.enabled": "scheduler_enabled",
        "scheduler.interval_seconds": "scheduler_interval_seconds",
        "frontend.serve_static": "frontend_serve_static",
        "frontend.build_dir": "frontend_build_dir",
    }

    def _flatten(data: Any, prefix: str = "") -> None:
        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if full_key in yaml_key_map:
                    flat[yaml_key_map[full_key]] = value
                _flatten(value, full_key)

    # 1. Load config/default.yaml
    default_yaml = project_root / "config" / "default.yaml"
    if default_yaml.exists():
        with open(default_yaml, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if data:
                _flatten(data)

    # 2. Load CONFIG_FILE override
    config_file = os.environ.get("CONFIG_FILE")
    if config_file:
        config_path = Path(config_file)
        if not config_path.is_absolute():
            config_path = project_root / config_path
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data:
                    _flatten(data)

    return flat


class Settings(BaseSettings):
    app_name: str = "Spider_XHS"
    api_title: str = "Spider_XHS Operations Platform"
    environment: str = "development"

    # Database
    database_url: str = ""
    database_type: str = "sqlite"
    database_sqlite_path: str = "./data/spider_xhs.db"
    database_mysql_host: str = "localhost"
    database_mysql_port: int = 3306
    database_mysql_user: str = "spider_xhs"
    database_mysql_password: str = "change_me"
    database_mysql_database: str = "spider_xhs"

    # Security
    secret_key: str = "dev-only-change-me"
    fernet_key: str = ""

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # CORS
    backend_cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    # Scheduler
    scheduler_enabled: bool = False
    scheduler_interval_seconds: int = 60

    # Asset storage
    asset_storage_type: str = "local"

    # Frontend static serving
    frontend_serve_static: bool = False
    frontend_build_dir: str = "./frontend/dist"

    if hasattr(BaseSettings, "model_config"):
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def model_post_init(self, __context: Any) -> None:
        # Build database_url from component fields if not explicitly set
        if not self.database_url:
            if self.database_type == "mysql":
                object.__setattr__(
                    self,
                    "database_url",
                    f"mysql+pymysql://{self.database_mysql_user}:{self.database_mysql_password}"
                    f"@{self.database_mysql_host}:{self.database_mysql_port}/{self.database_mysql_database}"
                    "?charset=utf8mb4",
                )
            else:
                # Backward compatibility: if the old default DB path exists but the
                # new YAML-configured path does not, use the old path so existing
                # installations keep their data without manual migration.
                sqlite_path = self.database_sqlite_path
                old_default = "./backend/app/storage/spider_xhs.db"
                if sqlite_path != old_default:
                    new_db = Path(sqlite_path)
                    old_db = Path(old_default)
                    if not new_db.exists() and old_db.exists():
                        sqlite_path = old_default
                object.__setattr__(
                    self,
                    "database_url",
                    f"sqlite:///{sqlite_path}",
                )

    @property
    def storage_dir(self) -> Path:
        return Path("backend/app/storage")


@lru_cache
def get_settings() -> Settings:
    yaml_values = _load_yaml_config()
    return Settings(**yaml_values)
