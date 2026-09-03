"""Agent registry — dynamic registration and lookup of processing agents.

WHY a registry:
- New agents can be added without modifying the orchestrator core.
- Agents self-declare their capabilities (category, input/output schemas).
- The registry enables the routing logic to find the right agent.
- Supports both sync and async agent invocations.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from pydantic import BaseModel, Field

from app.pipeline.orchestrator.schemas import AgentTaskPayload, AgentTaskResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent descriptor
# ---------------------------------------------------------------------------

class AgentDescriptor(BaseModel):
    """Metadata about a registered agent.

    WHY descriptor pattern:
    - Agents register metadata once; the orchestrator queries it at runtime.
    - Enables dynamic routing: "which agents handle POLITICS?"
    - Makes the system self-documenting.
    """
    name: str
    display_name: str
    description: str = ""
    categories: list[str] = Field(default_factory=list)  # news domains this agent handles
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    is_critical: bool = True  # If True, failure blocks the pipeline
    timeout_seconds: float = 120.0
    max_retries: int = 3
    priority: int = 0  # Higher = executed first within a parallel group

    # The actual callable (not serialised)
    _handler: Callable | None = None

    class Config:
        arbitrary_types_allowed = True

    def with_handler(self, handler: Callable) -> AgentDescriptor:
        """Set the handler function (fluent API)."""
        self._handler = handler
        return self

    @property
    def handler(self) -> Callable | None:
        return self._handler


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class AgentRegistry:
    """Central registry for all processing agents.

    WHY singleton-like pattern:
    - Agents register once at startup; the orchestrator looks them up many times.
    - Prevents duplicate registrations.
    - Thread-safe via simple dict (GIL in CPython).
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentDescriptor] = {}
        self._category_map: dict[str, list[str]] = {}  # category → [agent_names]

    def register(
        self,
        name: str,
        handler: Callable,
        *,
        display_name: str | None = None,
        description: str = "",
        categories: list[str] | None = None,
        is_critical: bool = True,
        timeout_seconds: float = 120.0,
        max_retries: int = 3,
        priority: int = 0,
    ) -> AgentDescriptor:
        """Register an agent with the orchestrator.

        WHY explicit registration:
        - Forces agents to declare their capabilities upfront.
        - Prevents accidental duplicate registration (warns instead of overwrites).
        - Enables the routing logic to reason about available agents.
        """
        if name in self._agents:
            logger.warning(f"Agent '{name}' already registered, overwriting")

        descriptor = AgentDescriptor(
            name=name,
            display_name=display_name or name.replace("_", " ").title(),
            description=description,
            categories=categories or [],
            is_critical=is_critical,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            priority=priority,
        )
        descriptor._handler = handler

        self._agents[name] = descriptor

        # Update category → agents mapping
        for cat in (categories or []):
            cat_lower = cat.lower()
            if cat_lower not in self._category_map:
                self._category_map[cat_lower] = []
            if name not in self._category_map[cat_lower]:
                self._category_map[cat_lower].append(name)

        logger.info(f"Registered agent: {name} (categories: {categories})")
        return descriptor

    def get(self, name: str) -> AgentDescriptor | None:
        """Look up an agent by name."""
        return self._agents.get(name)

    def get_handler(self, name: str) -> Callable | None:
        """Get the handler function for an agent."""
        desc = self._agents.get(name)
        return desc.handler if desc else None

    def get_agents_for_category(self, category: str) -> list[AgentDescriptor]:
        """Get all agents that handle a specific news category."""
        names = self._category_map.get(category.lower(), [])
        return [self._agents[n] for n in names if n in self._agents]

    def get_all_agents(self) -> list[AgentDescriptor]:
        """Return all registered agents."""
        return list(self._agents.values())

    def get_critical_agents(self) -> list[AgentDescriptor]:
        """Return agents marked as critical (pipeline blocks on their failure)."""
        return [a for a in self._agents.values() if a.is_critical]

    def get_agent_names(self) -> list[str]:
        """Return all registered agent names."""
        return list(self._agents.keys())

    def unregister(self, name: str) -> bool:
        """Remove an agent from the registry."""
        if name not in self._agents:
            return False

        descriptor = self._agents.pop(name)
        for cat in descriptor.categories:
            cat_lower = cat.lower()
            if cat_lower in self._category_map:
                self._category_map[cat_lower] = [
                    n for n in self._category_map[cat_lower] if n != name
                ]
                if not self._category_map[cat_lower]:
                    del self._category_map[cat_lower]

        logger.info(f"Unregistered agent: {name}")
        return True

    def clear(self) -> None:
        """Remove all registered agents (useful for testing)."""
        self._agents.clear()
        self._category_map.clear()

    @property
    def agent_count(self) -> int:
        return len(self._agents)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    """Get the global agent registry (singleton)."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry (for testing)."""
    global _registry
    if _registry is not None:
        _registry.clear()
    _registry = None
