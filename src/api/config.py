"""Explicit, environment-backed configuration for the HTTP serving layer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class ApiSettings:
    """Settings intentionally limited to Phase 07 serving concerns.

    ``max_top_k`` is a development default, not a product policy decision. A
    production deployment must set and review it explicitly.
    """

    environment: str = "development"
    artifact_root: Path = Path("artifacts")
    registry_root: Path = Path("artifacts/registry")
    trust_profiles_path: str | None = None
    trust_provider: str = "csv"
    trust_version: str = "unversioned-csv-no-manifest"
    redis_url: str | None = None
    max_top_k: int = 10
    raw_top_m: int = 50
    cache_ttl_seconds: float = 300.0
    cors_origins: tuple[str, ...] = ()
    cors_allow_credentials: bool = False

    def __post_init__(self) -> None:
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("API_ENVIRONMENT must be development, test, or production")
        if self.trust_provider not in {"csv", "mock", "allow-all"}:
            raise ValueError("TRUST_PROVIDER must be csv, mock, or allow-all")
        if self.environment == "production" and self.trust_provider != "csv":
            raise ValueError("production requires TRUST_PROVIDER=csv")
        if self.cors_allow_credentials and "*" in self.cors_origins:
            raise ValueError("CORS wildcard origin cannot be used with credentials")
        if self.max_top_k < 1:
            raise ValueError("MAX_TOP_K must be positive")
        if self.raw_top_m < 1:
            raise ValueError("RAW_TOP_M must be positive")
        if self.raw_top_m < self.max_top_k:
            raise ValueError("RAW_TOP_M must be greater than or equal to MAX_TOP_K")
        if self.cache_ttl_seconds <= 0:
            raise ValueError("CACHE_TTL_SECONDS must be positive")

    @classmethod
    def from_environment(cls) -> ApiSettings:
        root = Path(os.getenv("ARTIFACT_ROOT", "artifacts"))
        environment = os.getenv("API_ENVIRONMENT", "development").lower()
        default_origins = (
            "" if environment == "production" else "http://localhost:3000,http://127.0.0.1:3000"
        )
        return cls(
            environment=environment,
            artifact_root=root,
            registry_root=Path(os.getenv("ACTIVE_REGISTRY_ROOT", str(root / "registry"))),
            trust_profiles_path=os.getenv("TRUST_PROFILES_PATH") or None,
            trust_provider=os.getenv("TRUST_PROVIDER", "csv").lower(),
            # The bundled CSV has no model/artifact manifest. This value makes
            # that limitation observable rather than inventing a model version.
            trust_version=os.getenv("TRUST_VERSION", "unversioned-csv-no-manifest"),
            redis_url=os.getenv("REDIS_URL") or None,
            max_top_k=int(os.getenv("MAX_TOP_K", "10")),
            raw_top_m=int(os.getenv("RAW_TOP_M", "50")),
            cache_ttl_seconds=float(os.getenv("CACHE_TTL_SECONDS", "300")),
            cors_origins=_csv(
                os.getenv(
                    "CORS_ALLOW_ORIGINS",
                    default_origins,
                )
            ),
            cors_allow_credentials=os.getenv(
                "CORS_ALLOW_CREDENTIALS", "false" if environment == "production" else "true"
            ).lower()
            in {"1", "true", "yes"},
        )
