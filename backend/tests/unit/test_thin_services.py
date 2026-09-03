"""Unit tests for the thin service layer, using fake repositories.

These avoid the database entirely and instead assert that the service
orchestrates repositories and raises the documented domain exceptions.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import DuplicateError, NotFoundError, UnauthorizedError
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.category import CategoryCreateRequest
from app.schemas.reading_history import ReadingHistoryCreateRequest
from app.schemas.source import SourceCreateRequest
from app.schemas.tag import TagCreateRequest
from app.services.article_service import ArticleService
from app.services.auth_service import AuthService
from app.services.bookmark_service import BookmarkService
from app.services.category_service import CategoryService
from app.services.credibility_service import CredibilityService
from app.services.event_service import EventService
from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.services.reading_history_service import ReadingHistoryService
from app.services.source_service import SourceService
from app.services.tag_service import TagService
from app.services.user_service import UserService

NOW = datetime(2026, 7, 30, 10, 0, 0, tzinfo=UTC)
UID = uuid4()


def make_article(**overrides) -> SimpleNamespace:
    article = SimpleNamespace(
        id=UID,
        title="AI Breakthrough",
        slug="ai-breakthrough",
        url="https://news.example/ai",
        source_id=UID,
        category_id=UID,
        event_id=None,
        summary="Summary",
        content="Content",
        author="Author",
        published_at="2026-07-30T10:00:00",
        language="en",
        sentiment="positive",
        sentiment_score=0.9,
        keywords="ai,health",
        entities="[]",
        credibility_score=0.8,
        credibility_factors="{}",
        image_url=None,
        view_count="0",
        is_verified=True,
        created_at=NOW,
        updated_at=NOW,
        source=SimpleNamespace(name="Test News"),
        category=SimpleNamespace(name="Technology"),
        tags=[],
    )
    for key, value in overrides.items():
        setattr(article, key, value)
    return article


class FakeDB:
    def __init__(self):
        self.flushed = False
        self.refreshed = []

    async def flush(self):
        self.flushed = True

    async def refresh(self, obj):
        self.refreshed.append(obj)


class FakeArticleRepo:
    def __init__(self):
        self.db = FakeDB()
        self.article = make_article()

    async def get_by_slug(self, slug):
        return self.article if slug == self.article.slug else None

    async def get_all(self, *args, **kwargs):
        return [self.article]

    async def get_by_category(self, category_id, skip, limit):
        return [self.article]

    async def get_trending(self, limit):
        return [self.article]

    async def get_by_id(self, article_id):
        if not self.article:
            return None
        return self.article if article_id == self.article.id else None

    async def get_by_event_id(self, event_id):
        return [self.article]


class TestArticleService:
    async def test_get_article_increments_view_count(self):
        service = ArticleService(FakeArticleRepo())
        result = await service.get_article("ai-breakthrough")
        assert result.slug == "ai-breakthrough"
        assert result.view_count == "1"

    async def test_get_article_not_found(self):
        service = ArticleService(FakeArticleRepo())
        with pytest.raises(NotFoundError):
            await service.get_article("missing")

    async def test_get_articles_default(self):
        service = ArticleService(FakeArticleRepo())
        result = await service.get_articles()
        assert result[0].slug == "ai-breakthrough"

    async def test_get_articles_by_category(self):
        service = ArticleService(FakeArticleRepo())
        result = await service.get_articles(category=str(UID))
        assert len(result) == 1

    async def test_get_trending(self):
        service = ArticleService(FakeArticleRepo())
        result = await service.get_trending(limit=5)
        assert result[0].slug == "ai-breakthrough"


class FakeCategoryRepo:
    def __init__(self):
        self.obj = SimpleNamespace(
            id=UID,
            name="Technology",
            slug="technology",
            description=None,
            icon=None,
            parent_id=None,
            display_order="0",
        )
        self.existing = None

    async def get_all(self, order_by=None, descending=True):
        return [self.obj]

    async def get_by_slug(self, slug):
        return self.existing

    async def create(self, **kwargs):
        self.obj = SimpleNamespace(id=UID, **kwargs)
        return self.obj


class TestCategoryService:
    async def test_get_categories(self):
        service = CategoryService(FakeCategoryRepo())
        result = await service.get_categories()
        assert result[0].slug == "technology"

    async def test_get_category_not_found(self):
        repo = FakeCategoryRepo()
        repo.existing = None
        service = CategoryService(repo)
        with pytest.raises(NotFoundError):
            await service.get_category("missing")

    async def test_create_category_success(self):
        service = CategoryService(FakeCategoryRepo())
        request = CategoryCreateRequest(name="Science", slug="science")
        result = await service.create_category(request)
        assert result.name == "Science"

    async def test_create_category_duplicate(self):
        repo = FakeCategoryRepo()
        repo.existing = SimpleNamespace(slug="science")
        service = CategoryService(repo)
        with pytest.raises(DuplicateError):
            await service.create_category(CategoryCreateRequest(name="Science", slug="science"))


class FakeSourceRepo:
    def __init__(self):
        self.obj = SimpleNamespace(
            id=UID,
            name="Test News",
            url="https://news.example",
            feed_url="https://news.example/rss",
            source_type="rss",
            language="en",
            country="us",
            category=None,
            is_active=True,
            reputation_score=0.8,
            fetch_interval_minutes=30,
        )
        self.existing_by_url = None

    async def get_by_url(self, url):
        return self.existing_by_url

    async def get_by_id(self, source_id):
        return self.obj if source_id == self.obj.id else None

    async def get_all(self, skip, limit, order_by, descending):
        return [self.obj]

    async def create(self, **kwargs):
        self.obj = SimpleNamespace(id=UID, **kwargs)
        return self.obj

    async def update(self, source_id, **data):
        if source_id != self.obj.id:
            return None
        for key, value in data.items():
            setattr(self.obj, key, value)
        return self.obj

    async def delete(self, source_id):
        return source_id == self.obj.id


class TestSourceService:
    async def test_create_source_success(self):
        service = SourceService(FakeSourceRepo())
        request = SourceCreateRequest(name="New", url="https://new.example", source_type="rss")
        result = await service.create_source(request)
        assert result.name == "New"

    async def test_create_source_duplicate(self):
        repo = FakeSourceRepo()
        repo.existing_by_url = SimpleNamespace(url="https://new.example")
        service = SourceService(repo)
        with pytest.raises(DuplicateError):
            await service.create_source(
                SourceCreateRequest(name="New", url="https://new.example", source_type="rss")
            )

    async def test_get_source(self):
        service = SourceService(FakeSourceRepo())
        result = await service.get_source(UID)
        assert result.name == "Test News"

    async def test_get_source_not_found(self):
        service = SourceService(FakeSourceRepo())
        with pytest.raises(NotFoundError):
            await service.get_source(uuid4())

    async def test_get_sources(self):
        service = SourceService(FakeSourceRepo())
        result = await service.get_sources()
        assert result[0].url == "https://news.example"

    async def test_update_source(self):
        service = SourceService(FakeSourceRepo())
        result = await service.update_source(UID, {"name": "Renamed"})
        assert result.name == "Renamed"

    async def test_update_source_not_found(self):
        service = SourceService(FakeSourceRepo())
        with pytest.raises(NotFoundError):
            await service.update_source(uuid4(), {"name": "Renamed"})

    async def test_delete_source(self):
        service = SourceService(FakeSourceRepo())
        await service.delete_source(UID)

    async def test_delete_source_not_found(self):
        service = SourceService(FakeSourceRepo())
        with pytest.raises(NotFoundError):
            await service.delete_source(uuid4())


class FakeTagRepo:
    def __init__(self):
        self.obj = SimpleNamespace(id=UID, name="AI", slug="ai")
        self.existing = None

    async def get_all(self, order_by=None, descending=True):
        return [self.obj]

    async def get_by_slug(self, slug):
        return self.existing

    async def create(self, **kwargs):
        self.obj = SimpleNamespace(id=UID, **kwargs)
        return self.obj


class TestTagService:
    async def test_get_tags(self):
        service = TagService(FakeTagRepo())
        result = await service.get_tags()
        assert result[0].slug == "ai"

    async def test_create_tag_success(self):
        service = TagService(FakeTagRepo())
        result = await service.create_tag(TagCreateRequest(name="AI", slug="ai"))
        assert result.name == "AI"

    async def test_create_tag_duplicate(self):
        repo = FakeTagRepo()
        repo.existing = SimpleNamespace(slug="ai")
        service = TagService(repo)
        with pytest.raises(DuplicateError):
            await service.create_tag(TagCreateRequest(name="AI", slug="ai"))


class FakeEventRepo:
    def __init__(self):
        self.obj = SimpleNamespace(
            id=UID,
            title="Event",
            slug="event",
            summary=None,
            description=None,
            category_id=None,
            start_date=None,
            end_date=None,
            article_count="0",
            importance_score=0.5,
            timeline=None,
            is_active=True,
            created_at=NOW,
        )

    async def get_by_slug(self, slug):
        return self.obj if slug == self.obj.slug else None

    async def get_active_events(self, limit):
        return [self.obj]


class TestEventService:
    async def test_get_event(self):
        service = EventService(FakeEventRepo(), FakeArticleRepo())
        result = await service.get_event("event")
        assert result.slug == "event"

    async def test_get_event_not_found(self):
        service = EventService(FakeEventRepo(), FakeArticleRepo())
        with pytest.raises(NotFoundError):
            await service.get_event("missing")

    async def test_get_events(self):
        service = EventService(FakeEventRepo(), FakeArticleRepo())
        result = await service.get_events()
        assert len(result) == 1

    async def test_get_event_articles(self):
        service = EventService(FakeEventRepo(), FakeArticleRepo())
        result = await service.get_event_articles(UID)
        assert result[0].title == "AI Breakthrough"


class FakeUserRepo:
    def __init__(self):
        self.user = SimpleNamespace(
            id=UID,
            email="u@test.com",
            username="user",
            full_name="User",
            avatar_url=None,
            role="user",
            is_active=True,
            is_verified=True,
        )

    async def get_by_id(self, user_id):
        return self.user if user_id == self.user.id else None

    async def update(self, user_id, **data):
        if user_id != self.user.id:
            return None
        for key, value in data.items():
            setattr(self.user, key, value)
        return self.user


class FakePreferenceRepo:
    def __init__(self):
        self.db = FakeDB()
        self.prefs = SimpleNamespace(
            preferred_categories=[],
            preferred_sources=[],
            preferred_languages=["en"],
            preferred_regions=[],
            notification_enabled=True,
            dark_mode=False,
            email_digest_frequency="daily",
        )

    async def get_or_create(self, user_id):
        return self.prefs


class TestUserService:
    async def test_get_profile(self):
        service = UserService(FakeUserRepo(), FakePreferenceRepo())
        result = await service.get_profile(UID)
        assert result.email == "u@test.com"

    async def test_get_profile_not_found(self):
        service = UserService(FakeUserRepo(), FakePreferenceRepo())
        with pytest.raises(NotFoundError):
            await service.get_profile(uuid4())

    async def test_update_profile(self):
        service = UserService(FakeUserRepo(), FakePreferenceRepo())
        result = await service.update_profile(UID, {"full_name": "Updated"})
        assert result.full_name == "Updated"

    async def test_get_preferences(self):
        service = UserService(FakeUserRepo(), FakePreferenceRepo())
        result = await service.get_preferences(UID)
        assert result.preferred_languages == ["en"]

    async def test_update_preferences(self):
        service = UserService(FakeUserRepo(), FakePreferenceRepo())
        result = await service.update_preferences(
            UID, {"notification_enabled": False, "dark_mode": True}
        )
        assert result.notification_enabled is False
        assert result.dark_mode is True


class FakeBookmarkRepo:
    def __init__(self):
        self.bookmarked = False
        self.removed = False
        self.obj = SimpleNamespace(
            id=UID,
            user_id=UID,
            article_id=UID,
            created_at=NOW,
            article=make_article(),
        )

    async def is_bookmarked(self, user_id, article_id):
        return self.bookmarked

    async def create(self, **kwargs):
        return self.obj

    async def remove_bookmark(self, user_id, article_id):
        return self.removed

    async def get_user_bookmarks(self, user_id, skip, limit):
        return [self.obj]


class TestBookmarkService:
    async def test_add_bookmark_success(self):
        repo = FakeBookmarkRepo()
        service = BookmarkService(repo, FakeArticleRepo())
        result = await service.add_bookmark(UID, UID)
        assert result.user_id == UID

    async def test_add_bookmark_article_not_found(self):
        article_repo = FakeArticleRepo()
        article_repo.article = None
        service = BookmarkService(FakeBookmarkRepo(), article_repo)
        with pytest.raises(NotFoundError):
            await service.add_bookmark(UID, UID)

    async def test_add_bookmark_duplicate(self):
        repo = FakeBookmarkRepo()
        repo.bookmarked = True
        service = BookmarkService(repo, FakeArticleRepo())
        with pytest.raises(DuplicateError):
            await service.add_bookmark(UID, UID)

    async def test_remove_bookmark(self):
        repo = FakeBookmarkRepo()
        repo.removed = True
        service = BookmarkService(repo, FakeArticleRepo())
        await service.remove_bookmark(UID, UID)

    async def test_remove_bookmark_not_found(self):
        service = BookmarkService(FakeBookmarkRepo(), FakeArticleRepo())
        with pytest.raises(NotFoundError):
            await service.remove_bookmark(UID, UID)

    async def test_get_bookmarks(self):
        service = BookmarkService(FakeBookmarkRepo(), FakeArticleRepo())
        result = await service.get_bookmarks(UID)
        assert result[0].user_id == UID


class FakeHistoryRepo:
    def __init__(self):
        self.db = FakeDB()
        self.existing = None
        self.record = SimpleNamespace(
            id=UID,
            article_id=UID,
            read_duration_seconds=10,
            scroll_depth=50,
            created_at=NOW,
            article=make_article(),
        )
        self.removed = True

    async def get_by_user_and_article(self, user_id, article_id):
        return self.existing

    async def create(self, **kwargs):
        return self.record

    async def get_user_history(self, user_id, skip=0, limit=50):
        return [self.record]

    async def count_user_history(self, user_id):
        return 1

    async def delete(self, record_id):
        return True

    async def remove_user_record(self, user_id, history_id):
        return self.removed


class TestReadingHistoryService:
    def build(self):
        return ReadingHistoryService(FakeHistoryRepo(), article_repo=FakeArticleRepo())

    async def test_record_reading_new(self):
        service = self.build()
        result = await service.record_reading(
            UID, ReadingHistoryCreateRequest(article_id=UID, read_duration_seconds=10)
        )
        assert result.read_duration_seconds == 10

    async def test_record_reading_accumulates(self):
        service = self.build()
        service.history_repo.existing = service.history_repo.record
        result = await service.record_reading(
            UID,
            ReadingHistoryCreateRequest(article_id=UID, read_duration_seconds=5, scroll_depth=80),
        )
        assert result.read_duration_seconds == 15
        assert result.scroll_depth == 80

    async def test_record_reading_article_not_found(self):
        repo = FakeArticleRepo()
        repo.article = None
        service = ReadingHistoryService(FakeHistoryRepo(), article_repo=repo)
        with pytest.raises(NotFoundError):
            await service.record_reading(
                UID, ReadingHistoryCreateRequest(article_id=UID, read_duration_seconds=5)
            )

    async def test_get_history(self):
        service = self.build()
        result = await service.get_history(UID)
        assert result.total == 1
        assert result.items[0].read_duration_seconds == 10

    async def test_clear_history(self):
        service = self.build()
        count = await service.clear_history(UID)
        assert count == 1

    async def test_remove_record(self):
        service = self.build()
        await service.remove_record(UID, UID)

    async def test_remove_record_not_found(self):
        service = self.build()
        service.history_repo.removed = False
        with pytest.raises(NotFoundError):
            await service.remove_record(UID, UID)


class FakeAuthUserRepo:
    def __init__(self):
        self.user = SimpleNamespace(
            id=UID,
            email="u@test.com",
            username="user",
            hashed_password="hashed",
            role="user",
            is_active=True,
        )
        self.by_email = None
        self.by_username = None

    async def get_by_email(self, email):
        return self.by_email

    async def get_by_username(self, username):
        return self.by_username

    async def create(self, **kwargs):
        self.user = SimpleNamespace(id=UID, **kwargs)
        return self.user

    async def get_by_id(self, user_id):
        return self.user if user_id == self.user.id else None


class TestAuthService:
    async def test_register_success(self):
        service = AuthService(FakeAuthUserRepo())
        result = await service.register(
            RegisterRequest(email="new@test.com", username="new", password="Pass123!")
        )
        assert result["message"] == "User registered successfully"
        assert result["email"] == "new@test.com"

    async def test_register_duplicate_email(self):
        repo = FakeAuthUserRepo()
        repo.by_email = SimpleNamespace(email="new@test.com")
        service = AuthService(repo)
        with pytest.raises(DuplicateError):
            await service.register(
                RegisterRequest(email="new@test.com", username="new", password="Pass123!")
            )

    async def test_register_duplicate_username(self):
        repo = FakeAuthUserRepo()
        repo.by_username = SimpleNamespace(username="new")
        service = AuthService(repo)
        with pytest.raises(DuplicateError):
            await service.register(
                RegisterRequest(email="new@test.com", username="new", password="Pass123!")
            )

    async def test_login_invalid_credentials(self, monkeypatch):
        service = AuthService(FakeAuthUserRepo())
        with pytest.raises(UnauthorizedError):
            await service.login(LoginRequest(email="u@test.com", password="wrong"))

    async def test_login_inactive_account(self, monkeypatch):
        repo = FakeAuthUserRepo()
        repo.by_email = repo.user
        repo.user.is_active = False

        async def fake_verify(password, hashed):
            return True

        monkeypatch.setattr("app.services.auth_service.verify_password", fake_verify)
        service = AuthService(repo)
        with pytest.raises(UnauthorizedError):
            await service.login(LoginRequest(email="u@test.com", password="right"))

    async def test_login_success(self, monkeypatch):
        repo = FakeAuthUserRepo()
        repo.by_email = repo.user

        async def fake_verify(password, hashed):
            return True

        def fake_create_token(data):
            return "signed-token"

        monkeypatch.setattr("app.services.auth_service.verify_password", fake_verify)
        monkeypatch.setattr("app.services.auth_service.create_access_token", fake_create_token)
        monkeypatch.setattr("app.services.auth_service.create_refresh_token", fake_create_token)

        service = AuthService(repo)
        result = await service.login(LoginRequest(email="u@test.com", password="right"))
        assert result.access_token == "signed-token"
        assert result.refresh_token == "signed-token"

    async def test_refresh_token_wrong_type(self, monkeypatch):
        service = AuthService(FakeAuthUserRepo())

        def fake_decode(token):
            return {"type": "access", "sub": str(UID)}

        monkeypatch.setattr("app.services.auth_service.decode_token", fake_decode)
        with pytest.raises(UnauthorizedError):
            await service.refresh_token("token")

    async def test_refresh_token_inactive_user(self, monkeypatch):
        repo = FakeAuthUserRepo()
        repo.user.is_active = False

        def fake_decode(token):
            return {"type": "refresh", "sub": str(UID)}

        monkeypatch.setattr("app.services.auth_service.decode_token", fake_decode)
        service = AuthService(repo)
        with pytest.raises(UnauthorizedError):
            await service.refresh_token("token")

    async def test_refresh_token_success(self, monkeypatch):
        repo = FakeAuthUserRepo()

        def fake_decode(token):
            return {"type": "refresh", "sub": str(UID)}

        def fake_create_token(data):
            return "fresh-token"

        monkeypatch.setattr("app.services.auth_service.decode_token", fake_decode)
        monkeypatch.setattr("app.services.auth_service.create_access_token", fake_create_token)
        monkeypatch.setattr("app.services.auth_service.create_refresh_token", fake_create_token)

        service = AuthService(repo)
        result = await service.refresh_token("token")
        assert result.access_token == "fresh-token"


class TestCredibilityService:
    async def test_assess_article(self):
        service = CredibilityService()
        result = await service.assess_article(str(UID))
        assert result["article_id"] == str(UID)
        assert "factors" in result
        assert result["verdict"] in ("likely_true", "needs_verification", "unreliable")


class TestPipelineOrchestrator:
    async def test_all_steps_succeed(self):
        orchestrator = PipelineOrchestrator()

        async def step_a(data):
            return {"a": data["x"] + 1}

        async def step_b(data):
            return {"b": data["a"] * 2}

        orchestrator.add_step("a", step_a).add_step("b", step_b)
        results = await orchestrator.execute({"x": 1})
        assert results["a"]["status"] == "success"
        assert results["b"]["status"] == "success"
        assert results["b"]["output"] == {"b": 4}

    async def test_failing_step_stops_pipeline(self):
        orchestrator = PipelineOrchestrator()

        async def step_ok(data):
            return {"ok": True}

        async def step_bad(data):
            raise ValueError("boom")

        async def step_never(data):
            raise AssertionError("should not run")

        orchestrator.add_step("ok", step_ok)
        orchestrator.add_step("bad", step_bad)
        orchestrator.add_step("never", step_never)

        results = await orchestrator.execute({})
        assert results["ok"]["status"] == "success"
        assert results["bad"]["status"] == "failed"
        assert results["bad"]["error"] == "boom"
        assert "never" not in results
