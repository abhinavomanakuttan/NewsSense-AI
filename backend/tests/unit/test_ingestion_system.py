"""Unit tests for the NewsSense AI News Ingestion System.

Tests cover:
- SSRF URL validation and security checks
- Article cleaning, HTML sanitization, URL canonicalization, and date parsing
- Deduplication preparation fingerprint generation
- News API client payload normalization
"""

import pytest

from app.pipeline.article_cleaner import (
    clean_html,
    clean_text,
    clean_url,
    generate_deduplication_fields,
    normalize_author,
    normalize_timestamp,
    normalize_title,
)
from app.pipeline.news_api_client import NewsApiClient
from app.utils.ssrf_validator import SSRFValidationError, validate_url_ssrf


# ============================================================================
# SSRF Validator Tests
# ============================================================================

def test_ssrf_validator_blocks_internal_ips():
    """Verify SSRF validator blocks loopback, private, and cloud metadata IPs."""
    with pytest.raises(SSRFValidationError):
        validate_url_ssrf("http://localhost/admin")

    with pytest.raises(SSRFValidationError):
        validate_url_ssrf("http://127.0.0.1:8080/metrics")

    with pytest.raises(SSRFValidationError):
        validate_url_ssrf("http://169.254.169.254/latest/meta-data/")

    with pytest.raises(SSRFValidationError):
        validate_url_ssrf("http://10.0.0.1/secret")

    with pytest.raises(SSRFValidationError):
        validate_url_ssrf("ftp://example.com/file")


def test_ssrf_validator_allows_valid_public_urls(monkeypatch):
    """Verify SSRF validator permits valid HTTP/HTTPS public URLs."""
    import socket
    # Mock DNS resolution to return a legitimate public IP address
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, *args, **kwargs: [(2, 1, 6, "", ("151.101.0.81", port))],
    )
    url = "https://feeds.bbci.co.uk/news/rss.xml"
    assert validate_url_ssrf(url) == url


def test_ssrf_validator_allow_private_flag():
    """Verify allow_private flag permits localhost in testing mode."""
    url = "http://127.0.0.1:8000/feed"
    assert validate_url_ssrf(url, allow_private=True) == url


# ============================================================================
# Article Cleaner & Normalization Tests
# ============================================================================

def test_clean_html_strips_scripts_and_boilerplate():
    """Verify HTML cleaning removes scripts, styles, navs, and extracts clean body text."""
    raw_html = """
    <html>
        <head><script>alert('xss');</script><style>body { color: red; }</style></head>
        <body>
            <nav><a href="#">Home</a></nav>
            <article>
                <h1>Breaking News Headline</h1>
                <p>First paragraph of actual news content.</p>
                <p>Second paragraph with details.</p>
            </article>
            <footer>Copyright 2026</footer>
        </body>
    </html>
    """
    cleaned = clean_html(raw_html)
    assert "alert" not in cleaned
    assert "Home" not in cleaned
    assert "Copyright" not in cleaned
    assert "Breaking News Headline" in cleaned
    assert "First paragraph of actual news content." in cleaned


def test_normalize_title_strips_suffixes_and_punctuation():
    """Verify title normalization lowercases and strips publisher suffixes."""
    title1 = "Global Climate Summit Reaches Accord - BBC News"
    title2 = "Global Climate Summit Reaches Accord - Reuters"

    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)

    assert norm1 == "global climate summit reaches accord"
    assert norm2 == "global climate summit reaches accord"
    assert norm1 == norm2


def test_clean_url_removes_tracking_parameters():
    """Verify clean_url removes utm_* and tracking parameters."""
    url = "https://example.com/article/123?utm_source=twitter&utm_medium=social&gclid=XYZ123&id=456"
    cleaned = clean_url(url)
    assert "utm_source" not in cleaned
    assert "gclid" not in cleaned
    assert "id=456" in cleaned
    assert cleaned.startswith("https://example.com/article/123")


def test_normalize_author():
    """Verify author string cleaning."""
    assert normalize_author("By John Doe (john@example.com)") == "John Doe"
    assert normalize_author("Written by Jane Smith") == "Jane Smith"
    assert normalize_author(None) is None


def test_normalize_timestamp():
    """Verify date parsing converts diverse strings into uniform ISO UTC format."""
    parsed = normalize_timestamp("2026-08-31T14:30:00Z")
    assert parsed == "2026-08-31T14:30:00Z"

    parsed_rfc = normalize_timestamp("Mon, 31 Aug 2026 14:30:00 +0000")
    assert "2026-08-31T14:30:00" in parsed_rfc


def test_generate_deduplication_fields():
    """Verify deduplication preparation fields generation."""
    fields = generate_deduplication_fields(
        title="Breaking Tech News - Wired",
        content="Artificial intelligence models advance rapidly in 2026.",
        url="https://wired.com/story/ai-news?utm_source=rss",
        source_domain="wired.com",
    )

    assert "normalized_title" in fields
    assert "content_hash" in fields
    assert "url_hash" in fields
    assert "source_hash" in fields
    assert "article_fingerprint" in fields

    assert fields["normalized_title"] == "breaking tech news"
    assert len(fields["content_hash"]) == 64
    assert len(fields["url_hash"]) == 64
    assert len(fields["source_hash"]) == 64
    assert len(fields["article_fingerprint"]) == 64


# ============================================================================
# News API Client Tests
# ============================================================================

def test_news_api_client_parsing():
    """Verify NewsApiClient correctly normalizes API JSON responses."""
    client = NewsApiClient()
    raw_response = {
        "status": "ok",
        "totalResults": 1,
        "articles": [
            {
                "title": "Quantum Computing Milestone Achieved",
                "description": "Researchers demonstrate fault-tolerant qubits.",
                "content": "Full article body about quantum computing breakthrough.",
                "url": "https://techcrunch.com/quantum-milestone",
                "author": "Alice Johnson",
                "publishedAt": "2026-09-01T10:00:00Z",
                "urlToImage": "https://techcrunch.com/images/quantum.jpg",
            }
        ],
    }

    entries = client.parse_api_response(raw_response, provider="newsapi")
    assert len(entries) == 1
    entry = entries[0]
    assert entry.title == "Quantum Computing Milestone Achieved"
    assert entry.url == "https://techcrunch.com/quantum-milestone"
    assert entry.summary == "Researchers demonstrate fault-tolerant qubits."
    assert entry.author == "Alice Johnson"
    assert entry.published_at == "2026-09-01T10:00:00Z"
    assert entry.image_url == "https://techcrunch.com/images/quantum.jpg"
