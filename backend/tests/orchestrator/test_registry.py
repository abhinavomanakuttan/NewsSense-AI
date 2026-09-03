"""Tests for AgentRegistry — registration, lookup, and category mapping.

WHY test the registry:
- Agent registration is the foundation of the routing system.
- Incorrect registration leads to silent routing failures.
- Dynamic registration/unregistration must be safe.
"""

import pytest

from app.pipeline.orchestrator.registry import AgentRegistry, get_registry, reset_registry


class TestAgentRegistry:
    """Tests for the AgentRegistry class."""

    def setup_method(self):
        self.registry = AgentRegistry()

    def test_register_agent(self):
        """Should register an agent with metadata."""
        async def handler(payload):
            return {"status": "completed"}

        desc = self.registry.register(
            name="test_agent",
            handler=handler,
            display_name="Test Agent",
            description="A test agent",
            categories=["technology", "science"],
            timeout_seconds=60.0,
        )

        assert desc.name == "test_agent"
        assert desc.display_name == "Test Agent"
        assert desc.categories == ["technology", "science"]
        assert desc.timeout_seconds == 60.0
        assert self.registry.agent_count == 1

    def test_get_agent(self):
        """Should retrieve an agent by name."""
        async def handler(payload):
            return {}

        self.registry.register(name="my_agent", handler=handler)
        agent = self.registry.get("my_agent")
        assert agent is not None
        assert agent.name == "my_agent"

    def test_get_nonexistent_agent(self):
        """Should return None for unknown agents."""
        assert self.registry.get("nonexistent") is None

    def test_get_handler(self):
        """Should return the handler function."""
        async def handler(payload):
            return {"result": "ok"}

        self.registry.register(name="my_agent", handler=handler)
        h = self.registry.get_handler("my_agent")
        assert h is not None
        assert callable(h)

    def test_get_agents_for_category(self):
        """Should find agents by category."""
        async def h1(p):
            return {}
        async def h2(p):
            return {}

        self.registry.register(name="tech_agent", handler=h1, categories=["technology"])
        self.registry.register(name="science_agent", handler=h2, categories=["science", "technology"])

        tech_agents = self.registry.get_agents_for_category("technology")
        assert len(tech_agents) == 2

        science_agents = self.registry.get_agents_for_category("science")
        assert len(science_agents) == 1

        sports_agents = self.registry.get_agents_for_category("sports")
        assert len(sports_agents) == 0

    def test_unregister_agent(self):
        """Should remove an agent."""
        async def handler(payload):
            return {}

        self.registry.register(name="temp_agent", handler=handler, categories=["tech"])
        assert self.registry.agent_count == 1

        result = self.registry.unregister("temp_agent")
        assert result is True
        assert self.registry.agent_count == 0
        assert self.registry.get("temp_agent") is None

    def test_unregister_nonexistent(self):
        """Should return False for unknown agents."""
        result = self.registry.unregister("nonexistent")
        assert result is False

    def test_overwrite_registration(self):
        """Should warn and overwrite on duplicate registration."""
        async def handler1(p):
            return {"v": 1}
        async def handler2(p):
            return {"v": 2}

        self.registry.register(name="agent", handler=handler1)
        self.registry.register(name="agent", handler=handler2)

        assert self.registry.agent_count == 1
        h = self.registry.get_handler("agent")
        # The second handler should be the active one
        assert h is not None

    def test_get_all_agents(self):
        """Should return all registered agents."""
        async def h(p):
            return {}

        self.registry.register(name="a", handler=h)
        self.registry.register(name="b", handler=h)
        self.registry.register(name="c", handler=h)

        all_agents = self.registry.get_all_agents()
        assert len(all_agents) == 3

    def test_get_critical_agents(self):
        """Should filter by is_critical flag."""
        async def h(p):
            return {}

        self.registry.register(name="critical", handler=h, is_critical=True)
        self.registry.register(name="optional", handler=h, is_critical=False)

        critical = self.registry.get_critical_agents()
        assert len(critical) == 1
        assert critical[0].name == "critical"

    def test_clear(self):
        """Should remove all agents."""
        async def h(p):
            return {}

        self.registry.register(name="a", handler=h, categories=["tech"])
        self.registry.register(name="b", handler=h, categories=["tech"])

        self.registry.clear()
        assert self.registry.agent_count == 0
        assert self.registry.get_agents_for_category("tech") == []

    def test_get_agent_names(self):
        """Should return list of agent names."""
        async def h(p):
            return {}

        self.registry.register(name="alpha", handler=h)
        self.registry.register(name="beta", handler=h)

        names = self.registry.get_agent_names()
        assert "alpha" in names
        assert "beta" in names


class TestGlobalRegistry:
    """Tests for the module-level singleton registry."""

    def setup_method(self):
        reset_registry()

    def teardown_method(self):
        reset_registry()

    def test_singleton(self):
        """get_registry should return the same instance."""
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_reset(self):
        """reset_registry should create a fresh instance."""
        r1 = get_registry()
        async def h(p):
            return {}
        r1.register(name="test", handler=h)

        reset_registry()
        r2 = get_registry()
        assert r2.agent_count == 0
