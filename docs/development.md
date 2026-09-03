# Development Guide

## Setup

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL 16
- Redis 7
- Docker Desktop
- Elasticsearch 8 (optional; search falls back to SQL when not running)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_lg

# Copy env file
cp .env.example .env

# Run migrations
alembic upgrade head

# Seed data
python -m scripts.seed

# Start server
uvicorn app.main:app --reload --port 8000
```

> **Note:** `bcrypt` is pinned to `>=4.0.0,<4.1.0` because newer versions are
> incompatible with `passlib 1.7.4` (see
> [passlib#764](https://github.com/borgstrom/passlib/issues/764)).

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy env file
cp .env.example .env.local

# Start dev server (proxies /api/v1 -> backend)
npm run dev
```

> The Next.js dev server runs on port 3000. Requests to `/api/v1/*` are
> rewritten to the backend API (`http://localhost:8000/api/v1` by default,
> overridable via `NEXT_PUBLIC_API_URL` in `.env.local`). Start the backend
> first, then the frontend.

## Code Style

### Python
```bash
# Check style
cd backend
ruff check . --fix
ruff format .

# Type check
mypy app --ignore-missing-imports
```

### TypeScript
```bash
# Check style
cd frontend
npm run lint

# Format
npm run format

# Type check
npm run typecheck
```

## Testing

Backend tests are split by layer:

```bash
cd backend
pytest                          # All tests (315; full suite ~6 min)
pytest tests/unit               # Pure unit tests (utils, security, schemas, services)
pytest tests/ai                 # AI module tests (models mocked)
pytest tests/pipeline           # Feed parsing, ingestion, Celery task wrappers
pytest tests/services           # Service-layer tests
pytest tests/repositories       # DB-backed repository tests
pytest tests/api                # API tests (FastAPI TestClient + test DB)
pytest --cov=app                # With coverage (~85%)
```

> Before a full-suite run, delete `smartfeed.db_test` if a previous run was
> killed mid-way — stale rows cause UNIQUE-constraint failures.

Frontend tests (Jest + React Testing Library):

```bash
cd frontend
npm test                        # All tests (use `--ci` in pipelines)
npm run build                   # Production build (also type-checks)
```

## Database Migrations

```bash
# Create migration
cd backend
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1

# View history
alembic history
```

## Running Workers

```bash
# Celery worker
cd backend
celery -A app.pipeline.celery_app worker --loglevel=info --concurrency=4

# Celery beat (scheduler)
celery -A app.pipeline.celery_app beat --loglevel=info
```

## Ingestion Pipeline

Feeds are fetched, parsed (RSS/Atom/JSON), deduplicated, and persisted by
`app.services.article_ingestion_service.ArticleIngestionService`. Entry points:

```bash
# Ingest a single source without a broker (dev-friendly)
cd backend
python -m scripts.run_pipeline <source_id>       # one source
python -m scripts.run_pipeline --all             # all active sources
python -m scripts.run_pipeline --list            # show sources and ids
```

- `Celery`: `celery -A app.pipeline.celery_app worker` runs
  `fetch_all_feeds` (beat every 5 min), which dispatches one `fetch_source`
  task per active source. AI enrichment tasks (classification, credibility,
  embeddings, summaries) are wired as async wrappers in `tasks/`.
- `Admin API`: `POST /admin/sources/{id}/refresh` and
  `POST /admin/ingest-all` queue Celery tasks, falling back to inline
  ingestion when the broker is unreachable.
- Deduplication: same `content_hash` (sha256 of title+content) or same URL
  within a feed or in the DB is skipped; slugs get numeric suffixes on
  collision.

## AI Enrichment

After ingestion, newly created articles are enriched by the AI modules
(`app/ai/`). Each module implements the `AIModule` interface
(`initialize` / `process` / `cleanup`) and is registered through
`ModelManager` for shared model caching:

| Module            | What it writes to Article                       |
|-------------------|-------------------------------------------------|
| `NewsClassifier`  | `category_id` (zero-shot, matches by slug)      |
| `SentimentAnalyzer`| `sentiment`, `sentiment_score`                 |
| `NERExtractor`    | `keywords`, `entities` (JSON strings)           |
| `CredibilityAssessor` | `credibility_score`, `credibility_factors`  |
| `NewsSummarizer`  | `summary` (only when absent/short)              |
| `EmbeddingGenerator` | embedding into Qdrant, `embedding_id`        |

- Orchestration: `app/services/article_enrichment_service.py`. Modules are
  injectable (for tests) and fault-isolated — one failing step never stops
  the others. Qdrant and Redis degrade gracefully when unreachable.
- Triggering: Celery task `enrich_article` is dispatched per new article by
  `fetch_source` (toggle with `enable_enrichment` in `.env`). The dev script
  supports inline enrichment: `python -m scripts.run_pipeline <id> --enrich`.
- Embeddings/index: `app/services/vector_store_service.py` wraps Qdrant
  (`articles` collection, cosine distance); `index_article` /
  `remove_from_index` tasks use it.
- Recommendations: `app/ai/recommender.py` scores candidate articles by
  blending explicit preferences with implicit signals — categories/sources the
  user actually read or bookmarked, keyword overlap with past reading, language
  preferences (non-preferred languages excluded), credibility, popularity, and
  recency. `app/services/recommendation_service.py` fetches recent candidates
  (excluding consumed articles), runs the recommender, and serves the result
  with a Redis read-through/write-back cache (`recommendations:user:{id}`,
  30 min TTL). `update_trending` and `update_user_recommendations` Celery tasks
  warm that cache. The cache is invalidated automatically whenever preferences,
  reading history, or bookmarks change.

## Search (Elasticsearch)

Full-text search runs on Elasticsearch when available and falls back to a SQL
`ILIKE` implementation otherwise:

- `app/services/elasticsearch_service.py` — thin wrapper over the
  `elasticsearch` client (index `articles`, `is_available`, `search`,
  `_build_query`, `build_article_document`). Configure hosts via
  `elasticsearch_hosts` in `.env` (default `http://localhost:9200`); an
  optional `elasticsearch_api_key` is supported.
- `app/services/search_service.py` — tries ES first, falls back to
  `article_repository.search_by_keywords` when ES is unreachable. Applies
  category/source/language/sentiment/date filters, sort (relevance/date/
  view_count/credibility), returns real totals and ES facets/highlights.
- Indexing: `index_article` / `remove_from_index` Celery tasks
  (`app/pipeline/tasks/indexer.py`) keep the `articles` index in sync; the
  enrichment service indexes each article after persisting enrichment fields.
- Local dev without a broker: ingest + index with
  `python -m scripts.run_pipeline <source_id> --enrich`. Without
  Elasticsearch running the search API silently uses SQL, so the app works
  either way.

## Chatbot (RAG)

`app/services/chatbot_service.py` answers questions strictly from retrieved
news content:

- Retrieval is vector-first: the question is embedded with
  `EmbeddingGenerator`, searched in Qdrant via `vector_store_service`, and
  the matching articles are loaded from the DB. When Qdrant or embeddings are
  unavailable the service falls back to
  `article_repository.search_by_keywords`.
- Context building: retrieved articles are turned into LangChain
  `Document`s and chunked with `RecursiveCharacterTextSplitter` (1000-char
  chunks, 100 overlap), capped at `MAX_CONTEXT_CHARS` (4000).
- Generation: `QAModule` (`app/ai/qa_chain.py`) answers with a local
  distilBERT question-answering pipeline, or OpenAI (via httpx) when
  `openai_api_key` is set. If generation fails or returns an empty answer the
  service responds with a helpful fallback and the retrieved sources.
- Persistence: `Conversation` / `ChatMessage` models store conversations per
  user, including the source list attached to each assistant message. The
  `ConversationRepository` (`app/repositories/conversation_repository.py`)
  handles get-or-create, listing, history, and deletion.
- API: `POST /chat` asks a question (continues an existing conversation when
  `conversation_id` is passed); `GET /chat/conversations`,
  `GET /chat/conversations/{id}`, and `DELETE /chat/conversations/{id}`
  manage the user's history. The frontend chat page (`frontend/src/app/
  (dashboard)/chatbot/page.tsx`) shows a conversation sidebar alongside the
  messages.
- Tests: `tests/services/test_chatbot_service.py` (fake embedder/vector
  store/QA module) and `tests/api/test_chatbot.py` cover retrieval,
  fallbacks, persistence, and the conversation endpoints.

## Real-time Notifications (WebSocket)

Notifications are pushed live to authenticated users over a WebSocket:

- Endpoint: `WS /api/v1/ws/notifications?token=<jwt>`. The token is decoded
  via `decode_token`; invalid/missing tokens get a `4401` close. After
  accepting, the server sends `{"type":"connected"}`, answers client
  `{"type":"ping"}` frames with `{"type":"pong"}`, and pushes
  `{"type":"notification","notification":{...}}` frames.
- Connection registry: `app/services/ws_manager.py` keeps per-user socket
  sets (`ConnectionManager`); one user may hold several sockets (tabs).
- Dispatch: `app/services/notification_dispatcher.py` sends a notification
  to the local sockets and publishes it to the Redis channel
  `smartfeed:notifications`. A subscriber task (started in `main.py`
  lifespan) re-routes messages from other workers to this process's sockets.
  When Redis is unreachable the local delivery still works and the
  subscriber simply disables itself.
- Producers:
  - `NotificationService.create_notification` pushes every created
    notification.
  - `ArticleNotificationProducer` (`app/services/notification_producer.py`)
    notifies users who have notifications enabled and whose
    `preferred_categories` match a newly enriched article's category. It is
    invoked by the enrichment service after a successful enrich-and-commit
    (production path only, best-effort and fault-isolated).
- Frontend: `frontend/src/components/layout/notifications-menu.tsx` opens the
  WebSocket, prepends live notifications, bumps the unread badge, and
  reconnects with exponential backoff.
- `RateLimitMiddleware` is a pure ASGI middleware so WebSocket scopes pass
  through untouched.
- Tests: `tests/api/test_websocket.py` (TestClient-based auth/connect/ping),
  `tests/services/test_ws_manager.py`, `test_notification_dispatcher.py`,
  `test_notification_producer.py`, and `test_notification_service.py`.

## Project Commands

```bash
make install    # Install all dependencies
make dev        # Start development environment
make test       # Run all tests
make lint       # Run linters
make format     # Format code
make migrate    # Run database migrations
make seed       # Seed initial data
```

## Architecture Decisions

### Why FastAPI over Django?
- Async-native for AI/IO-bound workloads
- Auto-generated OpenAPI docs
- Pydantic validation built-in
- Lighter weight for microservice patterns

### Why Celery over Redis Queue?
- Task persistence with RabbitMQ
- Beat scheduler for periodic feeds
- Worker scaling and monitoring
- Task prioritization and routing

### Why Qdrant over Pinecone?
- Self-hosted (no API costs)
- Written in Rust for performance
- Rich filtering with payload indexing
- Quantized vectors for memory efficiency

### Why separate search (ES + Qdrant)?
- Elasticsearch excels at full-text search, faceted navigation, and aggregations
- Qdrant excels at semantic similarity search
- Together they provide hybrid search capability
