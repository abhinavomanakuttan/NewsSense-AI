# AI-Powered News Intelligence Platform — Architecture Document

## 1. System Overview

A production-ready platform that aggregates news from multiple sources, processes it with AI,
and delivers personalized intelligent news experiences through a web interface and chatbot.

### Core Capabilities
- **Multi-source ingestion** (RSS, News APIs, government sites, etc.)
- **AI processing pipeline** (classification, summarization, NER, embeddings, clustering)
- **Personalized feeds** based on user preferences, history, and trending topics
- **Semantic & keyword search** via Elasticsearch + vector embeddings
- **Credibility assessment** with transparent confidence scoring
- **RAG chatbot** answering questions strictly from retrieved news content
- **Admin dashboard** for monitoring, analytics, and source management

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Next.js  │  │  Mobile  │  │    API   │  │  Admin   │   │
│  │   Web    │  │   App    │  │  Clients │  │  Panel   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼──────────────┼─────────────┼──────────────┼────────┘
        │              │             │              │
        ▼              ▼             ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│                  API Gateway / Load Balancer                 │
│                         (Nginx)                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Presentation Layer                         │
│              FastAPI + WebSockets + REST                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   Auth   │  │  News    │  │  Search  │  │  Chat    │   │
│  │  Routes  │  │  Routes  │  │  Routes  │  │  Routes  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Auth    │  │  News    │  │  Recs    │  │  Chat    │   │
│  │ Service  │  │ Service  │  │ Service  │  │ Service  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │Analytics │  │Credibility│  │Pipeline  │                   │
│  │ Service  │  │ Service   │  │Orchestr. │                   │
│  └──────────┘  └──────────┘  └──────────┘                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Repository Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  User    │  │  Article │  │   Event  │  │  Source  │   │
│  │  Repo    │  │  Repo    │  │   Repo   │  │  Repo    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Store Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │PostgreSQL│  │  Redis   │  │  Qdrant  │  │Elastic   │   │
│  │ (Rel.)   │  │ (Cache)  │  │(Vectors) │  │ (Search) │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐                                               │
│  │   S3     │                                               │
│  │ (Object) │                                               │
│  └──────────┘                                               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Data Pipeline Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Celery   │  │RabbitMQ  │  │  AI      │  │  ETL     │   │
│  │ Workers  │  │ (Broker) │  │  Modules  │  │  Tasks   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Technology Choices with Rationale

| Component          | Technology        | Why                                                                 |
|--------------------|-------------------|---------------------------------------------------------------------|
| Frontend           | Next.js 14        | SSR, ISR, file-based routing, React ecosystem                       |
| UI Framework       | Tailwind + Shadcn | Utility-first CSS, accessible components, dark mode built-in        |
| Backend            | FastAPI (Python)  | Async, auto-docs, Pydantic validation, high performance             |
| Database           | PostgreSQL 16     | ACID, JSONB, full-text search, robust ecosystem                     |
| Cache              | Redis 7           | Sub-millisecond reads, session store, rate limiting, pub/sub        |
| Vector DB          | Qdrant            | Written in Rust, fast, filtering, rich metadata support             |
| Search             | Elasticsearch 8   | Full-text, faceted search, relevance scoring, aggregation           |
| Queue              | Celery            | Distributed task queue, beat scheduler, proven reliability           |
| Message Broker     | RabbitMQ          | Reliable, persistent, supports complex routing patterns             |
| Embeddings         | sentence-transformers | State-of-the-art semantic embeddings (all-MiniLM-L6-v2)        |
| Classification     | Transformers      | Fine-tuned BART/RoBERTa models for zero/few-shot classification     |
| Summarization      | Transformers      | BART-large-CNN for abstractive summarization                        |
| NER                | spaCy + Transformers | Production-grade entity extraction                             |
| Translation        | Hugging Face MarianMT | Open-source, supports 100+ languages                           |
| LLM Orchestration  | LangChain         | Standardized interface for RAG, chains, tool use                    |
| Object Storage     | MinIO (S3-compat.)| Self-hosted, S3 API compatible, scalable                            |
| Containerization   | Docker + Compose  | Reproducible environments, microservice orchestration               |
| CI/CD              | GitHub Actions    | Native integration, matrix builds, caching                          |

---

## 4. Data Flow

```
                    ┌─────────────────┐
                    │  External       │
                    │  News Sources   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Feed Fetcher   │───► Raw HTML/JSON/XML
                    │  (Celery Beat)  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Data Cleaner   │───► Clean text + metadata
                    │  (Celery Task)  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Deduplicator   │───► Unique articles
                    │  (MinHash LSH)  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  NER + Keywords │───► Entities + keywords
                    │  (spaCy + AI)   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Embeddings     │───► Vector embeddings
                    │  (Sentence-T.)  │      stored in Qdrant
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Classification │───► Category + topics
                    │  (Transformers) │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Event Clustering│───► Event groups
                    │  (DBSCAN)       │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Summarization  │───► Event summaries
                    │  (BART)         │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Credibility    │───► Confidence scores
                    │  Assessment     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Index + Store  │───► PG, ES, Qdrant
                    │                 │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Update Recs    │───► Personalization
                    │                 │
                    └─────────────────┘
```

---

## 5. API Design Principles

- **RESTful** for CRUD operations
- **WebSocket** for real-time notifications
- **Versioned** (`/api/v1/...`)
- **Paginated** with cursor-based pagination for feeds
- **Filtered** via query parameters
- **Consistent error format**: `{ "error": { "code": "...", "message": "..." } }`
- **Rate limited** per user/IP
- **JWT authentication** with refresh tokens
- **OpenAPI 3.0** documentation auto-generated by FastAPI

---

## 6. Development Conventions

| Convention              | Standard                                              |
|-------------------------|-------------------------------------------------------|
| Python version          | 3.12+                                                 |
| Node version            | 20 LTS                                                |
| Code style (Python)     | Black + Ruff (line length 100)                        |
| Code style (TS/JS)      | Prettier + ESLint (single quotes, semicolons)         |
| Commit messages         | Conventional Commits (feat:, fix:, chore:, docs:)     |
| Branch naming           | `feature/xxx`, `fix/xxx`, `chore/xxx`                 |
| Testing (Python)        | pytest + pytest-cov (80%+ coverage)                   |
| Testing (TS/JS)         | Jest + React Testing Library                          |
| Database migrations     | Alembic (auto-generated)                              |
| Environment variables   | `.env` files with `.env.example` template             |

---

## 7. Project Structure (Top-Level)

```
smartfeed-ai/
├── backend/
│   ├── app/
│   │   ├── api/              # Route handlers
│   │   ├── core/             # Config, security, dependencies
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   ├── repositories/     # Data access layer
│   │   ├── pipeline/         # ETL pipeline tasks
│   │   ├── ai/               # AI module interfaces + impl
│   │   └── utils/            # Shared utilities
│   ├── alembic/              # DB migrations
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router pages
│   │   ├── components/       # Reusable UI components
│   │   ├── lib/              # API client, utilities
│   │   ├── hooks/            # Custom React hooks
│   │   ├── stores/           # Zustand stores
│   │   └── types/            # TypeScript types
│   ├── Dockerfile
│   └── package.json
├── infra/
│   ├── docker-compose.yml
│   ├── nginx/
│   ├── monitoring/
│   └── scripts/
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── database.md
│   ├── deployment.md
│   └── development.md
├── .github/
│   └── workflows/
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

---

## 8. Risk Assessment

| Risk                          | Likelihood | Impact | Mitigation                                                   |
|-------------------------------|------------|--------|--------------------------------------------------------------|
| API rate limits from sources  | High       | Medium | Multiple fallback sources, caching, backoff strategies       |
| LLM API costs                 | Medium     | High   | Use local models as default, cloud LLM as optional upgrade   |
| Embedding storage growth      | High       | Medium | Qdrant's built-in WAL + payload indexing; periodic cleanup   |
| News source downtime          | Medium     | Medium | Graceful degradation, stale cache serving                    |
| Data quality (bad sources)    | Medium     | Low    | Credibility scoring, manual moderation, blacklist            |
| Vector search latency         | Low        | Medium | Qdrant quantized vectors, HNSW tuning, sharding              |
| Concurrency issues            | Medium     | Medium | Celery task dedup, Redis locks, idempotent operations        |
| Deployment complexity         | Medium     | Low    | Comprehensive docker-compose, health checks, init scripts    |
| Security vulnerabilities      | Low        | High   | OWASP top 10 review, dependency scanning, audit logging      |

---

## 9. Development Phases (Overview)

| Phase | Duration (est.) | Deliverable                                    |
|-------|-----------------|------------------------------------------------|
| 1     | 1 day           | Architecture docs, project skeleton            |
| 2     | 1 day           | Complete folder structure with all directories |
| 3     | 1 day           | Docker configs, env setup, dependency files    |
| 4     | 2 days          | DB schema, Alembic migrations, seed scripts    |
| 5     | 5 days          | FastAPI app, auth, all CRUD endpoints          |
| 6     | 5 days          | Next.js app, all pages, components             |
| 7     | 3 days          | News collection pipeline, cleaning, processing |
| 8     | 4 days          | All AI modules with interfaces                 |
| 9     | 2 days          | Elasticsearch setup, indexing, search API      |
| 10    | 2 days          | Recommendation engine, personalization         |
| 11    | 3 days          | RAG chatbot with LangChain                     |
| 12    | 1 day           | Real-time notifications via WebSocket          |
| 13    | 2 days          | Admin analytics dashboard                      |
| 14    | 3 days          | Test suite across all layers                   |
| 15    | 2 days          | CI/CD, monitoring, deployment docs             |

> **Status:** Phases 1–14 complete. Phase 7 (data pipeline) is complete:
> feed fetching/parsing (`app/pipeline/feed_parser.py`), ingestion/dedup
> (`app/services/article_ingestion_service.py`), Celery task wiring, admin
> refresh + `scripts/run_pipeline.py`. Phase 8 (AI modules) is complete:
> `ArticleEnrichmentService` runs classifier/sentiment/NER/credibility/
> summarizer/embeddings on ingested articles (injectable + fault-isolated),
> recommender scoring wired into `/recommendations`, real
> `update_trending`/`update_user_recommendations` tasks, Qdrant-backed
> vector store with graceful degradation, `ModelManager` caching, sentiment/NER
> wrapper tasks, and a fixed translator. Phase 9 (search) is complete:
> `ElasticsearchService` (index "articles", filters, sort, facets, highlights)
> with the search API upgraded to use Elasticsearch first and fall back to the
> SQL implementation when ES is down; `article_repository.search_by_keywords`
> now applies filters/sort and returns a real total; the Celery indexer
> (`app/pipeline/tasks/indexer.py`) keeps the ES index in sync after
> enrichment; docker-compose wires `ELASTICSEARCH_HOSTS` to workers and the
> backend health-checks ES; the frontend search page gained a filter UI and
> pagination. Phase 10 (recommendations + personalization) is complete:
> `ArticleRecommender` now blends explicit preferences with implicit signals
> (categories/sources read or bookmarked, keyword overlap, language filter,
> recency boost); `RecommendationService` serves cached per-user lists from
> Redis (read-through + write-back) with the Celery updater warming the cache,
> and invalidates the cache whenever preferences, reading history, or
> bookmarks change. Phase 11 (RAG chatbot) is complete: conversations and
> messages are persisted (`Conversation`/`ChatMessage` models), the
> `ChatbotService` embeds the question, retrieves article chunks from Qdrant
> via LangChain (`RecursiveCharacterTextSplitter`) with a SQL keyword-search
> fallback, generates answers with `QAModule` (local distilBERT QA or OpenAI
> via httpx), and persists sources with each assistant message. The chat API
> gained conversation list/history/delete endpoints and the frontend chat page
> has a conversation sidebar. Phase 12 (real-time notifications) is complete:
> a per-user WebSocket endpoint (`/api/v1/ws/notifications`, token-authenticated)
> backed by `ConnectionManager`; `NotificationDispatcher` pushes new
> notifications locally and fans out to other workers over a Redis pub/sub
> channel (subscriber started in the app lifespan, graceful degradation when
> Redis is down); `NotificationService.create_notification` dispatches every
> created notification, and `ArticleNotificationProducer` notifies users whose
> saved categories match a newly enriched article (only when notifications are
> enabled). The frontend notifications menu now listens on the WebSocket and
> updates the badge/list live with reconnection + backoff. Phase 13 (admin
> analytics dashboard) is complete: the analytics API now exposes daily user
> activity (`/analytics/activity`), article publishing trends
> (`/analytics/articles-trend`), and category/source/sentiment distributions,
> plus a persisted event log (`AnalyticsEvent`) with a public
> `POST /analytics/track` endpoint (optional auth, anonymous events supported).
> The admin dashboard renders these as lightweight CSS bar charts (no chart
> library), with a 7/14/30-day range selector, distribution bars, and a recent
> events table. Phase 14 (test suite across all layers) is complete: coverage
> grew from ~71% to 85% (315 pytest tests). New suites cover the pure utilities
> (`tests/unit/test_utils.py`), the thin service layer with fake repositories
> (`tests/unit/test_thin_services.py`), every AI module with mocked models
> (`tests/ai/test_ai_modules.py`), the Redis fan-out and subscriber paths of the
> notification dispatcher, Celery task wrappers (`tests/pipeline/test_tasks.py`),
> the notification repository, and API edge cases (404/409 branches and admin
> pipeline fallbacks). Phase 14 also caught and fixed two real bugs: `diff.d`
> instead of `diff.days` in `time_ago`, and `not Notification.is_read` (Python
> negation of a SQLAlchemy column) making unread counts always return 0.
> Phase 15 (CI/CD, monitoring, deployment docs) is complete: the backend now
> exposes Prometheus metrics at `GET /metrics` (`app/core/metrics.py` — request
> counters/duration/inflight with UUID path normalization, plus WebSocket,
> notification, ingestion, and enrichment counters), Prometheus scrapes the
> backend job, and Grafana auto-provisions the "SmartFeed Backend" dashboard
> (request rate, 5xx, latency p95/p99, WebSockets, pipeline activity). The CI
> workflow now covers the full frontend check set (ESLint, typecheck, Prettier,
> Jest) alongside the backend suite, `pytest-timeout` is pinned in
> `requirements.txt`, and `docs/monitoring.md` documents the metric set,
> dashboard setup, and alerting starting points.
> Remaining polish: newsapi ingestion, event clustering glue, webhook
> subscriptions.

---

## 10. Next Steps

Phase 15 (CI/CD, monitoring, deployment docs) complete; Phases 1–15 done.
Remaining polish: newsapi ingestion, event clustering glue, webhook
subscriptions.
