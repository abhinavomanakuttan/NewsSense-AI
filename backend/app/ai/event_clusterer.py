import numpy as np
from sklearn.cluster import DBSCAN

from app.ai.base import AIModule


class EventClusterer(AIModule):
    def __init__(self):
        self.model = None

    async def initialize(self) -> None:
        pass

    async def process(self, data: dict, **kwargs) -> dict:
        articles = data.get("articles", [])
        embeddings = data.get("embeddings", [])

        if len(articles) < 2 or len(embeddings) < 2:
            return {"clusters": [{"cluster_id": 0, "article_ids": [a.get("id") for a in articles]}]}

        eps = kwargs.get("eps", 0.3)
        min_samples = kwargs.get("min_samples", 2)

        embedding_matrix = np.array(embeddings)
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine").fit(embedding_matrix)

        clusters = {}
        for i, label in enumerate(clustering.labels_):
            label_key = int(label)
            if label_key not in clusters:
                clusters[label_key] = []
            clusters[label_key].append(
                {
                    "article_id": str(articles[i].get("id")),
                    "title": articles[i].get("title"),
                    "label": label_key,
                }
            )

        cluster_list = [
            {
                "cluster_id": cid,
                "article_count": len(items),
                "articles": items,
                "is_noise": cid == -1,
            }
            for cid, items in clusters.items()
        ]

        return {
            "clusters": cluster_list,
            "total_clusters": len(cluster_list),
            "parameters": {"eps": eps, "min_samples": min_samples},
        }

    async def cleanup(self) -> None:
        pass
