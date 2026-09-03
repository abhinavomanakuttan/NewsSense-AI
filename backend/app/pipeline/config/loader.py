"""Source configuration loader.

Reads the YAML source definitions and exposes them through a SourceConfigLoader
that can be used by the ingestion pipeline, scheduler, and admin API.  Sources
can be added/removed/toggled purely via configuration.

Usage::

    loader = SourceConfigLoader()
    sources = loader.get_sources_for_category("technology")
    defaults = loader.get_defaults()
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# All recognised categories.
CATEGORIES: list[str] = [
    "politics",
    "sports",
    "science",
    "technology",
    "business",
    "entertainment",
    "world_news",
    "environment",
    "health",
]

_SOURCES_YAML = Path(__file__).parent / "sources.yaml"


@dataclass
class SourceDefinition:
    """Parsed representation of a single source from the YAML config."""

    name: str
    url: str
    category: str
    domain: str = ""
    feed_url: str = ""
    api_endpoint: str = ""
    source_type: str = "rss"
    language: str = "en"
    country: str = ""
    priority: str = "normal"
    reliability_score: float = 0.5
    rate_limit: int = 60
    fetch_interval_minutes: int = 15
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_backoff_base: int = 2
    retry_backoff_max: int = 60
    active: bool = True
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a flat dict suitable for Source model creation."""
        return {
            "name": self.name,
            "url": self.url,
            "domain": self.domain,
            "feed_url": self.feed_url,
            "api_endpoint": self.api_endpoint,
            "source_type": self.source_type,
            "language": self.language,
            "country": self.country,
            "category": self.category,
            "is_active": self.active,
            "reliability_score": self.reliability_score,
            "rate_limit": self.rate_limit,
            "fetch_interval_minutes": self.fetch_interval_minutes,
            "priority": self.priority,
            "config": json.dumps(self.config) if self.config else None,
        }


class SourceConfigLoader:
    """Load and query source configurations from sources.yaml."""

    def __init__(self, path: str | Path | None = None):
        self._path = Path(path) if path else _SOURCES_YAML
        self._raw: dict[str, Any] = {}
        self._sources: dict[str, list[SourceDefinition]] = {}
        self._schedules: dict[str, int] = {}
        self._defaults: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            logger.warning("Source config not found at %s – using empty config", self._path)
            return

        with open(self._path, encoding="utf-8") as fh:
            self._raw = yaml.safe_load(fh) or {}

        self._defaults = self._raw.get("defaults", {})
        self._schedules = {
            k: int(v) for k, v in self._raw.get("schedules", {}).items()
        }

        for category in CATEGORIES:
            entries = self._raw.get(category, [])
            self._sources[category] = [self._parse_source(category, e) for e in entries]

        total = sum(len(v) for v in self._sources.values())
        logger.info(
            "Loaded %d sources across %d categories from %s",
            total,
            len(self._sources),
            self._path,
        )

    def _parse_source(self, category: str, entry: dict[str, Any]) -> SourceDefinition:
        merged = {**self._defaults, **entry}
        return SourceDefinition(
            category=category,
            name=merged.get("name", ""),
            url=merged.get("url", ""),
            domain=merged.get("domain", ""),
            feed_url=merged.get("feed_url", ""),
            api_endpoint=merged.get("api_endpoint", ""),
            source_type=merged.get("source_type", "rss"),
            language=merged.get("language", "en"),
            country=merged.get("country", ""),
            priority=merged.get("priority", "normal"),
            reliability_score=float(merged.get("reliability_score", 0.5)),
            rate_limit=int(merged.get("rate_limit", 60)),
            fetch_interval_minutes=int(merged.get("fetch_interval_minutes", 15)),
            timeout_seconds=int(merged.get("timeout_seconds", 30)),
            max_retries=int(merged.get("max_retries", 3)),
            retry_backoff_base=int(merged.get("retry_backoff_base", 2)),
            retry_backoff_max=int(merged.get("retry_backoff_max", 60)),
            active=merged.get("active", True),
            config=merged.get("config", {}),
        )

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_defaults(self) -> dict[str, Any]:
        return dict(self._defaults)

    def get_schedules(self) -> dict[str, int]:
        """Return priority → interval-seconds mapping."""
        return dict(self._schedules)

    def get_interval_for_priority(self, priority: str) -> int:
        return self._schedules.get(priority, 600)

    def get_categories(self) -> list[str]:
        return list(CATEGORIES)

    def get_sources_for_category(self, category: str) -> list[SourceDefinition]:
        return list(self._sources.get(category, []))

    def get_active_sources_for_category(self, category: str) -> list[SourceDefinition]:
        return [s for s in self._sources.get(category, []) if s.active]

    def get_all_sources(self) -> list[SourceDefinition]:
        out: list[SourceDefinition] = []
        for cat in CATEGORIES:
            out.extend(self._sources.get(cat, []))
        return out

    def get_all_active_sources(self) -> list[SourceDefinition]:
        return [s for s in self.get_all_sources() if s.active]

    def get_source_by_name(self, name: str) -> SourceDefinition | None:
        for cat in CATEGORIES:
            for s in self._sources.get(cat, []):
                if s.name == name:
                    return s
        return None

    def get_high_priority_sources(self) -> list[SourceDefinition]:
        return [s for s in self.get_all_active_sources() if s.priority == "high"]

    def get_normal_priority_sources(self) -> list[SourceDefinition]:
        return [s for s in self.get_all_active_sources() if s.priority == "normal"]

    def get_low_priority_sources(self) -> list[SourceDefinition]:
        return [s for s in self.get_all_active_sources() if s.priority == "low"]

    def reload(self) -> None:
        """Hot-reload the YAML file."""
        self._sources.clear()
        self._raw.clear()
        self._load()

    def __repr__(self) -> str:
        total = sum(len(v) for v in self._sources.values())
        return f"<SourceConfigLoader sources={total} categories={len(self._sources)}>"


# Module-level singleton for convenience
_config_loader: SourceConfigLoader | None = None


def get_config_loader() -> SourceConfigLoader:
    global _config_loader
    if _config_loader is None:
        _config_loader = SourceConfigLoader()
    return _config_loader


def reload_config_loader() -> SourceConfigLoader:
    global _config_loader
    _config_loader = SourceConfigLoader()
    return _config_loader
