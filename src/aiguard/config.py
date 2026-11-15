"""Runtime configuration, read from ``AIGUARD_*`` environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROLES = ("viewer", "analyst", "admin")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AIGUARD_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./aiguard.db"
    #: Only files inside this directory can be referenced through the API.
    artifact_dir: Path = Path("./artifacts")
    #: Comma-separated ``name:role:key`` entries, e.g. ``ci:analyst:s3cret``.
    api_keys: str = ""
    rate_limit_per_minute: int = 120
    max_request_bytes: int = 20 * 1024 * 1024
    max_scan_bytes: int = 2 * 1024 * 1024 * 1024
    #: Optional path to a YAML policy file replacing the built-in policy set.
    policy_file: Path | None = None

    def parsed_api_keys(self) -> dict[str, tuple[str, str]]:
        """Return ``{key: (name, role)}``; raises ``ValueError`` on bad entries."""
        parsed: dict[str, tuple[str, str]] = {}
        for entry in filter(None, (e.strip() for e in self.api_keys.split(","))):
            parts = entry.split(":", 2)
            if len(parts) != 3 or not all(parts):
                raise ValueError("AIGUARD_API_KEYS entries must look like name:role:key")
            name, role, key = parts
            if role not in ROLES:
                raise ValueError(f"Unknown role {role!r}; expected one of {ROLES}")
            if len(key) < 16:
                raise ValueError(f"API key for {name!r} must be at least 16 characters")
            parsed[key] = (name, role)
        return parsed


@lru_cache
def get_settings() -> Settings:
    return Settings()
