# Database Schema

## Entity-Relationship Diagram

```
┌───────────┐       ┌──────────────┐       ┌────────────┐
│   users   │──┬────│  bookmarks   │───────│  articles  │
└───────────┘  │    └──────────────┘       └────────────┘
               │                                    ▲
               │    ┌─────────────────┐             │
               ├────│ reading_history  │─────────────┘
               │    └─────────────────┘
               │    ┌────────────────┐
               ├────│  notifications  │
               │    └────────────────┘
               │    ┌──────────────────┐
               ├────│  search_history   │
               │    └──────────────────┘
               │    ┌──────────────────────┐
               └────│  user_preferences    │
                    └──────────────────────┘

┌───────────┐       ┌────────────┐       ┌──────────────┐
│  sources  │───────│  articles  │───────│ article_tags │───┐
└───────────┘       └────────────┘       └──────────────┘   │
                             │                              │
                             ▼                              ▼
                      ┌────────────┐                  ┌────────┐
                      │ categories │                  │  tags  │
                      └────────────┘                  └────────┘
                             ▲
                      ┌──────┘
                      ▼
                 ┌──────────┐
                 │  events  │
                 └──────────┘

Standalone tables: jobs, sports, analytics_events
```

## Table Relationships

| Parent → Child       | Type     | FK Column    | On Delete      |
|----------------------|----------|--------------|----------------|
| users → bookmarks    | 1:N      | user_id      | CASCADE        |
| users → reading_history | 1:N   | user_id      | CASCADE        |
| users → notifications | 1:N     | user_id      | CASCADE        |
| users → search_history | 1:N    | user_id      | CASCADE        |
| users → user_preferences | 1:1  | user_id      | CASCADE        |
| articles → bookmarks | 1:N      | article_id   | CASCADE        |
| articles → reading_history | 1:N | article_id  | CASCADE        |
| sources → articles   | 1:N      | source_id    | SET NULL       |
| categories → articles | 1:N     | category_id  | SET NULL       |
| events → articles    | 1:N      | event_id     | SET NULL       |
| articles → tags      | M:N      | article_tags | CASCADE        |

## All Tables & Columns

### users (core authentication)
| Column            | Type              | Constraints          |
|-------------------|-------------------|----------------------|
| id                | UUID              | PK, uuid_generate_v4 |
| email             | VARCHAR(255)      | UNIQUE, NOT NULL     |
| username          | VARCHAR(100)      | UNIQUE, NOT NULL     |
| hashed_password   | VARCHAR(255)      | NOT NULL             |
| full_name         | VARCHAR(255)      |                      |
| avatar_url        | VARCHAR(500)      |                      |
| role              | VARCHAR(20)       | DEFAULT 'user'       |
| is_active         | BOOLEAN           | DEFAULT true         |
| is_verified       | BOOLEAN           | DEFAULT false        |
| preferences       | JSON              |                      |
| created_at        | TIMESTAMPTZ       | DEFAULT now()        |
| updated_at        | TIMESTAMPTZ       | DEFAULT now()        |
| **Indexes**       | email, username, id |                    |

### articles (core content)
| Column             | Type              | Constraints              |
|--------------------|-------------------|--------------------------|
| id                 | UUID              | PK                       |
| title              | VARCHAR(500)      | NOT NULL                 |
| slug               | VARCHAR(500)      | UNIQUE, NOT NULL         |
| url                | VARCHAR(1000)     | UNIQUE, NOT NULL         |
| source_id          | UUID              | FK → sources(id)         |
| category_id        | UUID              | FK → categories(id)      |
| event_id           | UUID              | FK → events(id)          |
| content            | TEXT              |                          |
| summary            | TEXT              |                          |
| content_hash       | VARCHAR(64)       | NOT NULL, INDEXED        |
| author             | VARCHAR(255)      |                          |
| published_at       | VARCHAR(50)       | INDEXED                  |
| language           | VARCHAR(10)       | DEFAULT 'en'             |
| sentiment          | VARCHAR(20)       |                          |
| sentiment_score    | FLOAT             |                          |
| keywords           | TEXT              |                          |
| entities           | TEXT              |                          |
| embedding_id       | VARCHAR(100)      | Qdrant reference         |
| is_duplicate       | BOOLEAN           | DEFAULT false            |
| credibility_score  | FLOAT             | 0.0 - 1.0                |
| image_url          | VARCHAR(1000)     |                          |
| view_count         | VARCHAR(10)       | DEFAULT '0'              |
| is_verified        | BOOLEAN           | DEFAULT false            |
| created_at         | TIMESTAMPTZ       |                          |
| updated_at         | TIMESTAMPTZ       |                          |

### sources (news sources configuration)
| Column                | Type              | Constraints          |
|-----------------------|-------------------|----------------------|
| id                    | UUID              | PK                   |
| name                  | VARCHAR(255)      | NOT NULL             |
| url                   | VARCHAR(500)      | UNIQUE, NOT NULL     |
| feed_url              | VARCHAR(500)      |                      |
| source_type           | VARCHAR(50)       | rss/api/website      |
| language              | VARCHAR(10)       | DEFAULT 'en'         |
| country               | VARCHAR(5)        | ISO code             |
| category              | VARCHAR(50)       |                      |
| is_active             | BOOLEAN           | DEFAULT true         |
| reputation_score      | FLOAT             | DEFAULT 0.5          |
| fetch_interval_minutes| INTEGER           | DEFAULT 30           |
| last_fetched_at       | VARCHAR(50)       |                      |
| config                | TEXT              |                      |

### categories (article classification)
| Column         | Type              | Constraints          |
|----------------|-------------------|----------------------|
| id             | UUID              | PK                   |
| name           | VARCHAR(100)      | UNIQUE, NOT NULL     |
| slug           | VARCHAR(100)      | UNIQUE, NOT NULL     |
| description    | TEXT              |                      |
| icon           | VARCHAR(50)       |                      |
| parent_id      | VARCHAR(50)       | Self-referential     |
| display_order  | VARCHAR(10)       | DEFAULT '0'          |

### tags (article keywords as structured entities)
| Column | Type              | Constraints          |
|--------|-------------------|----------------------|
| id     | UUID              | PK                   |
| name   | VARCHAR(100)      | UNIQUE, NOT NULL     |
| slug   | VARCHAR(100)      | UNIQUE, NOT NULL     |

### article_tags (M:N association)
| Column     | Type              | Constraints                |
|------------|-------------------|----------------------------|
| article_id | UUID              | FK → articles, CASCADE     |
| tag_id     | UUID              | FK → tags, CASCADE         |
| **PK**     | (article_id, tag_id) | Composite primary key   |

### events (grouped news stories)
| Column           | Type              | Constraints          |
|------------------|-------------------|----------------------|
| id               | UUID              | PK                   |
| title            | VARCHAR(500)      | NOT NULL             |
| slug             | VARCHAR(500)      | UNIQUE, NOT NULL     |
| summary          | TEXT              |                      |
| description      | TEXT              |                      |
| category_id      | VARCHAR(50)       |                      |
| start_date       | TIMESTAMPTZ       |                      |
| end_date         | TIMESTAMPTZ       |                      |
| article_count    | VARCHAR(10)       | DEFAULT '0'          |
| importance_score | FLOAT             | DEFAULT 0.0          |
| timeline         | TEXT              | JSON timeline        |
| is_active        | BOOLEAN           | DEFAULT true         |

### bookmarks (user saved articles)
| Column     | Type              | Constraints                |
|------------|-------------------|----------------------------|
| id         | UUID              | PK                         |
| user_id    | UUID              | FK → users, CASCADE        |
| article_id | UUID              | FK → articles, CASCADE     |
| **Index**  | (user_id, article_id) | UNIQUE composite        |

### reading_history (user engagement tracking)
| Column               | Type              | Constraints                |
|----------------------|-------------------|----------------------------|
| id                   | UUID              | PK                         |
| user_id              | UUID              | FK → users, CASCADE        |
| article_id           | UUID              | FK → articles, CASCADE     |
| read_duration_seconds| INTEGER           | DEFAULT 0                  |
| scroll_depth         | INTEGER           | DEFAULT 0                  |
| **Index**            | (user_id, article_id) | UNIQUE composite        |

### notifications (user alerts)
| Column          | Type              | Constraints          |
|-----------------|-------------------|----------------------|
| id              | UUID              | PK                   |
| user_id         | UUID              | FK → users, CASCADE  |
| title           | VARCHAR(500)      | NOT NULL             |
| body            | VARCHAR(2000)     |                      |
| notification_type| VARCHAR(50)      | NOT NULL             |
| reference_id    | VARCHAR(100)      |                      |
| reference_type  | VARCHAR(50)       |                      |
| is_read         | BOOLEAN           | DEFAULT false        |
| is_sent         | BOOLEAN           | DEFAULT false        |

### search_history (user search tracking)
| Column       | Type              | Constraints          |
|--------------|-------------------|----------------------|
| id           | UUID              | PK                   |
| user_id      | UUID              | FK → users, CASCADE  |
| query        | VARCHAR(500)      | NOT NULL             |
| filters      | VARCHAR(2000)     |                      |
| result_count | VARCHAR(10)       | DEFAULT '0'          |

### user_preferences (personalization settings)
| Column                  | Type              | Constraints              |
|-------------------------|-------------------|--------------------------|
| id                      | UUID              | PK                       |
| user_id                 | UUID              | FK → users, UNIQUE       |
| preferred_categories    | JSON              |                          |
| preferred_sources       | JSON              |                          |
| preferred_languages     | JSON              | DEFAULT '["en"]'          |
| preferred_regions       | JSON              |                          |
| notification_enabled    | BOOLEAN           | DEFAULT true             |
| dark_mode               | BOOLEAN           | DEFAULT false            |
| email_digest_frequency  | VARCHAR(20)       | DEFAULT 'daily'          |
| custom_settings         | JSON              |                          |

### jobs (job listings feed)
| Column       | Type              | Constraints          |
|--------------|-------------------|----------------------|
| id           | UUID              | PK                   |
| title        | VARCHAR(500)      | NOT NULL             |
| company      | VARCHAR(255)      | NOT NULL             |
| location     | VARCHAR(255)      |                      |
| description  | TEXT              |                      |
| url          | VARCHAR(1000)     | UNIQUE, NOT NULL     |
| salary_range | VARCHAR(100)      |                      |
| job_type     | VARCHAR(50)       |                      |
| industry     | VARCHAR(100)      |                      |
| posted_at    | TIMESTAMPTZ       |                      |
| source       | VARCHAR(100)      |                      |

### sports (sports news & scores)
| Column     | Type              | Constraints          |
|------------|-------------------|----------------------|
| id         | UUID              | PK                   |
| title      | VARCHAR(500)      | NOT NULL             |
| sport_type | VARCHAR(50)       | NOT NULL, INDEXED    |
| league     | VARCHAR(100)      |                      |
| team1      | VARCHAR(255)      |                      |
| team2      | VARCHAR(255)      |                      |
| score      | VARCHAR(50)       |                      |
| status     | VARCHAR(50)       | DEFAULT 'upcoming'   |
| start_time | TIMESTAMPTZ       |                      |
| summary    | TEXT              |                      |
| url        | VARCHAR(1000)     |                      |
| source     | VARCHAR(100)      |                      |

### analytics_events (usage tracking)
| Column         | Type              | Constraints          |
|----------------|-------------------|----------------------|
| id             | UUID              | PK                   |
| event_type     | VARCHAR(100)      | NOT NULL, INDEXED    |
| user_id        | VARCHAR(100)      |                      |
| article_id     | VARCHAR(100)      |                      |
| session_id     | VARCHAR(100)      |                      |
| metadata       | JSON              |                      |
| value          | FLOAT             |                      |
| timestamp      | TIMESTAMPTZ       | NOT NULL             |

### conversations (chatbot sessions per user)
| Column         | Type              | Constraints          |
|----------------|-------------------|----------------------|
| id             | UUID              | PK                   |
| user_id        | UUID              | NOT NULL, FK → users, INDEXED |
| title          | VARCHAR(255)      |                      |
| created_at     | TIMESTAMPTZ       | NOT NULL             |
| updated_at     | TIMESTAMPTZ       | NOT NULL             |

### chat_messages (chatbot turn within a conversation)
| Column         | Type              | Constraints          |
|----------------|-------------------|----------------------|
| id             | UUID              | PK                   |
| conversation_id| UUID              | NOT NULL, FK → conversations, INDEXED |
| role           | VARCHAR(20)       | NOT NULL             |
| content        | TEXT              | NOT NULL             |
| sources        | JSON              |                      |
| created_at     | TIMESTAMPTZ       | NOT NULL             |
| updated_at     | TIMESTAMPTZ       | NOT NULL             |

## Index Summary

| Index Name                    | Table            | Columns              | Type   |
|-------------------------------|------------------|----------------------|--------|
| ix_users_email                | users            | email                | UNIQUE |
| ix_users_username             | users            | username             | UNIQUE |
| ix_articles_slug              | articles         | slug                 | UNIQUE |
| ix_articles_content_hash      | articles         | content_hash         |        |
| ix_articles_published_at      | articles         | published_at         |        |
| ix_articles_source_id         | articles         | source_id            |        |
| ix_articles_category_id       | articles         | category_id          |        |
| ix_bookmarks_user_article     | bookmarks        | (user_id, article_id)| UNIQUE |
| ix_reading_history_user_article| reading_history | (user_id, article_id)| UNIQUE |
| ix_notifications_user_unread  | notifications    | (user_id, is_read)   |        |
| ix_user_preferences_user_id   | user_preferences | user_id              | UNIQUE |
| ix_sports_sport_type          | sports           | sport_type           |        |
| ix_conversations_user_id      | conversations    | user_id              |        |
| ix_chat_messages_conversation_id | chat_messages | conversation_id      |        |

## Migration Management

```bash
# Create new migration (requires running database)
cd backend
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# View migration history
alembic history

# Generate SQL without applying (offline mode)
alembic upgrade head --sql

# Current migration file: backend/alembic/versions/001_initial_schema.py
```

## Seed Data

The seed script creates:
1. Admin user (admin@smartfeed.ai / admin123)
2. 10 categories (Politics, Tech, Business, Science, Health, Sports, Entertainment, World, Environment, Education)
3. 5 news sources (BBC News, Reuters, Associated Press, TechCrunch, The Guardian)

```bash
cd backend
python scripts/seed.py
```
