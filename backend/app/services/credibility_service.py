class CredibilityService:
    def __init__(self):
        pass

    async def assess_article(self, article_id: str) -> dict:
        factors = []
        score = 0.5

        factors.append(
            {
                "factor": "source_reputation",
                "score": 0.7,
                "detail": "Source has moderate reputation",
            }
        )
        factors.append(
            {"factor": "has_multiple_sources", "score": 0.6, "detail": "Partially corroborated"}
        )

        score = sum(f["score"] for f in factors) / len(factors)

        return {
            "article_id": article_id,
            "credibility_score": round(score, 2),
            "factors": factors,
            "verdict": "likely_true"
            if score > 0.7
            else "needs_verification"
            if score > 0.4
            else "unreliable",
        }
