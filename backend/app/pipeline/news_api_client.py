"""News API ingestion client supporting official News APIs (NewsAPI.org, GNews, MediaStack, and Generic JSON feeds).

Converts raw API payloads into normalized `FeedEntry` objects used across the ingestion pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.pipeline.feed_parser import FeedEntry, FeedFetchError
from app.utils.ssrf_validator import validate_url_ssrf

logger = logging.getLogger(__name__)

USER_AGENT = "NewsSenseAI/1.0 (+https://newssense.ai)"


class NewsApiClient:
    """Client for querying external News APIs and normalizing article payloads."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def fetch_news_api(
        self,
        endpoint: str,
        api_key: str | None = None,
        category: str | None = None,
        query: str | None = None,
        language: str = "en",
        country: str | None = None,
        page_size: int = 50,
        provider: str = "newsapi",
    ) -> list[FeedEntry]:
        """Fetch articles from a News API provider and return normalized FeedEntry list."""
        validate_url_ssrf(endpoint)

        key = api_key or getattr(settings, f"{provider.lower()}_key", None) or getattr(settings, "newsapi_key", None)
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        params: dict[str, Any] = {}

        if provider.lower() in ("newsapi", "newsapi.org"):
            if key:
                headers["X-Api-Key"] = key
            params = {"pageSize": min(page_size, 100), "language": language}
            if category:
                params["category"] = category
            if country:
                params["country"] = country.lower()
            if query:
                params["q"] = query

        elif provider.lower() in ("gnews", "gnews.io"):
            if key:
                params["apikey"] = key
            params.update({"max": min(page_size, 100), "lang": language})
            if category:
                params["topic"] = category
            if query:
                params["q"] = query

        elif provider.lower() in ("mediastack",):
            if key:
                params["access_key"] = key
            params.update({"limit": min(page_size, 100), "languages": language})
            if category:
                params["categories"] = category
            if country:
                params["countries"] = country.lower()
            if query:
                params["keywords"] = query

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(endpoint, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                raise FeedFetchError(f"HTTP error fetching from {provider} API ({endpoint}): {exc}") from exc
            except Exception as exc:
                raise FeedFetchError(f"Failed to fetch/parse {provider} API response: {exc}") from exc

        return self.parse_api_response(data, provider=provider)

    def parse_api_response(self, data: dict[str, Any], provider: str = "newsapi") -> list[FeedEntry]:
        """Parse raw API JSON into normalized FeedEntry list."""
        if not isinstance(data, dict):
            return []

        entries: list[FeedEntry] = []
        raw_articles = data.get("articles") or data.get("data") or data.get("items") or []
        if not isinstance(raw_articles, list):
            return []

        for item in raw_articles:
            if not isinstance(item, dict):
                continue

            title = item.get("title") or item.get("name") or ""
            url = item.get("url") or item.get("link") or item.get("external_url") or ""
            if not title or not url:
                continue

            summary = item.get("description") or item.get("snippet") or item.get("summary")
            content = item.get("content") or summary

            author = None
            raw_author = item.get("author")
            if isinstance(raw_author, str):
                author = raw_author
            elif isinstance(raw_author, dict):
                author = raw_author.get("name")

            published_at = item.get("publishedAt") or item.get("published_at") or item.get("pubDate")
            image_url = item.get("urlToImage") or item.get("image") or item.get("image_url")

            entries.append(
                FeedEntry(
                    title=title.strip(),
                    url=url.strip(),
                    summary=summary,
                    content=content,
                    author=author,
                    published_at=published_at,
                    image_url=image_url,
                    guid=url,
                    tags=[],
                )
            )

        return entries
