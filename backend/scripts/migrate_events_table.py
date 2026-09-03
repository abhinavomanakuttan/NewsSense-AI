import sqlite3

def migrate():
    conn = sqlite3.connect("smartfeed.db")
    cursor = conn.cursor()

    # 1. Events table
    cursor.execute("PRAGMA table_info(events)")
    existing_events = {row[1] for row in cursor.fetchall()}
    event_cols = [
        ("category", "TEXT"),
        ("subcategories", "TEXT"),
        ("entities", "TEXT"),
        ("locations", "TEXT"),
        ("source_count", "INTEGER DEFAULT 1"),
        ("independent_source_count", "REAL DEFAULT 1.0"),
        ("embedding", "TEXT"),
        ("status", "TEXT DEFAULT 'active'"),
        ("structured_summary", "TEXT"),
    ]
    for col, typ in event_cols:
        if col not in existing_events:
            print(f"Adding events.{col} ({typ})...")
            cursor.execute(f"ALTER TABLE events ADD COLUMN {col} {typ}")

    # 2. Articles table
    cursor.execute("PRAGMA table_info(articles)")
    existing_articles = {row[1] for row in cursor.fetchall()}
    article_cols = [
        ("source_name", "TEXT"),
        ("category_name", "TEXT"),
        ("discovered_at", "TEXT"),
        ("normalized_title", "TEXT"),
        ("url_hash", "TEXT"),
        ("source_hash", "TEXT"),
        ("article_fingerprint", "TEXT"),
        ("country", "TEXT"),
        ("raw_metadata", "TEXT"),
        ("duplicate_of_id", "TEXT"),
        ("is_syndicated", "INTEGER DEFAULT 0"),
        ("source_independence_score", "REAL DEFAULT 1.0"),
        ("match_type", "TEXT"),
    ]
    for col, typ in article_cols:
        if col not in existing_articles:
            print(f"Adding articles.{col} ({typ})...")
            cursor.execute(f"ALTER TABLE articles ADD COLUMN {col} {typ}")

    conn.commit()
    print("ALL MIGRATIONS COMPLETE!")

if __name__ == "__main__":
    migrate()
