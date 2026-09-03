from app.ai.base import AIModule
from app.core.config import settings


class Translator(AIModule):
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self._loaded_lang: str | None = None

    async def initialize(self) -> None:
        # Default to French on first load; process() reloads for other langs.
        await self._load_for("fr")

    async def _load_for(self, lang: str) -> None:
        if self.model is not None and self._loaded_lang == lang:
            return

        from transformers import MarianMTModel, MarianTokenizer

        model_name = settings.translation_model_name.format(lang=lang)
        self.tokenizer = MarianTokenizer.from_pretrained(model_name)
        self.model = MarianMTModel.from_pretrained(model_name)
        self._loaded_lang = lang

    async def process(self, data: dict, **kwargs) -> dict:
        text = data.get("text", "")
        target_lang = kwargs.get("target_lang", "fr")

        if self.model is None:
            await self._load_for(target_lang)
        else:
            await self._load_for(target_lang)

        batch = self.tokenizer([text[:1024]], return_tensors="pt", padding=True)
        translated = self.model.generate(**batch)
        translated_text = self.tokenizer.decode(translated[0], skip_special_tokens=True)

        return {
            "original_text": text[:200],
            "translated_text": translated_text,
            "target_language": target_lang,
        }

    async def cleanup(self) -> None:
        self.model = None
        self.tokenizer = None
        self._loaded_lang = None
