"""Tests for the AI module wrappers, with model dependencies mocked.

Each module loads heavyweight ML models behind a lazy initializer; these tests
inject fakes so behavior (result shaping, fallbacks, batching, cleanup) is
verified without touching the network or loading real models.
"""

from types import SimpleNamespace

from app.ai import (
    classifier,
    credibility,
    embeddings,
    event_clusterer,
    ner,
    qa_chain,
    sentiment,
    summarizer,
    timeline,
    translator,
)
from app.ai.models import ModelManager


class FakeCallable:
    """Wraps a plain function so instances are genuinely callable."""

    def __init__(self, fn):
        self.fn = fn

    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)


def install_fake_model(monkeypatch, fake):
    monkeypatch.setattr(ModelManager, "get", lambda key, loader_fn: fake)


class TestSentimentAnalyzer:
    async def test_process_positive(self, monkeypatch):
        fake = FakeCallable(lambda text: [{"label": "POSITIVE", "score": 0.98}])
        install_fake_model(monkeypatch, fake)
        module = sentiment.SentimentAnalyzer()
        result = await module.process({"title": "Great news", "content": "All good"})
        assert result["sentiment"] == "positive"
        assert result["score"] == 0.98

    async def test_process_negative_and_neutral_labels(self, monkeypatch):
        fake = FakeCallable(lambda text: [{"label": "NEGATIVE", "score": 0.9}])
        install_fake_model(monkeypatch, fake)
        module = sentiment.SentimentAnalyzer()
        result = await module.process({"title": "Bad", "content": "Awful"})
        assert result["sentiment"] == "negative"

    async def test_unknown_label_defaults_neutral(self, monkeypatch):
        fake = FakeCallable(lambda text: [{"label": "WEIRD", "score": 0.5}])
        install_fake_model(monkeypatch, fake)
        module = sentiment.SentimentAnalyzer()
        result = await module.process({"title": "x", "content": "y"})
        assert result["sentiment"] == "neutral"

    async def test_cleanup_resets_model(self, monkeypatch):
        install_fake_model(
            monkeypatch, FakeCallable(lambda text: [{"label": "POSITIVE", "score": 1.0}])
        )
        module = sentiment.SentimentAnalyzer()
        await module.process({"title": "a", "content": "b"})
        await module.cleanup()
        assert module.model is None


class TestNewsClassifier:
    async def test_process(self, monkeypatch):
        def handle(text, candidate_labels, multi_label):
            return {
                "labels": ["technology", "science"],
                "scores": [0.95, 0.05],
            }

        fake = FakeCallable(handle)
        install_fake_model(monkeypatch, fake)
        module = classifier.NewsClassifier()
        result = await module.process({"title": "Chip breakthrough", "content": "Details"})
        assert result["category"] == "technology"
        assert result["confidence"] == 0.95
        assert result["all_scores"]["science"] == 0.05

    async def test_custom_candidate_labels(self, monkeypatch):
        def handle(text, candidate_labels, multi_label):
            return {"labels": ["tech"], "scores": [1.0]}

        fake = FakeCallable(handle)
        install_fake_model(monkeypatch, fake)
        module = classifier.NewsClassifier()
        result = await module.process({"title": "t"}, categories=["tech", "bio"])
        assert result["category"] == "tech"

    async def test_cleanup(self, monkeypatch):
        install_fake_model(
            monkeypatch, FakeCallable(lambda *a, **kw: {"labels": ["a"], "scores": [1.0]})
        )
        module = classifier.NewsClassifier()
        await module.process({"title": "t", "content": "c"})
        await module.cleanup()
        assert module.model is None and module.tokenizer is None


class TestCredibilityAssessor:
    async def test_high_reputation_likely_true(self):
        module = credibility.CredibilityAssessor()
        result = await module.process(
            {
                "article": {
                    "title": "Report",
                    "content": "According to official sources, confirmed.",
                    "content_hash": "h1",
                },
                "source": {"reputation_score": 0.9},
                "similar_articles": [
                    {"content_hash": "h2", "credibility_score": 0.8},
                    {"content_hash": "h3", "credibility_score": 0.75},
                    {"content_hash": "h4", "credibility_score": 0.9},
                    {"content_hash": "h5", "credibility_score": 0.85},
                    {"content_hash": "h6", "credibility_score": 0.8},
                ],
            }
        )
        assert result["verdict"] == "likely_true"
        assert 0.0 <= result["credibility_score"] <= 1.0
        assert len(result["factors"]) >= 2

    async def test_low_reputation_unreliable(self):
        module = credibility.CredibilityAssessor()
        result = await module.process(
            {
                "article": {"title": "Rumor", "content": "vague", "content_hash": "h1"},
                "source": {"reputation_score": 0.1},
                "similar_articles": [],
            }
        )
        assert result["verdict"] == "unreliable"

    async def test_middle_ground_needs_verification(self):
        module = credibility.CredibilityAssessor()
        result = await module.process(
            {
                "article": {"title": "Mixed", "content": "people say things", "content_hash": "h1"},
                "source": {"reputation_score": 0.5},
                "similar_articles": [],
            }
        )
        assert result["verdict"] == "needs_verification"


class FakeSpacyDoc:
    def __init__(self):
        self.ents = [
            SimpleNamespace(text="Apple", label_="ORG", start_char=0, end_char=5),
            SimpleNamespace(text="Apple", label_="ORG", start_char=10, end_char=15),
            SimpleNamespace(text="New York", label_="GPE", start_char=20, end_char=28),
        ]
        self.tokens = [
            SimpleNamespace(text="Apple", is_alpha=True, is_stop=False),
            SimpleNamespace(text="announced", is_alpha=True, is_stop=True),
            SimpleNamespace(text="acquisition", is_alpha=True, is_stop=False),
            SimpleNamespace(text="2024", is_alpha=False, is_stop=False),
        ]

    def __iter__(self):
        return iter(self.tokens)


class TestNERExtractor:
    async def test_entities_and_keywords(self, monkeypatch):
        fake_nlp = FakeCallable(lambda text: FakeSpacyDoc())
        monkeypatch.setattr(ner.spacy, "load", lambda name: fake_nlp)
        module = ner.NERExtractor()
        result = await module.process(
            {"title": "Apple news", "content": "Apple announced the acquisition."}
        )
        assert len(result["entities"]) == 2  # deduped Apple
        assert result["entity_count"] == 2
        assert "Apple" in result["keywords"]
        assert "2024" not in result["keywords"]
        assert result["entities_json"]

    async def test_uses_text_fallback(self, monkeypatch):
        fake_nlp = FakeCallable(lambda text: FakeSpacyDoc())
        monkeypatch.setattr(ner.spacy, "load", lambda name: fake_nlp)
        module = ner.NERExtractor()
        result = await module.process({"text": "just text"})
        assert result["entity_count"] == 2

    async def test_cleanup(self, monkeypatch):
        monkeypatch.setattr(ner.spacy, "load", lambda name: SimpleNamespace())
        module = ner.NERExtractor()
        await module.initialize()
        assert module.nlp is not None
        await module.cleanup()
        assert module.nlp is None


class TestNewsSummarizer:
    def _fake(self, summary_text):
        def handle(text, max_length, min_length, do_sample):
            return [{"summary_text": summary_text}]

        return FakeCallable(handle)

    async def test_short_text_unchanged(self, monkeypatch):
        install_fake_model(monkeypatch, self._fake("unused"))
        module = summarizer.NewsSummarizer()
        result = await module.process({"content": "short text here"})
        assert result["summary"] == "short text here"
        assert result["compression_ratio"] == 1.0

    async def test_long_text_uses_model(self, monkeypatch):
        install_fake_model(monkeypatch, self._fake("A concise summary."))
        module = summarizer.NewsSummarizer()
        result = await module.process({"content": "word " * 100})
        assert result["summary"] == "A concise summary."
        assert 0.0 < result["compression_ratio"] < 1.0

    async def test_process_batch(self, monkeypatch):
        install_fake_model(monkeypatch, self._fake("s"))
        module = summarizer.NewsSummarizer()
        results = await module.process_batch(["word " * 100, "word " * 100])
        assert len(results) == 2


class TestEmbeddingGenerator:
    async def test_process(self, monkeypatch):
        import numpy as np

        fake = SimpleNamespace(encode=lambda text, normalize_embeddings: np.array([0.1, 0.2, 0.3]))
        install_fake_model(monkeypatch, fake)
        module = embeddings.EmbeddingGenerator()
        result = await module.process({"title": "t", "content": "c"})
        assert result["dimension"] == 3
        assert result["embedding"] == [0.1, 0.2, 0.3]

    async def test_process_batch_returns_ndarray(self, monkeypatch):
        import numpy as np

        fake = SimpleNamespace(
            encode=lambda texts, normalize_embeddings, show_progress_bar: np.array([[0.1], [0.2]])
        )
        install_fake_model(monkeypatch, fake)
        module = embeddings.EmbeddingGenerator()
        result = await module.process_batch(["a", "b"])
        assert result.shape == (2, 1)

    async def test_compute_similarity(self, monkeypatch):
        module = embeddings.EmbeddingGenerator()
        score = await module.compute_similarity([1.0, 0.0], [0.0, 1.0])
        assert score == 0.0
        score = await module.compute_similarity([1.0, 1.0], [1.0, 1.0])
        assert score == 2.0

    async def test_cleanup(self, monkeypatch):
        import numpy as np

        fake = SimpleNamespace(encode=lambda text, normalize_embeddings: np.array([0.1]))
        install_fake_model(monkeypatch, fake)
        module = embeddings.EmbeddingGenerator()
        await module.process({"title": "t", "content": "c"})
        await module.cleanup()
        assert module.model is None


class TestTranslator:
    async def test_process_translates(self, monkeypatch):
        class FakeTokenizer:
            def __init__(self, name=None):
                self.name = name

            @staticmethod
            def from_pretrained(name):
                tok = FakeTokenizer(name)
                tok.decode = lambda ids, skip_special_tokens: "Bonjour le monde"
                return tok

            def __call__(self, texts, return_tensors, padding):
                return {"input_ids": [1, 2, 3]}

        class FakeModel:
            def __init__(self, name=None):
                self.name = name

            @staticmethod
            def from_pretrained(name):
                model = FakeModel(name)
                model.generate = lambda **batch: [[101, 102]]
                return model

        monkeypatch.setattr("transformers.MarianMTModel", FakeModel)
        monkeypatch.setattr("transformers.MarianTokenizer", FakeTokenizer)
        module = translator.Translator()
        result = await module.process({"text": "Hello world"}, target_lang="fr")
        assert result["translated_text"] == "Bonjour le monde"
        assert result["target_language"] == "fr"
        assert result["original_text"] == "Hello world"

    async def test_cleanup(self, monkeypatch):
        class FakeTokenizer:
            @staticmethod
            def from_pretrained(name):
                return FakeTokenizer()

        class FakeModel:
            @staticmethod
            def from_pretrained(name):
                return FakeModel()

        monkeypatch.setattr("transformers.MarianMTModel", FakeModel)
        monkeypatch.setattr("transformers.MarianTokenizer", FakeTokenizer)
        module = translator.Translator()
        await module.initialize()
        assert module.model is not None
        await module.cleanup()
        assert module.model is None
        assert module._loaded_lang is None


class TestEventClusterer:
    async def test_too_few_articles_single_cluster(self):
        module = event_clusterer.EventClusterer()
        result = await module.process({"articles": [{"id": "a1"}], "embeddings": [[0.1, 0.1]]})
        assert result["clusters"][0]["cluster_id"] == 0
        assert result["clusters"][0]["article_ids"] == ["a1"]

    async def test_clusters_embeddings(self):
        module = event_clusterer.EventClusterer()
        result = await module.process(
            {
                "articles": [
                    {"id": "a1", "title": "T1"},
                    {"id": "a2", "title": "T2"},
                    {"id": "a3", "title": "T3"},
                    {"id": "a4", "title": "T4"},
                ],
                "embeddings": [
                    [1.0, 0.0, 0.0],
                    [0.99, 0.01, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.99, 0.01],
                ],
            },
            eps=0.5,
        )
        assert result["total_clusters"] >= 1
        assert "parameters" in result


class TestTimelineGenerator:
    async def test_sorts_articles(self):
        module = timeline.TimelineGenerator()
        result = await module.process(
            {
                "articles": [
                    {"id": "b", "published_at": "2026-07-02", "title": "B"},
                    {"id": "a", "published_at": "2026-07-01", "title": "A"},
                ]
            }
        )
        assert result["total_events"] == 2
        assert result["timeline"][0]["title"] == "A"
        assert result["timeline"][1]["title"] == "B"
        assert result["date_range"]["start"] == "2026-07-01"
        assert result["date_range"]["end"] == "2026-07-02"

    async def test_empty_articles(self):
        module = timeline.TimelineGenerator()
        result = await module.process({"articles": []})
        assert result["total_events"] == 0
        assert result["date_range"]["start"] is None


class TestQAModule:
    async def test_local_pipeline_answer(self, monkeypatch):
        fake = FakeCallable(lambda question, context: {"answer": "42", "score": 0.9})
        install_fake_model(monkeypatch, fake)
        module = qa_chain.QAModule()
        result = await module.process({"question": "What?", "context": "The answer is 42."})
        assert result["answer"] == "42"
        assert result["confidence"] == 0.9

    async def test_openai_path(self, monkeypatch):
        monkeypatch.setattr(qa_chain.settings, "openai_api_key", "fake-key")

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": "From OpenAI"}}]}

        class FakeClient:
            def __init__(self, timeout=None):
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, **kwargs):
                return FakeResponse()

        monkeypatch.setattr("httpx.AsyncClient", FakeClient)
        module = qa_chain.QAModule()
        result = await module.process({"question": "Q", "context": "C"})
        assert result["answer"] == "From OpenAI"
        assert result["confidence"] == 0.8


class TestModelManager:
    def test_get_caches_model(self):
        ModelManager.clear()
        calls = []

        def loader():
            calls.append(1)
            return "model-instance"

        assert ModelManager.get("k", loader) == "model-instance"
        assert ModelManager.get("k", loader) == "model-instance"
        assert len(calls) == 1

    def test_clear(self):
        ModelManager.clear()
        assert ModelManager._instances == {}
