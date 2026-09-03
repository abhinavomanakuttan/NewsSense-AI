# API Documentation

## Overview

Base URL: `/api/v1`

All requests require `Content-Type: application/json` header.

Authentication uses JWT Bearer tokens in the `Authorization` header.

Interactive docs: `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.

## Authentication

| Method | Endpoint           | Description        |
|--------|--------------------|--------------------|
| POST   | /auth/register     | Register new user  |
| POST   | /auth/login        | Login              |
| POST   | /auth/refresh      | Refresh token      |

### Register

```json
POST /api/v1/auth/register
{
  "email": "user@example.com",
  "username": "janedoe",
  "password": "StrongPass123!",
  "full_name": "Jane Doe"
}
```

### Login

```json
POST /api/v1/auth/login
{
  "email": "user@example.com",
  "password": "StrongPass123!"
}
```

Returns `access_token` and `refresh_token`. Send the access token as `Authorization: Bearer <token>` on authenticated endpoints.

## Users

| Method | Endpoint                | Description         |
|--------|-------------------------|---------------------|
| GET    | /users/me              | Get profile         |
| PUT    | /users/me              | Update profile      |
| GET    | /users/me/preferences  | Get preferences     |
| PUT    | /users/me/preferences  | Update preferences  |

All user endpoints require authentication.

## Articles

| Method | Endpoint             | Description          |
|--------|----------------------|----------------------|
| GET    | /articles            | List articles        |
| GET    | /articles/trending   | Trending articles    |
| GET    | /articles/{slug}     | Get article by slug  |

`GET /articles` supports `skip`, `limit`, and `category` (category UUID) query params.
`GET /articles/{slug}` increments the article's view count.

## Reading History

| Method | Endpoint             | Description                       |
|--------|----------------------|-----------------------------------|
| GET    | /reading-history     | List reading history              |
| POST   | /reading-history     | Record a read (upserts + accumulates duration) |
| DELETE | /reading-history     | Clear entire history              |
| DELETE | /reading-history/{id}| Remove a single history record    |

```json
POST /api/v1/reading-history
{
  "article_id": "54e90f10-6ac9-4fa3-849c-d13baf0ec55a",
  "read_duration_seconds": 45,
  "scroll_depth": 80
}
```

Repeated records for the same article accumulate `read_duration_seconds` and keep the max `scroll_depth`.

## Sources

| Method | Endpoint              | Description       |
|--------|-----------------------|-------------------|
| GET    | /sources              | List sources      |
| GET    | /sources/{id}         | Get source        |
| POST   | /sources              | Create source     |
| PUT    | /sources/{id}         | Update source     |
| DELETE | /sources/{id}         | Delete source     |

## Categories

| Method | Endpoint              | Description       |
|--------|-----------------------|-------------------|
| GET    | /categories           | List categories   |
| GET    | /categories/{slug}    | Get category      |
| POST   | /categories           | Create category   |

## Tags

| Method | Endpoint   | Description    |
|--------|------------|----------------|
| GET    | /tags      | List tags      |
| POST   | /tags      | Create tag     |

## Bookmarks

| Method | Endpoint                  | Description          |
|--------|---------------------------|----------------------|
| GET    | /bookmarks               | List bookmarks (includes embedded article title/slug/summary/source) |
| POST   | /bookmarks               | Add bookmark         |
| DELETE | /bookmarks/{article_id}  | Remove bookmark      |

## Notifications

| Method | Endpoint                         | Description            |
|--------|----------------------------------|------------------------|
| GET    | /notifications                  | List notifications     |
| PUT    | /notifications/{id}/read        | Mark as read           |
| PUT    | /notifications/read-all         | Mark all as read       |

## Events

| Method | Endpoint                     | Description            |
|--------|------------------------------|------------------------|
| GET    | /events                     | List events            |
| GET    | /events/{slug}              | Get event              |
| GET    | /events/{id}/articles       | Event articles         |

## Search

| Method | Endpoint   | Description    |
|--------|------------|----------------|
| POST   | /search    | Search articles|

Works for anonymous visitors; authenticated users additionally get their queries saved to search history.

```json
POST /api/v1/search
{
  "query": "artificial intelligence",
  "page": 1,
  "page_size": 20
}
```

## Recommendations

| Method | Endpoint         | Description            |
|--------|------------------|------------------------|
| GET    | /recommendations | Get personalized feed  |

## Chatbot

| Method | Endpoint                                 | Description                          |
|--------|------------------------------------------|--------------------------------------|
| POST   | /chat                                    | Ask a question (RAG from articles)   |
| GET    | /chat/conversations                      | List the user's conversations        |
| GET    | /chat/conversations/{id}                 | Get a conversation's message history |
| DELETE | /chat/conversations/{id}                 | Delete a conversation                |

All chatbot endpoints require authentication. `POST /chat` accepts
`{ "message": string, "conversation_id": optional string }` and returns
`{ "answer", "sources": [{ title, url, snippet, relevance_score }],
"conversation_id", "confidence" }`. Omitting `conversation_id` starts a new
conversation; passing an existing one continues it. Retrieval is
vector-first (Qdrant, via the article embeddings) with a SQL keyword-search
fallback, and answers are generated from the retrieved article context.

## WebSocket (Real-time Notifications)

| Endpoint                    | Description                          |
|-----------------------------|--------------------------------------|
| WS /api/v1/ws/notifications | Live notification stream (auth via `?token=` query param) |

Authenticate with the JWT as a `token` query parameter. On connect the server
sends `{"type": "connected", "user_id": "..."}`. The client should send
`{"type": "ping"}` periodically and receives `{"type": "pong"}`. Incoming
frames look like:

```json
{
  "type": "notification",
  "notification": {
    "id": "…", "title": "…", "body": "…", "notification_type": "new_article",
    "is_read": false, "created_at": "…"
  }
}
```

Invalid or missing tokens close the connection with code `4401`.

## Analytics (Admin)

| Method | Endpoint                  | Description                       |
|--------|---------------------------|-----------------------------------|
| GET    | /analytics/overview       | System overview                   |
| GET    | /analytics/activity       | Daily user activity series        |
| GET    | /analytics/articles-trend | Daily published-articles series   |
| GET    | /analytics/categories     | Articles grouped by category      |
| GET    | /analytics/sources        | Articles + credibility by source  |
| GET    | /analytics/sentiment      | Articles grouped by sentiment     |
| GET    | /analytics/events         | Paginated analytics event log     |
| POST   | /analytics/track          | Record a client-side event        |

Except `POST /analytics/track`, all endpoints require an admin role.

- `GET /analytics/overview` returns total users, active users today, articles, articles today, sources, active sources, searches, and events.
- `GET /analytics/activity?days=N` returns a zero-filled daily series (default 14) of `active_users`, `page_views`, `searches`, and `bookmarks`. `active_users` is the distinct set of users with any reading, search, or bookmark that day.
- `GET /analytics/articles-trend?days=N` returns a zero-filled daily count of published articles.
- `GET /analytics/categories` and `GET /analytics/sentiment` return `{label, count}`-style items; `GET /analytics/sources` additionally returns `avg_credibility`.
- `GET /analytics/events?limit=&skip=` returns the newest `AnalyticsEvent` rows plus a `total`.
- `POST /analytics/track` accepts `{event_type, article_id?, value?, metadata?}` with optional auth. Unauthenticated callers are recorded as anonymous. Response is the created event.

## Admin

| Method | Endpoint                    | Description                     |
|--------|-----------------------------|---------------------------------|
| POST   | /admin/sources/{id}/refresh | Fetch + ingest one source       |
| POST   | /admin/ingest-all           | Fetch + ingest all active feeds |
| GET    | /admin/system/health        | Health check                    |

`POST /admin/sources/{id}/refresh` queues a Celery task when a broker is
reachable; otherwise it runs ingestion inline and returns the per-source result
(`fetched`/`new`/`duplicates`/`skipped` counts). The source must be active and
have a `feed_url`.

## Error Format

Errors use standard HTTP status codes:

| Code | Meaning                       |
|------|-------------------------------|
| 400  | Bad request                   |
| 401  | Unauthenticated / invalid token |
| 403  | Forbidden (missing admin role) |
| 404  | Resource not found            |
| 409  | Duplicate resource            |
| 422  | Validation error              |
| 429  | Rate limit exceeded           |

