import logging
import re

from bs4 import BeautifulSoup

from app.pipeline.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def clean_html_content(raw_html: str) -> dict:
    if not raw_html:
        return {"cleaned_text": "", "word_count": 0}

    soup = BeautifulSoup(raw_html, "lxml")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator=" ")

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s.,!?;:'\"()-]", "", text)
    text = text.strip()

    return {
        "cleaned_text": text,
        "word_count": len(text.split()),
        "char_count": len(text),
    }


@celery_app.task
def extract_metadata(raw_data: dict) -> dict:
    text = raw_data.get("content", "")

    word_count = len(text.split())
    reading_time = max(1, round(word_count / 200))

    has_images = bool(raw_data.get("image_url"))
    has_video = "youtube" in text.lower() or "video" in text.lower()

    return {
        "word_count": word_count,
        "reading_time_minutes": reading_time,
        "has_images": has_images,
        "has_video": has_video,
        "content_length": len(text),
    }
