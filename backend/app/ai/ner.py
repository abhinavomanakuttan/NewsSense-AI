import json

import spacy

from app.ai.base import AIModule
from app.core.config import settings


class NERExtractor(AIModule):
    def __init__(self):
        self.nlp = None

    async def initialize(self) -> None:
        self.nlp = spacy.load(settings.ner_model_name)

    async def process(self, data: dict, **kwargs) -> dict:
        text = data.get("content") or data.get("text", "")
        title = data.get("title", "")

        if self.nlp is None:
            await self.initialize()

        combined = title + ". " + text[:10000]
        doc = self.nlp(combined)

        entities = []
        seen = set()
        for ent in doc.ents:
            key = f"{ent.text}:{ent.label_}"
            if key not in seen:
                entities.append(
                    {
                        "text": ent.text,
                        "label": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char,
                    }
                )
                seen.add(key)

        keywords = [
            token.text
            for token in doc
            if token.is_alpha and not token.is_stop and len(token.text) > 2
        ]
        keyword_freq = {}
        for kw in keywords:
            keyword_freq[kw] = keyword_freq.get(kw, 0) + 1

        top_keywords = sorted(keyword_freq.items(), key=lambda x: -x[1])[:20]

        return {
            "entities": entities,
            "keywords": [kw for kw, _ in top_keywords],
            "entity_count": len(entities),
            "entities_json": json.dumps(entities),
            "keywords_json": json.dumps([kw for kw, _ in top_keywords]),
        }

    async def cleanup(self) -> None:
        self.nlp = None
