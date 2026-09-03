"""Multi-Channel Evidence Retrieval Module for NewsSense AI.

Stage 2: For every claim retrieve external & internal evidence from:
- Google Fact Check Tools API
- Multi-source news corpus (cluster articles & internal database)
- Authoritative / official news search
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievedEvidence:
    source_name: str
    url: str | None
    passage: str
    publication_date: str | None
    source_reliability: float
    retrieval_score: float
    is_factcheck_database: bool = False


class EvidenceRetriever:
    """Retrieves relevant evidence passages for a claim across multiple channels."""

    AUTHORITATIVE_SOURCES = {
        "reuters.com": 0.95,
        "apnews.com": 0.95,
        "bloomberg.com": 0.92,
        "bbc.com": 0.92,
        "afp.com": 0.94,
        "wsj.com": 0.90,
        "who.int": 0.98,
        "cdc.gov": 0.98,
        "bls.gov": 0.99,
        "politifact.com": 0.95,
        "factcheck.org": 0.95,
        "snopes.com": 0.92,
    }

    @classmethod
    async def retrieve_evidence(
        cls,
        claim_text: str,
        cluster_articles: list[dict[str, Any]] | None = None,
        max_passages: int = 6,
    ) -> list[RetrievedEvidence]:
        """Retrieve evidence passages from fact check databases and multi-source corpus."""
        evidence_list: list[RetrievedEvidence] = []

        # 1. Query Google Fact Check Tools API if online
        factcheck_results = await cls._query_google_factcheck(claim_text)
        evidence_list.extend(factcheck_results)

        # 2. Query Multi-source cluster articles
        if cluster_articles:
            corpus_results = cls._retrieve_from_cluster(claim_text, cluster_articles)
            evidence_list.extend(corpus_results)

        # 3. Deduplicate by passage snippet
        seen_snippets = set()
        deduped: list[RetrievedEvidence] = []
        for ev in evidence_list:
            snip = ev.passage[:40].lower()
            if snip not in seen_snippets:
                seen_snippets.add(snip)
                deduped.append(ev)

        # Sort by relevance & reliability
        deduped.sort(key=lambda x: (x.retrieval_score * 0.6 + x.source_reliability * 0.4), reverse=True)
        return deduped[:max_passages]

    @classmethod
    async def _query_google_factcheck(cls, query: str) -> list[RetrievedEvidence]:
        """Query Google Fact Check Tools API if an API key is configured."""
        api_key = getattr(settings, "google_factcheck_api_key", None)
        if not api_key:
            return []

        results: list[RetrievedEvidence] = []
        try:
            url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
            params = {"query": query, "languageCode": "en", "key": api_key}
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    claims = data.get("claims", [])
                    for c in claims[:3]:
                        reviews = c.get("claimReview", [])
                        for r in reviews:
                            publisher = r.get("publisher", {}).get("name", "Fact-Checker")
                            rating = r.get("textualRating", "Fact Check Review")
                            title = r.get("title") or c.get("text") or ""
                            url_ref = r.get("url")

                            passage = f"Fact-check assessment by {publisher}: {rating}. Details: {title}"
                            results.append(
                                RetrievedEvidence(
                                    source_name=publisher,
                                    url=url_ref,
                                    passage=passage,
                                    publication_date=r.get("reviewDate"),
                                    source_reliability=0.95,
                                    retrieval_score=0.90,
                                    is_factcheck_database=True,
                                )
                            )
        except Exception as exc:
            logger.debug("Google Fact Check API query skipped: %s", exc)

        return results

    @classmethod
    def _retrieve_from_cluster(cls, claim_text: str, articles: list[dict[str, Any]]) -> list[RetrievedEvidence]:
        """Extract high-relevance paragraphs from multi-source articles in the event cluster."""
        results: list[RetrievedEvidence] = []
        claim_terms = set(re.findall(r"\w+", claim_text.lower()))

        for art in articles:
            publisher = art.get("source_name") or art.get("publisher") or "Corpus Source"
            domain = art.get("source_domain") or art.get("domain") or ""
            pub_date = str(art.get("published_at") or "")
            url = art.get("url")
            reliability = cls._calculate_source_reliability(publisher, domain)

            content = art.get("content") or art.get("summary") or ""
            paragraphs = [p.strip() for p in re.split(r"\n+|(?:(?<=[.!?])\s+(?=[A-Z]))", content) if len(p.strip()) > 30]

            for para in paragraphs:
                para_terms = set(re.findall(r"\w+", para.lower()))
                if not para_terms:
                    continue

                overlap = len(claim_terms.intersection(para_terms))
                if overlap >= 2:
                    score = min(0.98, overlap / max(len(claim_terms), 1) + 0.3)
                    results.append(
                        RetrievedEvidence(
                            source_name=publisher,
                            url=url,
                            passage=para,
                            publication_date=pub_date,
                            source_reliability=reliability,
                            retrieval_score=round(score, 2),
                            is_factcheck_database=False,
                        )
                    )

        return results

    @classmethod
    def _calculate_source_reliability(cls, publisher: str, domain: str) -> float:
        """Assign baseline credibility based on domain reputation."""
        d_lower = domain.lower()
        p_lower = publisher.lower()

        for auth_d, score in cls.AUTHORITATIVE_SOURCES.items():
            if auth_d in d_lower or auth_d.split(".")[0] in p_lower:
                return score

        return 0.80  # Baseline for general news publications
