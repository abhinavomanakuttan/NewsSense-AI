from app.ai.base import AIModule


class TimelineGenerator(AIModule):
    async def initialize(self) -> None:
        pass

    async def process(self, data: dict, **kwargs) -> dict:
        articles = data.get("articles", [])

        sorted_articles = sorted(
            articles,
            key=lambda a: a.get("published_at", ""),
        )

        timeline = []
        for i, article in enumerate(sorted_articles):
            timeline.append(
                {
                    "index": i + 1,
                    "date": article.get("published_at", "Unknown"),
                    "title": article.get("title", ""),
                    "summary": article.get("summary", ""),
                    "url": article.get("url", ""),
                    "source": article.get("source_name", ""),
                }
            )

        return {
            "timeline": timeline,
            "total_events": len(timeline),
            "date_range": {
                "start": sorted_articles[0].get("published_at") if sorted_articles else None,
                "end": sorted_articles[-1].get("published_at") if sorted_articles else None,
            },
        }

    async def cleanup(self) -> None:
        pass
