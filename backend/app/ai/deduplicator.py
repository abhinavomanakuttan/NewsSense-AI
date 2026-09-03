"""Deduplication Engine for NewsSense AI.

Handles:
- Stage 1: Exact Duplicate Detection (URL hash, Content hash, Normalized Title hash)
- Stage 2: Near Duplicate Detection (Title Token Jaccard, TF-IDF Cosine, SequenceMatcher)
- Syndication Detection (Wire signatures, text fingerprint overlap, source independence scoring)
"""

from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# Known syndication wire services and attribution signatures
WIRE_SIGNATURE_PATTERNS = [
    r"^(AP|ASSOCIATED\s+PRESS)\s*[-—–:]",
    r"^(REUTERS)\s*[-—–:]",
    r"^(AFP|AGENCE\s+FRANCE[- ]PRESSE)\s*[-—–:]",
    r"^(BLOOMBERG|BLOOMBERG\s+NEWS)\s*[-—–:]",
    r"^(PR\s+NEWSWIRE|BUSINESS\s+WIRE)\s*[-—–:]",
    r"reporting\s+by\s+[^;]+;\s*editing\s+by",
    r"\(c\)\s*\d{4}\s*(reuters|associated\s+press|bloomberg)",
    r"this\s+story\s+was\s+originally\s+published\s+by",
]


@dataclass
class DeduplicationResult:
    is_duplicate: bool
    is_near_duplicate: bool
    is_syndicated: bool
    match_type: str  # exact_duplicate, near_duplicate, syndicated, unique
    similarity_score: float
    confidence: float
    matched_article_id: str | None = None
    source_independence_score: float = 1.0
    reason: str = ""


class DeduplicationEngine:
    """Multi-stage deduplication and syndication detection engine."""

    def __init__(
        self,
        exact_title_threshold: float = 1.0,
        near_title_jaccard_threshold: float = 0.78,
        near_content_tfidf_threshold: float = 0.78,
        syndication_text_threshold: float = 0.88,
    ):
        self.exact_title_threshold = exact_title_threshold
        self.near_title_jaccard_threshold = near_title_jaccard_threshold
        self.near_content_tfidf_threshold = near_content_tfidf_threshold
        self.syndication_text_threshold = syndication_text_threshold

    # ------------------------------------------------------------------
    # Stage 1: Exact Duplicate Detection
    # ------------------------------------------------------------------

    def check_exact_duplicate(
        self,
        candidate_hashes: dict[str, str],
        existing_articles: list[dict[str, Any]],
    ) -> DeduplicationResult | None:
        """Fast O(N) in-memory or indexed hash matching."""
        cand_url_hash = candidate_hashes.get("url_hash")
        cand_content_hash = candidate_hashes.get("content_hash")
        cand_norm_title = candidate_hashes.get("normalized_title")

        for existing in existing_articles:
            ex_id = str(existing.get("id") or existing.get("article_id") or "")

            # 1. Exact URL match
            if cand_url_hash and existing.get("url_hash") == cand_url_hash:
                return DeduplicationResult(
                    is_duplicate=True,
                    is_near_duplicate=False,
                    is_syndicated=False,
                    match_type="exact_duplicate",
                    similarity_score=1.0,
                    confidence=1.0,
                    matched_article_id=ex_id,
                    source_independence_score=0.0,
                    reason="Exact URL hash match",
                )

            # 2. Exact content hash match
            if cand_content_hash and existing.get("content_hash") == cand_content_hash:
                return DeduplicationResult(
                    is_duplicate=True,
                    is_near_duplicate=False,
                    is_syndicated=False,
                    match_type="exact_duplicate",
                    similarity_score=1.0,
                    confidence=1.0,
                    matched_article_id=ex_id,
                    source_independence_score=0.0,
                    reason="Exact content hash match",
                )

            # 3. Exact normalized title match from the same domain
            if (
                cand_norm_title
                and existing.get("normalized_title") == cand_norm_title
                and existing.get("source_domain") == candidate_hashes.get("source_domain")
            ):
                return DeduplicationResult(
                    is_duplicate=True,
                    is_near_duplicate=False,
                    is_syndicated=False,
                    match_type="exact_duplicate",
                    similarity_score=1.0,
                    confidence=0.99,
                    matched_article_id=ex_id,
                    source_independence_score=0.0,
                    reason="Exact title match from same publisher",
                )

        return None

    # ------------------------------------------------------------------
    # Stage 2: Near Duplicate Detection
    # ------------------------------------------------------------------

    def check_near_duplicate(
        self,
        title: str = "",
        content: str = "",
        existing_articles: list[dict[str, Any]] | None = None,
        *,
        candidate_title: str | None = None,
        candidate_content: str | None = None,
    ) -> DeduplicationResult | None:
        """Token Jaccard, SequenceMatcher, and TF-IDF similarity checks."""
        title = candidate_title if candidate_title is not None else title
        content = candidate_content if candidate_content is not None else content
        existing_articles = existing_articles or []

        cand_tokens = set(re.findall(r"\w+", title.lower()))
        if not cand_tokens:
            return None

        best_score = 0.0
        best_match_id = None
        best_match_article = None

        for existing in existing_articles:
            ex_title = existing.get("title", "")
            ex_tokens = set(re.findall(r"\w+", ex_title.lower()))
            if not ex_tokens:
                continue

            # Title Token Jaccard similarity
            intersection = len(cand_tokens.intersection(ex_tokens))
            union = len(cand_tokens.union(ex_tokens))
            jaccard = intersection / union if union > 0 else 0.0

            # Title SequenceMatcher ratio
            seq_ratio = difflib.SequenceMatcher(None, title.lower(), ex_title.lower()).ratio()
            title_score = max(jaccard, seq_ratio)

            if title_score > best_score:
                best_score = title_score
                best_match_id = str(existing.get("id") or existing.get("article_id") or "")
                best_match_article = existing

        if best_score >= self.near_title_jaccard_threshold and best_match_article:
            # Check content similarity via TF-IDF to confirm near-duplication
            ex_content = best_match_article.get("content", "")
            content_sim = self.compute_tfidf_similarity(content[:2000], ex_content[:2000])

            combined_sim = (0.6 * best_score) + (0.4 * content_sim)
            if combined_sim >= self.near_content_tfidf_threshold:
                return DeduplicationResult(
                    is_duplicate=True,
                    is_near_duplicate=True,
                    is_syndicated=False,
                    match_type="near_duplicate",
                    similarity_score=round(combined_sim, 4),
                    confidence=round(min(1.0, combined_sim + 0.05), 4),
                    matched_article_id=best_match_id,
                    source_independence_score=0.1,
                    reason=f"Near duplicate: title_sim={best_score:.2f}, content_tfidf={content_sim:.2f}",
                )

        return None

    # ------------------------------------------------------------------
    # Stage 3: Syndication Detection
    # ------------------------------------------------------------------

    def check_syndication(
        self,
        candidate_article: dict[str, Any],
        existing_articles: list[dict[str, Any]],
    ) -> DeduplicationResult | None:
        """Detect wire service republishing (identical body, distinct publisher)."""
        cand_content = candidate_article.get("content", "")
        cand_domain = candidate_article.get("source_domain", "")
        cand_title = candidate_article.get("title", "")
        cand_has_wire_sig = self.has_wire_signature(cand_content) or self.has_wire_signature(cand_title)

        cand_head = cand_content[:1500].strip().lower()
        if len(cand_head) < 100:
            return None

        for existing in existing_articles:
            ex_domain = existing.get("source_domain", "")
            if ex_domain and cand_domain and ex_domain == cand_domain:
                continue  # Same publisher is an update or duplicate, not syndication across publishers

            ex_content = existing.get("content", "")
            ex_head = ex_content[:1500].strip().lower()
            if len(ex_head) < 100:
                continue

            # Compare text similarity between the two article bodies
            ratio = difflib.SequenceMatcher(None, cand_head[:600], ex_head[:600]).ratio()
            ex_has_wire_sig = self.has_wire_signature(ex_content) or self.has_wire_signature(existing.get("title", ""))

            # If high text overlap across different domains -> Syndicated wire story
            if ratio >= self.syndication_text_threshold or (ratio >= 0.78 and (cand_has_wire_sig or ex_has_wire_sig)):
                matched_id = str(existing.get("id") or existing.get("article_id") or "")
                independence_score = 0.2 if (cand_has_wire_sig or ratio >= 0.90) else 0.5

                return DeduplicationResult(
                    is_duplicate=False,  # Syndicated articles are linked to the event, not discarded
                    is_near_duplicate=False,
                    is_syndicated=True,
                    match_type="syndicated",
                    similarity_score=round(ratio, 4),
                    confidence=0.92 if (cand_has_wire_sig or ex_has_wire_sig) else 0.85,
                    matched_article_id=matched_id,
                    source_independence_score=independence_score,
                    reason=f"Syndicated wire content across distinct domains '{cand_domain}' and '{ex_domain}' (ratio={ratio:.2f})",
                )

        return None

    # ------------------------------------------------------------------
    # Helper Metrics
    # ------------------------------------------------------------------

    @staticmethod
    def has_wire_signature(text: str) -> bool:
        if not text:
            return False
        for pattern in WIRE_SIGNATURE_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
        return False

    @staticmethod
    def compute_tfidf_similarity(text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0
        try:
            vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", max_features=1000)
            tfidf = vectorizer.fit_transform([text1, text2])
            sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
            return float(sim)
        except Exception:
            return 0.0

    def deduplicate(self, articles: list[dict[str, Any]]) -> dict[str, Any]:
        """Convenience method: run full dedup pipeline on a list of article dicts.

        Returns a dict with:
        - unique_articles: list of articles that are not duplicates
        - duplicate_pairs: list of (original_id, duplicate_id, reason) tuples
        - duplicate_count: number of duplicates found
        - syndication_count: number of syndicated copies found
        """
        if not articles:
            return {"unique_articles": [], "duplicate_pairs": [], "duplicate_count": 0, "syndication_count": 0}

        unique_articles: list[dict[str, Any]] = []
        duplicate_pairs: list[tuple[str, str, str]] = []
        syndication_count = 0

        for article in articles:
            candidate_hashes = {
                "url_hash": article.get("url_hash") or str(hash(article.get("url", ""))),
                "content_hash": article.get("content_hash") or str(hash(article.get("content", ""))),
                "normalized_title": (article.get("title") or "").lower().strip(),
            }

            # Check against existing unique articles
            dup_result = self.check_exact_duplicate(
                candidate_hashes=candidate_hashes,
                existing_articles=unique_articles,
            )

            if dup_result and dup_result.is_duplicate:
                art_id = str(article.get("id") or article.get("article_id") or "unknown")
                matched_id = dup_result.matched_article_id or ""
                duplicate_pairs.append((art_id, matched_id, dup_result.reason))
                continue

            # Check near-duplicates
            near_dup_result = self.check_near_duplicate(
                title=article.get("title") or "",
                content=article.get("content") or article.get("summary") or "",
                existing_articles=unique_articles,
            )

            if near_dup_result and near_dup_result.is_duplicate and near_dup_result.confidence >= 0.85:
                art_id = str(article.get("id") or article.get("article_id") or "unknown")
                matched_id = near_dup_result.matched_article_id or ""
                duplicate_pairs.append((art_id, matched_id, near_dup_result.reason))
                continue

            # Check syndication across distinct publishers
            synd_result = self.check_syndication(
                candidate_article=article,
                existing_articles=unique_articles,
            )
            if synd_result and synd_result.is_syndicated:
                syndication_count += 1

            unique_articles.append(article)

        return {
            "unique_articles": unique_articles,
            "duplicate_pairs": duplicate_pairs,
            "duplicate_count": len(duplicate_pairs),
            "syndication_count": syndication_count,
        }


