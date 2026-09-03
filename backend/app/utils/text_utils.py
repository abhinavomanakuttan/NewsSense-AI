import hashlib
import re
import unicodedata


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text[:500]


def truncate_text(text: str, max_length: int = 500) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(" ", 1)[0] + "..."


def extract_content_hash(title: str, content: str) -> str:
    return hashlib.sha256((title + content).encode()).hexdigest()


def strip_html(html: str) -> str:
    clean = re.compile("<.*?>")
    return re.sub(clean, "", html)
