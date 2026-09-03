from datetime import UTC, datetime

import dateparser


def parse_date(date_string: str | None) -> datetime | None:
    if not date_string:
        return None
    parsed = dateparser.parse(date_string)
    if parsed and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def format_date(date: datetime, format: str = "%Y-%m-%dT%H:%M:%SZ") -> str:
    return date.strftime(format)


def time_ago(date: datetime) -> str:
    now = datetime.now(UTC)
    diff = now - date

    if diff.days > 365:
        return f"{diff.days // 365}y ago"
    if diff.days > 30:
        return f"{diff.days // 30}mo ago"
    if diff.days > 0:
        return f"{diff.days}d ago"
    if diff.seconds > 3600:
        return f"{diff.seconds // 3600}h ago"
    if diff.seconds > 60:
        return f"{diff.seconds // 60}m ago"
    return "just now"
