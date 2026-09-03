from app.ai.base import AIModule


class CredibilityAssessor(AIModule):
    def __init__(self):
        self.model = None

    async def initialize(self) -> None:
        pass

    async def process(self, data: dict, **kwargs) -> dict:
        article = data.get("article", {})
        source = data.get("source", {})
        similar_articles = data.get("similar_articles", [])

        factors = []
        score = 0.5

        source_reputation = source.get("reputation_score", 0.5)
        factors.append({"name": "source_reputation", "score": source_reputation, "weight": 0.3})
        score += (source_reputation - 0.5) * 0.6

        corroboration_count = len(similar_articles)
        corroboration_score = min(corroboration_count / 5, 1.0)
        factors.append(
            {"name": "cross_source_corroboration", "score": corroboration_score, "weight": 0.25}
        )
        score += corroboration_score * 0.1

        content = article.get("title", "") + " " + (article.get("content", "") or "")
        has_specifies = any(
            word in content.lower()
            for word in ["according to", "reported", "confirmed", "official"]
        )
        specificity_score = 0.8 if has_specifies else 0.4
        factors.append({"name": "specificity", "score": specificity_score, "weight": 0.2})
        score += (specificity_score - 0.5) * 0.1

        has_verification = any(
            a.get("content_hash") != article.get("content_hash")
            and a.get("credibility_score", 0) > 0.7
            for a in similar_articles
        )
        if has_verification:
            factors.append({"name": "verified_by_trusted_source", "score": 1.0, "weight": 0.25})
            score += 0.1

        final_score = max(0.0, min(1.0, score))

        if final_score >= 0.7:
            verdict = "likely_true"
        elif final_score >= 0.4:
            verdict = "needs_verification"
        else:
            verdict = "unreliable"

        return {
            "credibility_score": round(final_score, 2),
            "verdict": verdict,
            "factors": factors,
            "explanation": f"Credibility score of {round(final_score, 2)} based on source reputation ({source_reputation}), "
            f"cross-source corroboration ({corroboration_count} related articles), "
            f"and content specificity.",
        }

    async def cleanup(self) -> None:
        pass
