"""Small, typed configuration for the F00 process; no credentials."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    log_level: str = "info"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        level = env.get("RAG_LOG_LEVEL", "info")
        if level not in {"critical", "error", "warning", "info", "debug"}:
            raise ValueError("RAG_LOG_LEVEL is invalid")
        return cls(log_level=level)
