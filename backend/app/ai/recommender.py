"""Scoring-based article recommender with implicit preference signals.

Operates on DB-shaped article payloads (keys mirror the Article model) plus a
user-preferences dict. Pure heuristics, no model download.

Signals (additive, capped at a reasonable ceiling):

- explicit preference: preferred category (+0.3), preferred source (+0.2)
- implicit affinity: categories the user actually read/bookmarked are boosted,
  weighted by how often they appear in the user's history
- content similarity: keyword overlap between a candidate and the union of
  keywords from the user's reading history + bookmarks
- credibility: scores > 0.7 get +0.1
- popularity: up to +0.1 as view_count grows toward 1000
- recency: fresh articles (within 7 days) get +0.1

Articles in a language the user explicitly does not read are excluded.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from app.ai.base import AIModule

_BASE_SCORE = 0.5
_CATEGORY_BOOST = 0.3
_SOURCE_BOOST = 0.2
_CREDIBILITY_BOOST = 0.1
_POPULARITY_MAX = 0.1
_RECENCY_DAYS = 7
_RECENCY_BOOST = 0.1
_MAX_AFFINITY_BOOST = 0.25
_MAX_KEYWORD_BOOST = 0.15


def _parse_keywords(value) -> list[str]:
    """Normalize keywords (JSON string, list, or None) into a lowercase list."""
    if not value:
        return []
    if isinstance(value, list):
        raw = value
    elif isinstance(value, str):
        stripped = value.strip()
        try:
            raw = json.loads(stripped)
        except (json.JSONDecodeError, TypeError):
            raw = [stripped]
    else:
        raw = []
    keywords = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            keywords.append(item.strip().lower())
    return keywords


def _recency_bonus(published_at) -> float:
    """Return +0.1 when the article was published within the last 7 days."""
    if not published_at:
        return 0.0
    try:
        if isinstance(published_at, datetime):
            published = published_at.date()
        elif isinstance(published_at, date):
            published = published_at
        else:
            published = datetime.fromisoformat(str(published_at).replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return 0.0
    if published >= date.today() - timedelta(days=_RECENCY_DAYS):
        return _RECENCY_BOOST
    return 0.0


def _build_affinity(history: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
    """Count how often each category/source appears across a user's history."""
    category_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for record in history:
        category = record.get("category")
        if category:
            category_counts[category] = category_counts.get(category, 0) + 1
        source = record.get("source_name")
        if source:
            source_counts[source] = source_counts.get(source, 0) + 1
    return category_counts, source_counts


class ArticleRecommender(AIModule):
    def __init__(self):
        self.model = None

    async def initialize(self) -> None:
        pass

    async def process(self, data: dict, **kwargs) -> dict:
        articles = data.get("article_embeddings", [])
        user_preferences = data.get("user_preferences", {})
        reading_history = data.get("reading_history", [])
        bookmarks = data.get("bookmarks", [])

        preferred_categories = set(user_preferences.get("preferred_categories") or [])
        preferred_sources = set(user_preferences.get("preferred_sources") or [])
        preferred_languages = {
            lang.lower() for lang in (user_preferences.get("preferred_languages") or [])
        }

        read_ids = {str(h.get("article_id")) for h in reading_history}
        bookmarked_ids = {str(b.get("article_id")) for b in bookmarks}
        excluded_ids = read_ids | bookmarked_ids

        history_keywords = [
            keyword
            for record in [*reading_history, *bookmarks]
            for keyword in _parse_keywords(record.get("keywords"))
        ]
        history_keywords = list(set(history_keywords))

        category_counts, source_counts = _build_affinity([*reading_history, *bookmarks])
        total_history = max(len([*reading_history, *bookmarks]), 1)

        scored = []
        for article in articles:
            article_id = article.get("id") or article.get("article_id")
            if article_id is None or str(article_id) in excluded_ids:
                continue

            language = (article.get("language") or "").lower()
            if preferred_languages and language and language not in preferred_languages:
                continue

            score = _BASE_SCORE
            reasons = []

            category = article.get("category") or (article.get("category_name") or "")
            if category and category in preferred_categories:
                score += _CATEGORY_BOOST
                reasons.append(f"interest in {category}")
            elif category and category in category_counts:
                affinity = min(category_counts[category] / total_history, 1.0)
                boost = affinity * _MAX_AFFINITY_BOOST
                score += boost
                reasons.append(f"you read {category} articles")

            source = article.get("source_name")
            if source and source in preferred_sources:
                score += _SOURCE_BOOST
                reasons.append(f"preferred source {source}")
            elif source and source in source_counts:
                affinity = min(source_counts[source] / total_history, 1.0)
                score += affinity * 0.1
                reasons.append(f"from {source}, which you read")

            article_keywords = _parse_keywords(article.get("keywords"))
            if history_keywords and article_keywords:
                overlap = len(set(article_keywords) & set(history_keywords))
                if overlap:
                    keyword_boost = min(overlap * 0.05, _MAX_KEYWORD_BOOST)
                    score += keyword_boost
                    reasons.append("matches topics you read")

            credibility = article.get("credibility_score")
            if credibility is not None:
                try:
                    if float(credibility) > 0.7:
                        score += _CREDIBILITY_BOOST
                        reasons.append("high credibility")
                except (TypeError, ValueError):
                    pass

            view_count = article.get("view_count") or 0
            try:
                popularity = min(int(view_count) / 1000.0, 1.0)
            except (TypeError, ValueError):
                popularity = 0.0
            if popularity > 0:
                score += _POPULARITY_MAX * popularity

            score += _recency_bonus(article.get("published_at"))

            scored.append(
                {
                    "article_id": str(article_id),
                    "score": round(score, 4),
                    "reasons": reasons,
                }
            )

        scored.sort(key=lambda x: -x["score"])
        return {"recommendations": scored[: kwargs.get("limit", 20)]}

    async def cleanup(self) -> None:
        pass
