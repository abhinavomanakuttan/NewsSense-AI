import asyncio

from app.core.security import hash_password
from app.db.session import async_session_factory
from app.repositories.category_repository import CategoryRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.user_repository import UserRepository


async def seed():
    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        source_repo = SourceRepository(session)
        category_repo = CategoryRepository(session)

        admin = await user_repo.get_by_email("admin@smartfeed.ai")
        if not admin:
            admin = await user_repo.create(
                email="admin@smartfeed.ai",
                username="admin",
                hashed_password=hash_password("admin123"),
                full_name="System Admin",
                role="admin",
                is_verified=True,
            )
            print(f"Created admin user: {admin.id}")

        categories = [
            {"name": "Politics", "slug": "politics", "description": "Political news and analysis"},
            {"name": "Technology", "slug": "technology", "description": "Tech industry news"},
            {"name": "Business", "slug": "business", "description": "Business and finance"},
            {"name": "Science", "slug": "science", "description": "Scientific discoveries"},
            {"name": "Health", "slug": "health", "description": "Health and medical news"},
            {"name": "Sports", "slug": "sports", "description": "Sports coverage"},
            {"name": "Entertainment", "slug": "entertainment", "description": "Entertainment news"},
            {"name": "World", "slug": "world", "description": "International news"},
            {"name": "Environment", "slug": "environment", "description": "Environmental news"},
            {"name": "Education", "slug": "education", "description": "Education news"},
        ]

        for cat in categories:
            existing = await category_repo.get_by_slug(cat["slug"])
            if not existing:
                await category_repo.create(**cat)
                print(f"Created category: {cat['name']}")

        sources = [
            {
                "name": "BBC News",
                "url": "https://www.bbc.com/news",
                "feed_url": "http://feeds.bbci.co.uk/news/rss.xml",
                "source_type": "rss",
                "language": "en",
                "country": "gb",
                "reputation_score": 0.9,
            },
            {
                "name": "Reuters",
                "url": "https://www.reuters.com",
                "feed_url": "https://www.reuters.com/tools/rss",
                "source_type": "rss",
                "language": "en",
                "country": "us",
                "reputation_score": 0.95,
            },
            {
                "name": "Associated Press",
                "url": "https://apnews.com",
                "feed_url": "https://feeds.apnews.com/apnews",
                "source_type": "rss",
                "language": "en",
                "country": "us",
                "reputation_score": 0.9,
            },
            {
                "name": "TechCrunch",
                "url": "https://techcrunch.com",
                "feed_url": "https://techcrunch.com/feed/",
                "source_type": "rss",
                "language": "en",
                "country": "us",
                "reputation_score": 0.7,
            },
            {
                "name": "The Guardian",
                "url": "https://www.theguardian.com",
                "feed_url": "https://www.theguardian.com/world/rss",
                "source_type": "rss",
                "language": "en",
                "country": "gb",
                "reputation_score": 0.85,
            },
        ]

        for src in sources:
            existing = await source_repo.get_by_url(src["url"])
            if not existing:
                await source_repo.create(**src)
                print(f"Created source: {src['name']}")

        await session.commit()
        print("Seed completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
