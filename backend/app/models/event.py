import json
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Event(Base, TimestampMixin, UUIDMixin):
    __tablename__ = "events"

    title = Column(String(500), nullable=False)
    slug = Column(String(500), unique=True, nullable=False, index=True)
    summary = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    category_id = Column(String(50), nullable=True)
    category = Column(String(50), nullable=True)
    subcategories = Column(Text, nullable=True)  # JSON list: ["AI", "Government Policy"]
    entities = Column(Text, nullable=True)  # JSON dict/list: {"PER": [...], "ORG": [...]}
    locations = Column(Text, nullable=True)  # JSON list: ["Washington, D.C.", "Geneva"]
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    article_count = Column(String(10), default="0", nullable=False)
    source_count = Column(Integer, default=1, nullable=False)
    independent_source_count = Column(Float, default=1.0, nullable=False)
    importance_score = Column(Float, default=0.0, nullable=False)
    embedding = Column(Text, nullable=True)  # JSON float list of centroid embedding
    status = Column(String(50), default="active", nullable=False)  # active, flagged_verification, resolved, archived
    timeline = Column(Text, nullable=True)  # JSON list of update objects: [{time, article_id, type, note}]
    structured_summary = Column(Text, nullable=True)  # JSON representation of EventSummaryOutput
    is_active = Column(Boolean, default=True, nullable=False)

    # Canonical aliases & properties
    @property
    def event_id(self):
        return self.id

    @property
    def canonical_title(self) -> str:
        return self.title

    @canonical_title.setter
    def canonical_title(self, value: str):
        self.title = value

    @property
    def start_time(self):
        return self.start_date

    @start_time.setter
    def start_time(self, value):
        self.start_date = value

    @property
    def latest_update(self):
        return self.end_date

    @latest_update.setter
    def latest_update(self, value):
        self.end_date = value

    @property
    def importance(self) -> float:
        return self.importance_score

    @importance.setter
    def importance(self, value: float):
        self.importance_score = value

    @property
    def article_ids(self) -> list[str]:
        from sqlalchemy import inspect
        state = inspect(self)
        if "articles" not in state.unloaded:
            articles = self.__dict__.get("articles")
            if articles:
                return [str(a.id) for a in articles]
        return []

    def get_timeline_list(self) -> list[dict]:
        if not self.timeline:
            return []
        try:
            return json.loads(self.timeline)
        except Exception:
            return []

    def append_timeline_event(self, timestamp: str, article_id: str, event_type: str, note: str):
        tl = self.get_timeline_list()
        tl.append({
            "timestamp": timestamp,
            "article_id": article_id,
            "type": event_type,
            "note": note,
        })
        self.timeline = json.dumps(tl)
