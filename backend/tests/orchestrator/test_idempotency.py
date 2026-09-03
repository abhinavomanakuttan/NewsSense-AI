"""Tests for idempotency guards and deduplication checkers.

WHY test idempotency:
- Duplicate processing wastes compute and produces inconsistent results.
- Content hash deduplication must handle edge cases (empty strings, unicode).
- Lock acquisition must handle Redis unavailability gracefully.
"""

import pytest

from app.pipeline.orchestrator.idempotency import DeduplicationChecker, IdempotencyGuard


class TestIdempotencyGuard:
    """Tests for distributed lock-based idempotency."""

    @pytest.mark.asyncio
    async def test_acquire_without_redis(self):
        """Should allow processing when Redis is unavailable."""
        guard = IdempotencyGuard(redis_client=None)
        assert await guard.acquire("EVT-1", "agent1") is True

    @pytest.mark.asyncio
    async def test_release_without_redis(self):
        """Should not crash when releasing without Redis."""
        guard = IdempotencyGuard(redis_client=None)
        await guard.release("EVT-1", "agent1")  # Should not raise

    @pytest.mark.asyncio
    async def test_is_processing_without_redis(self):
        """Should return False when Redis is unavailable."""
        guard = IdempotencyGuard(redis_client=None)
        assert await guard.is_processing("EVT-1", "agent1") is False


class TestDeduplicationChecker:
    """Tests for article-level deduplication."""

    @pytest.mark.asyncio
    async def test_without_redis(self):
        """All checks should return False/defaults when Redis is unavailable."""
        checker = DeduplicationChecker(redis_client=None)
        assert await checker.is_article_processed("ART-1") is False
        await checker.mark_article_processed("ART-1")  # Should not raise
        assert await checker.get_processing_version("EVT-1") == 1

    def test_compute_content_hash(self):
        """Content hash should be deterministic and consistent."""
        h1 = DeduplicationChecker.compute_content_hash("Hello World")
        h2 = DeduplicationChecker.compute_content_hash("Hello World")
        assert h1 == h2
        assert len(h1) == 32  # SHA-256 truncated to 32 chars

    def test_content_hash_case_insensitive(self):
        """Content hash should be case-insensitive (normalized)."""
        h1 = DeduplicationChecker.compute_content_hash("Hello World")
        h2 = DeduplicationChecker.compute_content_hash("hello world")
        assert h1 == h2

    def test_content_hash_different_content(self):
        """Different content should produce different hashes."""
        h1 = DeduplicationChecker.compute_content_hash("Article A")
        h2 = DeduplicationChecker.compute_content_hash("Article B")
        assert h1 != h2

    def test_content_hash_empty_string(self):
        """Empty string should produce a valid hash."""
        h = DeduplicationChecker.compute_content_hash("")
        assert len(h) == 32

    def test_content_hash_unicode(self):
        """Unicode content should produce valid hashes."""
        h = DeduplicationChecker.compute_content_hash("日本語の記事")
        assert len(h) == 32

    def test_content_hash_long_content(self):
        """Long content should produce consistent hash."""
        long_text = "word " * 10000
        h = DeduplicationChecker.compute_content_hash(long_text)
        assert len(h) == 32

    @pytest.mark.asyncio
    async def test_content_dedup_without_redis(self):
        """Content dedup should degrade gracefully without Redis."""
        checker = DeduplicationChecker(redis_client=None)
        assert await checker.is_content_duplicate("hash123") is False
        await checker.mark_content_seen("hash123", "EVT-1")  # Should not raise
        assert await checker.get_event_for_content("hash123") is None
