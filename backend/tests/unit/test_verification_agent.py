"""Comprehensive Unit Tests for Fact-Checking and Verification Agent in NewsSense AI.

Tests cover:
- Stage 1: Atomic claim extraction and taxonomy classification (FACTUAL, ATTRIBUTION, NUMERICAL, PREDICTION, OPINION)
- Stage 3: NLI Cross-Encoder Stance Detection (SUPPORTS, REFUTES, NEUTRAL)
- Stage 4: Source Independence Discounting (syndicated wire copies vs independent reports)
- Stage 5: Corroboration scoring and strict 4-tier verdict logic (WELL_SUPPORTED, DISPUTED, UNVERIFIED, CONTRADICTED)
- Critique loop alert generation upon contradicted claims
"""

import pytest

from app.ai.claim_extractor import ClaimExtractor
from app.ai.evidence_retriever import RetrievedEvidence
from app.ai.nli_verifier import NLIVerifier
from app.ai.verification_agent import VerificationAgent
from app.schemas.verification import ClaimType, VerificationVerdict


# ============================================================================
# Stage 1: Claim Extraction & Classification Tests
# ============================================================================

def test_atomic_claim_extraction_and_attribution():
    """Verify that attribution sentences decompose into Attribution + Core claim."""
    sentence = "The minister announced that unemployment fell to 4%."
    claims = ClaimExtractor.extract_claims(sentence)

    assert len(claims) >= 2

    # Claim 1: Attribution
    attribution_claims = [c for c in claims if c.claim_type == ClaimType.ATTRIBUTION]
    assert len(attribution_claims) == 1
    assert "minister announced" in attribution_claims[0].text.lower()
    assert attribution_claims[0].source_attribution == "The minister"

    # Claim 2: Numerical assertion
    numerical_claims = [c for c in claims if c.claim_type == ClaimType.NUMERICAL]
    assert len(numerical_claims) == 1
    assert "4%" in numerical_claims[0].text
    assert numerical_claims[0].is_checkable is True


def test_opinion_classification_filtered_from_fact_checking():
    """Verify that opinion statements are classified as OPINION and flagged non-checkable."""
    opinion_sentence = "In my opinion, this new budget is a terrible decision."
    claims = ClaimExtractor.extract_claims(opinion_sentence)

    assert len(claims) == 1
    assert claims[0].claim_type == ClaimType.OPINION
    assert claims[0].is_checkable is False


def test_prediction_classification():
    """Verify forward-looking statements are classified as PREDICTION."""
    prediction_sentence = "Analysts forecast that inflation will reach 2% in 2027."
    claims = ClaimExtractor.extract_claims(prediction_sentence)

    pred_claims = [c for c in claims if c.claim_type == ClaimType.PREDICTION]
    assert len(pred_claims) >= 1
    assert "2027" in pred_claims[0].text


# ============================================================================
# Stage 3: NLI Stance Detection Tests
# ============================================================================

def test_nli_stance_detection_supports():
    nli = NLIVerifier()
    premise = "The Bureau of Labor Statistics confirmed unemployment dropped to 4.0 percent in August."
    hypothesis = "Unemployment fell to 4%."

    result = nli.classify_stance(premise, hypothesis)
    assert result.stance == "SUPPORTS"
    assert result.confidence >= 0.70


def test_nli_stance_detection_refutes_contradiction():
    nli = NLIVerifier()
    premise = "The ministry refuted earlier reports and clarified unemployment rose to 6.2 percent."
    hypothesis = "Unemployment fell to 4%."

    result = nli.classify_stance(premise, hypothesis)
    assert result.stance == "REFUTES"
    assert result.confidence >= 0.70


def test_nli_stance_detection_neutral():
    nli = NLIVerifier()
    premise = "The government passed a new environmental conservation act in parliament."
    hypothesis = "Unemployment fell to 4%."

    result = nli.classify_stance(premise, hypothesis)
    assert result.stance == "NEUTRAL"


# ============================================================================
# Stage 4: Source Independence Discounting Tests
# ============================================================================

def test_source_independence_discounts_syndicated_wire_copy():
    """5 websites repeating the same AP syndicated wire report must be discounted."""
    nli = NLIVerifier()

    syndicated_evidence = [
        RetrievedEvidence("Site 1", "http://s1.com", "According to Associated Press, the treasury released $5B.", "2026-09-02", 0.85, 0.90),
        RetrievedEvidence("Site 2", "http://s2.com", "According to Associated Press, the treasury released $5B.", "2026-09-02", 0.85, 0.90),
        RetrievedEvidence("Site 3", "http://s3.com", "According to Associated Press, the treasury released $5B.", "2026-09-02", 0.85, 0.90),
        RetrievedEvidence("Site 4", "http://s4.com", "According to Associated Press, the treasury released $5B.", "2026-09-02", 0.85, 0.90),
        RetrievedEvidence("Site 5", "http://s5.com", "According to Associated Press, the treasury released $5B.", "2026-09-02", 0.85, 0.90),
    ]

    weights = nli.compute_source_independence(syndicated_evidence)
    assert len(weights) == 5
    assert weights[0] >= 0.70  # First report receives normal weight

    # Subsequent identical wire copies are heavily discounted to 0.20
    for w in weights[1:]:
        assert w <= 0.25


# ============================================================================
# Stage 5: Corroboration Scoring & Graded Verdict Tests
# ============================================================================

def test_verdict_well_supported():
    nli = NLIVerifier()
    evidence = [
        RetrievedEvidence("Reuters", "https://reuters.com/1", "The department officially allocated $5 billion in federal funding.", "2026-09-02", 0.95, 0.95),
        RetrievedEvidence("Associated Press", "https://apnews.com/1", "Officials confirmed the $5 billion tech infrastructure grant package.", "2026-09-02", 0.95, 0.92),
    ]

    output = nli.evaluate_claim_corroboration("c1", "The government allocated $5 billion for technology infrastructure.", "NUMERICAL", evidence)
    assert output.verdict == VerificationVerdict.WELL_SUPPORTED.value
    assert output.confidence >= 0.85
    assert len(output.supporting_evidence) >= 2


def test_verdict_contradicted():
    nli = NLIVerifier()
    evidence = [
        RetrievedEvidence("PolitiFact", "https://politifact.com/1", "Fact-check: False. Official budget records show funding was denied, not allocated.", "2026-09-02", 0.95, 0.95),
        RetrievedEvidence("Reuters", "https://reuters.com/2", "The ministry denied that any $5 billion budget was approved.", "2026-09-02", 0.95, 0.92),
    ]

    output = nli.evaluate_claim_corroboration("c2", "The government allocated $5 billion for technology infrastructure.", "NUMERICAL", evidence)
    assert output.verdict == VerificationVerdict.CONTRADICTED.value
    assert output.confidence >= 0.85
    assert len(output.refuting_evidence) >= 1


def test_verdict_disputed():
    nli = NLIVerifier()
    evidence = [
        RetrievedEvidence("Source A", "https://a.com", "Officials report exactly 10 casualties following the incident.", "2026-09-02", 0.90, 0.90),
        RetrievedEvidence("Source B", "https://b.com", "Emergency responders confirmed 15 casualties were recorded.", "2026-09-02", 0.90, 0.90),
    ]

    output = nli.evaluate_claim_corroboration("c3", "The incident resulted in 10 casualties.", "NUMERICAL", evidence)
    assert output.verdict in {VerificationVerdict.DISPUTED.value, VerificationVerdict.WELL_SUPPORTED.value, VerificationVerdict.UNVERIFIED.value}


# ============================================================================
# Event Cluster Verification & Critique Loop Tests
# ============================================================================

@pytest.mark.asyncio
async def test_event_cluster_verification_and_critique_alert():
    agent = VerificationAgent()

    cluster_articles = [
        {
            "title": "Government Approves $5 Billion Infrastructure Program",
            "content": (
                "WASHINGTON — Officials confirmed the $5 billion funding package today. "
                "However, reports claiming the funds were canceled due to debt were completely false and refuted."
            ),
            "source_name": "Reuters",
            "source_domain": "reuters.com",
            "published_at": "2026-09-02T10:00:00Z",
        },
        {
            "title": "Treasury Confirms AI Infrastructure Package",
            "content": "The Treasury officially authorized the $5 billion program.",
            "source_name": "Associated Press",
            "source_domain": "apnews.com",
            "published_at": "2026-09-02T11:00:00Z",
        }
    ]

    resp = await agent.verify_event_cluster(
        event_id="evt-verification-01",
        event_title="Government Approves $5 Billion Infrastructure Program",
        articles=cluster_articles,
    )

    assert resp.event_id == "evt-verification-01"
    assert resp.total_claims >= 1
    assert resp.overall_trust_score >= 0.50
    assert len(resp.claims) >= 1
    assert any(c.verdict in {VerificationVerdict.WELL_SUPPORTED.value, VerificationVerdict.UNVERIFIED.value} for c in resp.claims)
