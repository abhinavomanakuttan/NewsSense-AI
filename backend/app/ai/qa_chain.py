from app.ai.base import AIModule
from app.ai.models import ModelManager
from app.core.config import settings

_QA_MODEL = "distilbert-base-cased-distilled-squad"


class QAModule(AIModule):
    def __init__(self):
        self.model = None
        self.tokenizer = None

    async def initialize(self) -> None:
        if not settings.openai_api_key:
            from transformers import pipeline

            def _load():
                return pipeline("question-answering", model=_QA_MODEL)

            self.model = ModelManager.get(f"qa:{_QA_MODEL}", _load)

    async def process(self, data: dict, **kwargs) -> dict:
        question = data.get("question", "")
        context = data.get("context", "")

        if settings.openai_api_key:
            return await self._answer_with_openai(question, context)

        if self.model is None:
            await self.initialize()
        result = self.model(question=question, context=context[:4000])
        return {
            "answer": result["answer"],
            "confidence": round(float(result["score"]), 4),
            "question": question,
            "context_length": len(context),
        }

    async def _answer_with_openai(self, question: str, context: str) -> dict:
        import httpx

        prompt = (
            f"Based on the following news articles, answer the question.\n\n"
            f"Context:\n{context[:4000]}\n\nQuestion: {question}"
        )
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.openai_model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            answer = response.json()["choices"][0]["message"]["content"]

        return {
            "answer": answer,
            "confidence": 0.8,
            "question": question,
            "context_length": len(context),
        }

    async def cleanup(self) -> None:
        self.model = None
