"""Unit tests for Bias & Media Framing Agent in NewsSense AI.

Validates:
- Cross-publisher headline & lead framing contrast detection
- Linguistic discourse profiling (emotional terms, sensationalism, voice, certainty)
- Selective fact emphasis vs omission detection
- Political safeguard enforcement (prohibition of crude ideological labels)
- Comprehensive multi-source event framing synthesis
"""

import pytest

from app.ai.framing_agent import FramingAgent
from app.ai.framing_analyzer import SourceDiscourseProfiler


# ============================================================================
# Headline & Lead Framing Classification Tests
# ============================================================================

def test_headline_framing_classification_triad():
    """Verify that different editorial angles on the SAME event are mapped to distinct narrative frames."""
    profiler = SourceDiscourseProfiler()

    # Source A: Focus on milestone / leadership
    p_a = profiler.profile_article(
        headline="Government launches ambitious reform",
        lead_paragraph="The administration officially unveiled its flagship legislative program today.",
    )
    assert p_a.primary_frame == "GOVERNMENT_ACHIEVEMENT"
    assert p_a.tone == "congratulatory_promotional"
    assert p_a.sentiment == "positive"

    # Source B: Focus on dissent / controversy
    p_b = profiler.profile_article(
        headline="Government faces criticism over controversial reform",
        lead_paragraph="Opposition leaders and advocacy groups slammed the controversial package today.",
    )
    assert p_b.primary_frame == "CONTROVERSY_AND_CRITICISM"
    assert p_b.tone == "critical_skeptical"
    assert p_b.sentiment == "negative"

    # Source C: Focus on technical / policy details
    p_c = profiler.profile_article(
        headline="New reform changes taxation rules and fiscal criteria",
        lead_paragraph="The new statutory guidelines establish revised percentage rates and compliance criteria.",
    )
    assert p_c.primary_frame == "POLICY_AND_TECHNICAL_DETAILS"
    assert p_c.tone == "objective_analytical"
    assert p_c.sentiment == "neutral"


# ============================================================================
# Linguistic Discourse & Stylistic Profiling Tests
# ============================================================================

def test_discourse_profiler_emotional_and_sensational_language():
    """Detect presence of emotionally loaded terms and sensational adjectives."""
    profiler = SourceDiscourseProfiler()

    sensational_text = (
        "In a shocking and catastrophic disaster, the chaotic and devastating collapse "
        "sparked pure outrage across Wall Street!"
    )
    profile = profiler.profile_article(
        headline="Shocking and Catastrophic Disaster Sparks Outrage!",
        lead_paragraph=sensational_text,
    )

    assert profile.emotional_intensity >= 0.40
    assert profile.sensationalism_score >= 0.40
    assert profile.tone == "sensationalist_emotive"


def test_epistemic_certainty_and_hedging_detection():
    """Distinguish between high epistemic certainty and hedged speculative phrasing."""
    profiler = SourceDiscourseProfiler()

    hedged_profile = profiler.profile_article(
        headline="Minister Allegedly Involved in Unverified Talks",
        lead_paragraph="Reports suggest the official reportedly participated in rumored negotiations, unconfirmed sources say.",
    )
    assert hedged_profile.certainty_level == "hedged/speculative"

    certain_profile = profiler.profile_article(
        headline="Official Undeniably Confirms Agreement",
        lead_paragraph="The department conclusively proven and confirmed that the statutory agreement is definitely settled.",
    )
    assert certain_profile.certainty_level == "high"


def test_voice_transitivity_passive_vs_active():
    """Verify passive voice detection where agency is deflected."""
    profiler = SourceDiscourseProfiler()

    passive_profile = profiler.profile_article(
        headline="Protesters Dispersed in Capitol Square",
        lead_paragraph="Crowds were dispersed and tear gas was deployed as demonstrators were arrested.",
    )
    # Elevated passive constructions reduce active_voice_ratio
    assert passive_profile.active_voice_ratio <= 0.85


# ============================================================================
# Political News Safeguards Tests
# ============================================================================

def test_political_safeguards_prohibits_ideological_slurs():
    """The agent must strictly avoid labeling sources as 'left-wing', 'right-wing', or 'biased'."""
    agent = FramingAgent()

    test_input = "Source A shows left-wing and conservative bias in its reporting."
    clean = agent._enforce_safeguards(test_input)

    assert "left-wing" not in clean
    assert "conservative bias" not in clean
    assert "divergent editorial perspective" in clean


# ============================================================================
# Full Multi-Source Event Framing Synthesis Tests
# ============================================================================

def test_multi_source_event_framing_synthesis():
    agent = FramingAgent()

    event_articles = [
        {
            "source_name": "Government Gazette",
            "title": "Government launches ambitious green energy reform",
            "content": "WASHINGTON — The administration celebrated the launch of its $10 billion clean energy initiative.",
        },
        {
            "source_name": "Watchdog Daily",
            "title": "Administration faces criticism over controversial energy bill costs",
            "content": "WASHINGTON — Industry representatives slammed the controversial bill, citing massive economic costs.",
        },
        {
            "source_name": "Fiscal Monitor",
            "title": "New energy statute amends regulatory emissions rules",
            "content": "The federal framework establishes new emissions compliance criteria and statutory deadlines.",
        }
    ]

    verified_claims = [
        "The administration announced a $10 billion clean energy initiative.",
        "The legislation establishes revised emissions compliance criteria."
    ]

    response = agent.analyze_event_framing(
        event_id="evt-framing-101",
        event_title="Federal Clean Energy Legislation Overhaul",
        articles=event_articles,
        verified_claims=verified_claims,
    )

    assert response.event_id == "evt-framing-101"
    assert len(response.sources) == 3
    assert len(response.comparisons) == 3
    assert response.confidence >= 0.80

    # Verify per-source frames
    frames = {c.source: c.framing_features.primary_frame for c in response.comparisons}
    assert frames["Government Gazette"] == "GOVERNMENT_ACHIEVEMENT"
    assert frames["Watchdog Daily"] == "CONTROVERSY_AND_CRITICISM"
    assert frames["Fiscal Monitor"] == "POLICY_AND_TECHNICAL_DETAILS"

    # Verify synthesis
    assert len(response.areas_of_agreement) >= 1
    assert len(response.areas_of_difference) >= 1
    assert len(response.framing_patterns) >= 1
    assert len(response.language_patterns) >= 1
