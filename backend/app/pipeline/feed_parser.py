"""Feed fetching and parsing utilities.

Parses RSS, Atom, and JSON feeds into a normalized entry dict shape used
throughout the ingestion pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import struct_time
from typing import Any

import feedparser
import httpx

from app.utils.http_client import HttpClient

logger = logging.getLogger(__name__)

USER_AGENT = "SmartFeedAI/1.0 (+https://smartfeed.example.com)"

MAX_FEED_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class FeedFetchError(Exception):
    """Raised when a feed cannot be fetched or is not parseable."""


@dataclass
class FeedEntry:
    title: str
    url: str
    summary: str | None = None
    content: str | None = None
    author: str | None = None
    published_at: str | None = None
    image_url: str | None = None
    guid: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "summary": self.summary,
            "content": self.content,
            "author": self.author,
            "published_at": self.published_at,
            "image_url": self.image_url,
            "guid": self.guid,
            "tags": self.tags,
        }


def _format_parsed_date(parsed: struct_time | None) -> str | None:
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=UTC).isoformat()
    except (ValueError, TypeError):
        return None


def _extract_tags(entry: Any) -> list[str]:
    tags: list[str] = []
    for tag in entry.get("tags", []) or []:
        term = tag.get("term") or tag.get("label")
        if term:
            tags.append(term)
    return tags


def _extract_image(entry: Any) -> str | None:
    media_thumb = entry.get("media_thumbnail") or []
    if media_thumb and media_thumb[0].get("url"):
        return media_thumb[0]["url"]

    media_content = entry.get("media_content") or []
    for media in media_content:
        url = media.get("url", "")
        if url and (
            media.get("medium") == "image"
            or url.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
        ):
            return url

    enclosures = entry.get("enclosures") or []
    for enc in enclosures:
        if enc.get("type", "").startswith("image/"):
            return enc.get("href")

    # Some feeds inline the image as HTML inside summary/content.
    for field_name in ("summary", "content"):
        raw = entry.get(field_name)
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            raw = raw[0].get("value")
        if not isinstance(raw, str):
            continue
        import re

        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw)
        if match:
            return match.group(1)
    return None


def _parse_entry(entry: Any) -> FeedEntry:
    """Convert a feedparser entry into a normalized FeedEntry."""
    title = (entry.get("title") or "").strip()
    url = entry.get("link") or entry.get("id") or ""
    if not url:
        url = entry.get("guid") or ""

    # feedparser puts the full body in content[0].value, otherwise summary.
    content = None
    if entry.get("content"):
        content = entry["content"][0].get("value") if entry["content"][0] else None
    summary = entry.get("summary") or entry.get("description") or None
    if not content:
        content = summary

    published_at = (
        _format_parsed_date(entry.get("published_parsed"))
        or _format_parsed_date(entry.get("updated_parsed"))
        or entry.get("published")
        or entry.get("updated")
    )

    author = None
    if entry.get("author"):
        author = entry["author"]
    elif entry.get("authors"):
        author = entry["authors"][0].get("name")

    return FeedEntry(
        title=title,
        url=url,
        summary=summary,
        content=content,
        author=author,
        published_at=published_at,
        image_url=_extract_image(entry),
        guid=entry.get("guid") or entry.get("id"),
        tags=_extract_tags(entry),
    )


async def fetch_feed_content(url: str) -> bytes:
    """Fetch a feed URL, returning raw bytes (up to MAX_FEED_SIZE_BYTES)."""
    from app.utils.ssrf_validator import validate_url_ssrf

    validate_url_ssrf(url)
    async with HttpClient(timeout=30) as client:
        try:
            response = await client.get(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/rss+xml, application/atom+xml, application/feed+json, application/xml, text/xml, */*",
                },
            )
        except httpx.HTTPError as exc:
            raise FeedFetchError(f"Failed to fetch {url}: {exc}") from exc

        content = response.content
        if len(content) > MAX_FEED_SIZE_BYTES:
            raise FeedFetchError(f"Feed {url} exceeds size limit")
        return content



def parse_feed_content(raw: bytes | str, feed_url: str = "") -> list[FeedEntry]:
    """Parse raw feed bytes into a list of FeedEntry objects.

    Supports RSS 2.0, Atom, and JSON Feed. Raises FeedFetchError if nothing
    parseable is found.
    """
    try:
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    except UnicodeDecodeError:
        raise FeedFetchError(f"Unparseable feed encoding from {feed_url}") from None

    parsed = feedparser.parse(text)
    if parsed.bozo and not parsed.entries:
        # Try JSON feed format as a fallback.
        entries = _parse_json_feed(text)
        if entries:
            return entries
        raise FeedFetchError(f"Feed {feed_url} could not be parsed: {parsed.bozo_exception}")

    entries = [_parse_entry(entry) for entry in parsed.entries]
    if not entries:
        # Empty but valid feed.
        logger.info(f"Feed {feed_url} returned no entries")
        return []

    return entries


def _parse_json_feed(text: str) -> list[FeedEntry]:
    """Parse a JSON Feed (https://www.jsonfeed.org/) document."""
    import json

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, dict) or "items" not in data:
        return []

    entries: list[FeedEntry] = []
    for item in data.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name") or ""
        url = item.get("url") or item.get("external_url") or ""
        if not title or not url:
            continue

        content_html = item.get("content_html")
        summary = item.get("summary") or item.get("content_text")

        entries.append(
            FeedEntry(
                title=title,
                url=url,
                summary=summary,
                content=content_html or summary,
                author=item.get("author", {}).get("name")
                if isinstance(item.get("author"), dict)
                else None,
                published_at=item.get("date_published"),
                image_url=item.get("image"),
                guid=item.get("id"),
                tags=item.get("tags", []),
            )
        )
    return entries
