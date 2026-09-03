"""Article cleaning, normalization, and deduplication preparation engine.

Provides HTML sanitization, text & URL normalization, ISO UTC timestamp standardization,
and cryptographic fingerprint generation required by downstream deduplication and clustering agents.
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup
import dateutil.parser

logger = logging.getLogger(__name__)

# Common publisher title suffixes to strip during title normalization
PUBLISHER_SUFFIX_PATTERNS = [
    r"\s*[-|–—]\s*BBC\s+News.*$",
    r"\s*[-|–—]\s*Reuters.*$",
    r"\s*[-|–—]\s*TechCrunch.*$",
    r"\s*[-|–—]\s*The\s+Guardian.*$",
    r"\s*[-|–—]\s*AP\s+News.*$",
    r"\s*[-|–—]\s*CNN.*$",
    r"\s*[-|–—]\s*The\s+Verge.*$",
    r"\s*[-|–—]\s*Wired.*$",
    r"\s*[-|–—]\s*Bloomberg.*$",
    r"\s*[-|–—]\s*Forbes.*$",
    r"\s*[-|–—]\s*Al\s+Jazeera.*$",
    r"\s*[-|–—]\s*NPR.*$",
]

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
}


def clean_html(raw_html: str | None) -> str:
    """Sanitize HTML content by removing scripts, styles, navigation, and boilerplate."""
    if not raw_html or not isinstance(raw_html, str):
        return ""

    soup = BeautifulSoup(raw_html, "lxml")

    # Remove non-content elements
    for element in soup(["script", "style", "nav", "header", "footer", "aside", "iframe", "form", "svg"]):
        element.decompose()

    # Extract text with paragraph spacing
    text = soup.get_text(separator="\n")
    return clean_text(text)


def clean_text(text: str | None) -> str:
    """Normalize text encoding, whitespace, and strip control characters."""
    if not text or not isinstance(text, str):
        return ""

    # Normalize unicode to NFKC
    normalized = unicodedata.normalize("NFKC", text)

    # Remove non-printable control characters (except newlines & tabs)
    clean_chars = "".join(ch for ch in normalized if ch == "\n" or ch == "\t" or unicodedata.category(ch)[0] != "C")

    # Collapse multiple consecutive empty lines and whitespace
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in clean_chars.splitlines()]
    non_empty_lines = [line for line in lines if line]

    return "\n\n".join(non_empty_lines)


def normalize_title(title: str | None) -> str:
    """Lowercase, strip publisher suffixes, remove noise characters for title deduplication matching."""
    if not title or not isinstance(title, str):
        return ""

    text = title.strip()

    # Strip known publisher suffixes
    for pattern in PUBLISHER_SUFFIX_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Unicode NFKD decomposition to strip accents
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    lowered = normalized.lower()

    # Strip punctuation, retain alphanumeric and space
    clean = re.sub(r"[^\w\s]", "", lowered)
    return re.sub(r"\s+", " ", clean).strip()


def clean_url(url: str | None) -> str:
    """Clean tracking parameters and canonicalize URL format."""
    if not url or not isinstance(url, str):
        return ""

    url_str = url.strip()
    try:
        parsed = urlparse(url_str)
        if not parsed.scheme or not parsed.netloc:
            return url_str

        # Filter out tracking query parameters
        query_params = parse_qsl(parsed.query, keep_blank_values=False)
        clean_query = [(k, v) for k, v in query_params if k.lower() not in TRACKING_PARAMS]

        # Reconstruct canonical URL (lowercasing netloc, stripping trailing slashes in path)
        path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
        canonical = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            urlencode(clean_query),
            "",  # strip fragment
        ))
        return canonical
    except Exception:
        return url_str


def normalize_author(author: str | None) -> str | None:
    """Clean author strings by stripping prefix keywords and extra formatting."""
    if not author or not isinstance(author, str):
        return None

    text = author.strip()
    # Strip common prefixes
    text = re.sub(r"^(by|written by|author:)\s+", "", text, flags=re.IGNORECASE).strip()
    # Remove email addresses inside angle brackets or parentheses
    text = re.sub(r"[\(<].*?@.*?[\)>]", "", text).strip()
    return text if text else None


def normalize_timestamp(published_at: str | None) -> str:
    """Parse date string into ISO 8601 UTC timestamp string (YYYY-MM-DDTHH:MM:SSZ)."""
    if not published_at:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        dt = dateutil.parser.parse(published_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        else:
            dt = dt.astimezone(UTC)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        logger.debug(f"Failed to parse timestamp '{published_at}', using current UTC time")
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_deduplication_fields(
    title: str,
    content: str,
    url: str,
    source_domain: str,
) -> dict[str, str]:
    """Generate canonical hashes and article fingerprint required for deduplication.

    Returns dict containing:
    - normalized_title
    - content_hash
    - url_hash
    - source_hash
    - article_fingerprint
    """
    norm_title = normalize_title(title)
    clean_body = clean_text(content)
    clean_link = clean_url(url)
    domain = (source_domain or "").lower().strip()

    # Cryptographic hashes (SHA-256)
    content_payload = f"{norm_title}\n{clean_body}".encode("utf-8")
    content_hash = hashlib.sha256(content_payload).hexdigest()

    url_hash = hashlib.sha256(clean_link.encode("utf-8")).hexdigest()
    source_hash = hashlib.sha256(domain.encode("utf-8")).hexdigest()

    # Article Fingerprint: combines domain + normalized title + first 200 chars of clean content
    fingerprint_raw = f"{domain}:{norm_title}:{clean_body[:200]}".encode("utf-8")
    article_fingerprint = hashlib.sha256(fingerprint_raw).hexdigest()

    return {
        "normalized_title": norm_title,
        "content_hash": content_hash,
        "url_hash": url_hash,
        "source_hash": source_hash,
        "article_fingerprint": article_fingerprint,
    }
