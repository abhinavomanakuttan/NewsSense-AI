from sqlalchemy import Boolean, Column, Float, ForeignKey, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

article_tags = Table(
    "article_tags",
    Base.metadata,
    Column(
        "article_id",
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id", UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    ),
)


class Article(Base, TimestampMixin, UUIDMixin):
    __tablename__ = "articles"

    title = Column(String(500), nullable=False)
    slug = Column(String(500), unique=True, nullable=False, index=True)
    url = Column(String(1000), unique=True, nullable=False)
    source_id = Column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    category_id = Column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    event_id = Column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL"), nullable=True
    )
    source_name = Column(String(255), nullable=True)
    category_name = Column(String(50), nullable=True)
    discovered_at = Column(String(50), nullable=True)
    content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=False, index=True)
    normalized_title = Column(String(500), nullable=True, index=True)
    url_hash = Column(String(64), nullable=True, index=True)
    source_hash = Column(String(64), nullable=True, index=True)
    article_fingerprint = Column(String(64), nullable=True, index=True)
    country = Column(String(5), nullable=True)
    raw_metadata = Column(Text, nullable=True)  # JSON blob of original source metadata
    author = Column(String(255), nullable=True)
    published_at = Column(String(50), nullable=True)
    language = Column(String(10), default="en", nullable=False)
    sentiment = Column(String(20), nullable=True)
    sentiment_score = Column(Float, nullable=True)
    keywords = Column(Text, nullable=True)
    entities = Column(Text, nullable=True)
    embedding_id = Column(String(100), nullable=True)
    is_duplicate = Column(Boolean, default=False, nullable=False)
    duplicate_of_id = Column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )
    is_syndicated = Column(Boolean, default=False, nullable=False)
    source_independence_score = Column(Float, default=1.0, nullable=False)
    match_type = Column(String(50), nullable=True)  # exact_duplicate, near_duplicate, syndicated, event_match, new_event
    credibility_score = Column(Float, nullable=True)
    credibility_factors = Column(Text, nullable=True)
    image_url = Column(String(1000), nullable=True)
    view_count = Column(String(10), default="0", nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    source = relationship("Source", backref="articles")
    category = relationship("Category", backref="articles")
    event = relationship("Event", backref="articles")
    tags = relationship("Tag", secondary=article_tags, backref="articles")

    @property
    def article_id(self):
        return self.id

    @property
    def description(self):
        return self.summary

    @description.setter
    def description(self, value):
        self.summary = value



class ArticleTag(Base):
    __table__ = article_tags
