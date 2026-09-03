from app.ai.base import AIModule
from app.ai.models import ModelManager
from app.core.config import settings


class NewsClassifier(AIModule):
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.categories = [
            "politics",
            "business",
            "technology",
            "science",
            "health",
            "sports",
            "entertainment",
            "world",
            "environment",
            "education",
            "crime",
            "weather",
        ]

    async def initialize(self) -> None:
        from transformers import pipeline

        def _load():
            return pipeline(
                "zero-shot-classification",
                model=settings.classification_model_name,
                device=-1,
            )

        self.model = ModelManager.get(f"classifier:{settings.classification_model_name}", _load)

    async def process(self, data: dict, **kwargs) -> dict:
        text = data.get("title", "") + " " + (data.get("content", "") or "")
        candidate_labels = kwargs.get("categories", self.categories)

        if self.model is None:
            await self.initialize()

        result = self.model(text, candidate_labels, multi_label=False)
        top_category = result["labels"][0]
        confidence = result["scores"][0]

        return {
            "category": top_category,
            "confidence": round(confidence, 4),
            "all_scores": dict(zip(result["labels"], result["scores"], strict=True)),
        }

    async def cleanup(self) -> None:
        self.model = None
        self.tokenizer = None
