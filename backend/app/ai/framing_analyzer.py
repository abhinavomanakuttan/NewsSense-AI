"""Discourse Profiler, Narrative Classifier, and Omission Matrix for Media Framing Analysis."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# Lexical dictionaries for media framing and discourse analysis
EMOTIONAL_TERMS = {
    "disaster", "catastrophe", "triumph", "historic", "bombshell", "scandal",
    "breakthrough", "fiasco", "chaotic", "devastating", "heroic", "tyranny",
    "reckless", "furious", "outrage", "blunder", "nightmare", "miracle",
    "spectacular", "abysmal", "shameless", "vicious", "unprecedented", "slammed",
    "blasted", "gutted", "crippled", "crushed", "humiliated", "glorious"
}

SENSATIONAL_TERMS = {
    "shocking", "insane", "unbelievable", "massive blow", "bombshell", "earthquake",
    "panic", "mayhem", "chaos", "explodes", "meltdown", "warfare", "bloodbath",
    "stunner", "jaw-dropping", "wild", "unhinged", "nightmare scenario"
}

HIGH_CERTAINTY_TERMS = {
    "definitely", "undoubtedly", "certainly", "proven", "undeniable",
    "unquestionably", "incontestable", "conclusive", "guaranteed", "confirmed"
}

HEDGING_TERMS = {
    "allegedly", "reportedly", "purportedly", "claimed", "claims", "rumored",
    "suggests", "could", "might", "potentially", "apparent", "purported",
    "unverified", "unconfirmed", "unclear"
}

FRAME_KEYWORDS = {
    "GOVERNMENT_ACHIEVEMENT": [
        "launches", "unveils", "achieves", "breakthrough", "ambitious", "milestone",
        "delivers", "triumph", "leads", "success", "record", "celebrates", "victory",
        "pioneering", "progress", "championed"
    ],
    "CONTROVERSY_AND_CRITICISM": [
        "criticism", "criticized", "faces pushback", "controversial", "backlash", "slammed",
        "blasted", "under fire", "dispute", "protest", "protesters", "opposition",
        "rebuke", "outcry", "condemned", "condemnation", "condemns", "clashes"
    ],
    "POLICY_AND_TECHNICAL_DETAILS": [
        "rules", "regulations", "taxation", "provision", "statute", "clause",
        "amendment", "technical", "percentage", "rate", "framework", "mechanism",
        "stipulates", "criteria", "guidelines", "compliance", "restructuring"
    ],
    "ECONOMIC_AND_BUSINESS_IMPACT": [
        "inflation", "recession", "gdp", "markets", "stocks", "wall street", "costs",
        "investors", "interest rates", "unemployment", "fiscal", "spending", "deficit",
        "consumers", "supply chain", "revenue", "profits"
    ],
    "HUMAN_INTEREST_AND_VICTIMS": [
        "families", "victims", "struggling", "survivors", "ordinary citizens",
        "grassroots", "plight", "heartbreaking", "personal story", "impacted residents",
        "vulnerable", "workers", "children", "patients"
    ],
    "CRISIS_AND_SECURITY": [
        "threat", "emergency", "crisis", "disaster", "security", "warning", "evacuation",
        "casualty", "fatal", "investigation", "police", "military", "collapse"
    ],
    "ACCOUNTABILITY_AND_ETHICS": [
        "investigation", "ethics", "probe", "subpoena", "scandal", "corruption",
        "transparency", "oversight", "watchdog", "conflict of interest", "allegations"
    ]
}


@dataclass
class DiscourseProfile:
    primary_frame: str
    narrative_emphasis: str
    emotional_intensity: float
    sensationalism_score: float
    active_voice_ratio: float
    certainty_level: str
    tone: str
    sentiment: str
    quoted_actors: list[str]
    dominant_topics: list[str]


class SourceDiscourseProfiler:
    """Extracts empirical media framing and linguistic traits from an article."""

    @classmethod
    def profile_article(cls, headline: str, lead_paragraph: str, full_content: str = "") -> DiscourseProfile:
        combined_text = f"{headline}. {lead_paragraph}. {full_content[:1500]}".lower()
        words = re.findall(r"\b\w+\b", combined_text)
        word_count = max(len(words), 1)

        # 1. Emotional intensity
        emotional_count = sum(1 for w in words if w in EMOTIONAL_TERMS)
        emotional_intensity = round(min(1.0, (emotional_count / word_count) * 6.0), 2)

        # 2. Sensationalism score
        sensational_count = sum(1 for w in words if w in SENSATIONAL_TERMS)
        headline_sensational = sum(1 for term in SENSATIONAL_TERMS if term in headline.lower())
        exclamations = headline.count("!") + lead_paragraph.count("!")
        sensationalism_score = round(min(1.0, (sensational_count * 0.2) + (headline_sensational * 0.35) + (exclamations * 0.2)), 2)

        # 3. Epistemic Certainty
        certainty_count = sum(1 for w in words if w in HIGH_CERTAINTY_TERMS)
        hedging_count = sum(1 for w in words if w in HEDGING_TERMS)
        if hedging_count > certainty_count + 1:
            certainty_level = "hedged/speculative"
        elif certainty_count > hedging_count + 1:
            certainty_level = "high"
        else:
            certainty_level = "moderate"

        # 4. Voice and Transitivity (Passive voice detection: be + past participle)
        # Matches forms: was/were/been/is/are + verb ending in ed/en
        passive_matches = re.findall(r"\b(?:is|are|was|were|been|being)\s+([a-z]+(?:ed|en))\b", combined_text)
        total_clauses = max(len(re.split(r"[.,;]", combined_text)), 1)
        passive_ratio = min(1.0, len(passive_matches) / total_clauses)
        active_voice_ratio = round(1.0 - (passive_ratio * 0.8), 2)

        # 5. Quoted Actors and Direct Attribution
        quotes = re.findall(r'["“]([^"”]{8,150})["”]', f"{lead_paragraph} {full_content[:2000]}")
        quoted_actors = cls._extract_quoted_actors(lead_paragraph, full_content)

        # 6. Dominant Frame and Narrative Emphasis
        primary_frame, narrative_emphasis = cls._classify_frame(headline, lead_paragraph, combined_text)

        # 7. Tone and Sentiment
        tone, sentiment = cls._classify_tone_and_sentiment(headline, primary_frame, emotional_intensity, sensationalism_score)

        # 8. Dominant Topics
        dominant_topics = cls._extract_dominant_topics(combined_text)

        return DiscourseProfile(
            primary_frame=primary_frame,
            narrative_emphasis=narrative_emphasis,
            emotional_intensity=emotional_intensity,
            sensationalism_score=sensationalism_score,
            active_voice_ratio=active_voice_ratio,
            certainty_level=certainty_level,
            tone=tone,
            sentiment=sentiment,
            quoted_actors=quoted_actors,
            dominant_topics=dominant_topics,
        )

    @classmethod
    def _classify_frame(cls, headline: str, lead: str, combined: str) -> tuple[str, str]:
        """Classify dominant narrative frame with double weight on the headline."""
        scores: dict[str, float] = {k: 0.0 for k in FRAME_KEYWORDS}
        h_low = headline.lower()
        l_low = lead.lower()

        for frame, keywords in FRAME_KEYWORDS.items():
            for kw in keywords:
                if kw in h_low:
                    scores[frame] += 3.0  # High emphasis in headline
                if kw in l_low:
                    scores[frame] += 1.5  # High emphasis in lead
                if kw in combined:
                    scores[frame] += 0.5

        best_frame = max(scores, key=scores.get)
        if scores[best_frame] < 1.0:
            best_frame = "POLICY_AND_TECHNICAL_DETAILS"

        # Formulate grounded narrative emphasis description
        emphasis_map = {
            "GOVERNMENT_ACHIEVEMENT": "Emphasizes policy implementation as an institutional milestone and success",
            "CONTROVERSY_AND_CRITICISM": "Emphasizes public dissent, opposition pushback, and controversial aspects",
            "POLICY_AND_TECHNICAL_DETAILS": "Emphasizes structural mechanisms, statutory provisions, and regulatory details",
            "ECONOMIC_AND_BUSINESS_IMPACT": "Emphasizes macroeconomic effects, fiscal costs, and commercial impacts",
            "HUMAN_INTEREST_AND_VICTIMS": "Emphasizes personal narratives, societal stakeholders, and lived impacts",
            "CRISIS_AND_SECURITY": "Emphasizes institutional threats, emergency hazards, and security concerns",
            "ACCOUNTABILITY_AND_ETHICS": "Emphasizes investigative scrutiny, ethical compliance, and administrative oversight",
        }
        narrative_emphasis = emphasis_map.get(best_frame, "Emphasizes general event developments")
        return best_frame, narrative_emphasis

    @classmethod
    def _classify_tone_and_sentiment(
        cls, headline: str, frame: str, emotional_intensity: float, sensationalism_score: float
    ) -> tuple[str, str]:
        """Classify tone and sentiment based on empirical linguistic features."""
        if sensationalism_score >= 0.40 or emotional_intensity >= 0.75:
            tone = "sensationalist_emotive"
        elif frame == "CONTROVERSY_AND_CRITICISM":
            tone = "critical_skeptical"
        elif frame == "GOVERNMENT_ACHIEVEMENT":
            tone = "congratulatory_promotional"
        elif frame == "CRISIS_AND_SECURITY":
            tone = "urgent_alarmist"
        else:
            tone = "objective_analytical"

        # Sentiment determination
        if frame in {"GOVERNMENT_ACHIEVEMENT"}:
            sentiment = "positive"
        elif frame in {"CONTROVERSY_AND_CRITICISM", "CRISIS_AND_SECURITY"}:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return tone, sentiment

    @classmethod
    def _extract_quoted_actors(cls, lead: str, content: str) -> list[str]:
        """Detect attributed speakers and stakeholders quoted in the article."""
        actors = []
        attribution_patterns = [
            r'(?:said|stated|argued|claimed|noted|announced|explained)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+(?:said|stated|argued|claimed|added|warned)',
            r'according to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})',
        ]
        sample_text = f"{lead}. {content[:2000]}"
        for pattern in attribution_patterns:
            matches = re.findall(pattern, sample_text)
            for m in matches:
                clean_m = m.strip()
                if len(clean_m) > 3 and clean_m not in actors and clean_m.lower() not in {"the", "this", "that", "these", "those", "when", "after"}:
                    actors.append(clean_m)

        if not actors:
            # Fallback to key capitalized entities
            caps = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", lead)
            actors = [c for c in caps if len(c) > 4][:2]

        return actors[:4]

    @classmethod
    def _extract_dominant_topics(cls, text: str) -> list[str]:
        """Extract dominant topical keywords."""
        stopwords = {
            "the", "and", "for", "that", "this", "with", "from", "have", "were",
            "said", "their", "will", "would", "about", "after", "which", "could",
            "been", "also", "into", "more", "first", "other", "some", "time", "than"
        }
        words = [w for w in re.findall(r"\b[a-z]{4,}\b", text) if w not in stopwords]
        counts: dict[str, int] = {}
        for w in words:
            counts[w] = counts.get(w, 0) + 1

        sorted_words = sorted(counts, key=counts.get, reverse=True)
        return sorted_words[:4]


class OmissionMatrixBuilder:
    """Builds fact emphasis vs omission differential across sources."""

    @classmethod
    def analyze_facts(
        cls,
        source_text: str,
        all_articles: list[dict[str, Any]],
        verified_claims: list[str] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Identify key facts reported by this source vs facts reported elsewhere but omitted here."""
        s_low = source_text.lower()

        # Build master fact pool from verified claims and other articles
        candidate_facts: set[str] = set()
        if verified_claims:
            candidate_facts.update(verified_claims)

        for a in all_articles:
            title = a.get("title", "")
            if title:
                candidate_facts.add(title)

        key_facts: list[str] = []
        omitted_facts: list[str] = []

        for fact in candidate_facts:
            # Extract distinctive content words (len > 4)
            words = [w.lower() for w in re.findall(r"\b\w+\b", fact) if len(w) > 4]
            if not words:
                continue

            matches = sum(1 for w in words if w in s_low)
            ratio = matches / len(words)

            if ratio >= 0.50:
                key_facts.append(fact)
            elif ratio <= 0.15:
                omitted_facts.append(fact)

        return key_facts[:3], omitted_facts[:3]


class CrossSourceSynthesizer:
    """Synthesizes areas of agreement, areas of difference, and framing patterns."""

    @classmethod
    def synthesize_event(
        cls,
        comparisons: list[dict[str, Any]],
        event_title: str,
    ) -> tuple[list[str], list[str], list[str], list[str]]:
        """Generate consensus facts, areas of divergence, framing patterns, and language patterns."""
        if not comparisons:
            return [], [], [], []

        # 1. Areas of Agreement (Common factual core)
        agreement = [
            f"All sources report on the core event: '{event_title}'.",
        ]
        # Check shared entities
        shared_entities = set.intersection(*[set(c.get("entities_emphasized", [])) for c in comparisons if c.get("entities_emphasized")]) if len(comparisons) > 1 else set()
        if shared_entities:
            agreement.append(f"Unanimous consensus in reporting on key entities: {', '.join(sorted(shared_entities))}.")

        # 2. Areas of Difference (Observable coverage differentials)
        differences = []
        frames_seen = {c.get("source"): c.get("framing_features", {}).get("primary_frame") for c in comparisons}
        tones_seen = {c.get("source"): c.get("tone") for c in comparisons}

        sources = list(frames_seen.keys())
        if len(sources) >= 2:
            s1, s2 = sources[0], sources[1]
            f1, f2 = frames_seen[s1], frames_seen[s2]
            if f1 != f2:
                differences.append(f"{s1} emphasizes {f1.lower().replace('_', ' ')}, whereas {s2} focuses on {f2.lower().replace('_', ' ')}.")
            else:
                differences.append(f"{s1} and {s2} both adopt a {f1.lower().replace('_', ' ')} frame but select distinct quoted sources.")

        for c in comparisons:
            omitted = c.get("omitted_or_less_emphasized_facts", [])
            if omitted:
                differences.append(f"{c.get('source')} downplays or omits reference to: '{omitted[0]}'.")

        # 3. Framing Patterns
        framing_patterns = []
        for src, frame in frames_seen.items():
            framing_patterns.append(f"{src} contextualizes the event primarily through {frame.lower().replace('_', ' ')}.")

        # 4. Language Patterns
        language_patterns = []
        for c in comparisons:
            ff = c.get("framing_features", {})
            src = c.get("source")
            intensity = ff.get("emotional_intensity", 0.0)
            voice = ff.get("active_voice_ratio", 0.8)
            certainty = ff.get("certainty_level", "high")

            if intensity >= 0.40:
                language_patterns.append(f"{src} employs emotionally loaded adjectives and emotive modifiers (intensity: {intensity}).")
            else:
                language_patterns.append(f"{src} maintains restrained, descriptive lexical choices (intensity: {intensity}).")

            if voice < 0.70:
                language_patterns.append(f"{src} displays elevated passive voice usage, deflecting explicit agency.")

        return agreement[:3], differences[:4], framing_patterns[:4], language_patterns[:4]
