"""Tests for feed parsing utilities (no network access required)."""

import pytest

from app.pipeline.feed_parser import FeedFetchError, _parse_entry, parse_feed_content

RSS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://testfeed.com</link>
    <description>Sample feed</description>
    <item>
      <title>  First Story  </title>
      <link>https://testfeed.com/first</link>
      <description>A summary of the first story.</description>
      <content:encoded><![CDATA[<p>Full body of the first story.</p>]]></content:encoded>
      <author>Jane Doe</author>
      <pubDate>Wed, 29 Jul 2026 12:00:00 GMT</pubDate>
      <guid>https://testfeed.com/first</guid>
      <category>Tech</category>
      <category>AI</category>
      <enclosure url="https://testfeed.com/img1.jpg" type="image/jpeg"/>
    </item>
    <item>
      <title>Second Story</title>
      <link>https://testfeed.com/second</link>
      <description>Another summary.</description>
    </item>
  </channel>
</rss>
"""

ATOM_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <id>urn:atom</id>
  <entry>
    <title>Atom Entry</title>
    <id>urn:atom:1</id>
    <link href="https://atomfeed.com/1"/>
    <summary>Atom summary here.</summary>
    <updated>2026-07-28T08:30:00Z</updated>
  </entry>
</feed>
"""

JSON_FEED = b"""{
  "version": "https://jsonfeed.org/version/1.1",
  "title": "JSON Feed",
  "items": [
    {
      "id": "j1",
      "url": "https://jsonfeed.com/1",
      "title": "JSON Story",
      "summary": "A JSON summary.",
      "content_html": "<p>Body</p>",
      "date_published": "2026-07-27T09:00:00Z",
      "image": "https://jsonfeed.com/img.png",
      "tags": ["science"]
    }
  ]
}
"""


def test_parse_rss_extracts_fields():
    entries = parse_feed_content(RSS_XML)
    assert len(entries) == 2

    first = entries[0]
    assert first.title == "First Story"
    assert first.url == "https://testfeed.com/first"
    assert "summary of the first story" in first.summary
    assert first.content == "<p>Full body of the first story.</p>"
    assert first.author == "Jane Doe"
    assert first.published_at is not None
    assert first.guid == "https://testfeed.com/first"
    assert "Tech" in first.tags
    assert "AI" in first.tags
    assert first.image_url == "https://testfeed.com/img1.jpg"


def test_parse_atom():
    entries = parse_feed_content(ATOM_XML)
    assert len(entries) == 1
    assert entries[0].title == "Atom Entry"
    assert entries[0].url == "https://atomfeed.com/1"
    assert entries[0].published_at is not None


def test_parse_json_feed():
    entries = parse_feed_content(JSON_FEED)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.title == "JSON Story"
    assert entry.url == "https://jsonfeed.com/1"
    assert entry.image_url == "https://jsonfeed.com/img.png"
    assert entry.tags == ["science"]


def test_parse_invalid_raises():
    with pytest.raises(FeedFetchError):
        parse_feed_content(b"this is not a feed <", "https://example.com/bad")


def test_parse_empty_feed_returns_empty():
    empty = b"""<?xml version="1.0"?>
    <rss version="2.0"><channel><title>x</title></channel></rss>"""
    assert parse_feed_content(empty) == []


def test_parse_entry_missing_link_uses_id():
    entry = _parse_entry({"title": "No Link", "id": "https://example.com/item"})
    assert entry.url == "https://example.com/item"


def test_parse_entry_empty_title():
    entry = _parse_entry({"title": "  ", "link": "https://example.com/x"})
    assert entry.title == ""
