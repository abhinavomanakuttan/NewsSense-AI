from app.ai.base import AIModule
from app.ai.models import ModelManager

_SENTIMENT_MODEL = "distilbert-base-uncased-finetuned-sst-2-english"


class SentimentAnalyzer(AIModule):
    def __init__(self):
        self.model = None

    async def initialize(self) -> None:
        from transformers import pipeline

        def _load():
            return pipeline("sentiment-analysis", model=_SENTIMENT_MODEL)

        self.model = ModelManager.get(f"sentiment:{_SENTIMENT_MODEL}", _load)

    async def process(self, data: dict, **kwargs) -> dict:
        text = data.get("title", "") + " " + (data.get("content", "") or "")[:512]

        if self.model is None:
            await self.initialize()

        result = self.model(text[:512])[0]

        label = result["label"].lower()
        score = result["score"]

        sentiment_map = {
            "positive": "positive",
            "negative": "negative",
            "neutral": "neutral",
        }

        return {
            "sentiment": sentiment_map.get(label, "neutral"),
            "score": round(score, 4),
            "label": label,
        }

    async def cleanup(self) -> None:
        self.model = None
