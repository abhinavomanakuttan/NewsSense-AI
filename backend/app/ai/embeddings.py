import numpy as np

from app.ai.base import AIModule
from app.ai.models import ModelManager
from app.core.config import settings


class EmbeddingGenerator(AIModule):
    def __init__(self):
        self.model = None

    async def initialize(self) -> None:
        from sentence_transformers import SentenceTransformer

        def _load():
            return SentenceTransformer(settings.embedding_model_name)

        self.model = ModelManager.get(f"embeddings:{settings.embedding_model_name}", _load)

    async def process(self, data: dict, **kwargs) -> dict:
        text = data.get("content") or data.get("text", "")
        title = data.get("title", "")

        if self.model is None:
            await self.initialize()

        combined = title + " " + text[:8192]
        embedding = self.model.encode(combined, normalize_embeddings=True)

        return {
            "embedding": embedding.tolist(),
            "dimension": len(embedding),
            "model": settings.embedding_model_name,
        }

    async def process_batch(self, texts: list[str]) -> np.ndarray:
        if self.model is None:
            await self.initialize()
        return self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    async def compute_similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
        a = np.array(embedding1)
        b = np.array(embedding2)
        return float(np.dot(a, b))

    async def cleanup(self) -> None:
        self.model = None
