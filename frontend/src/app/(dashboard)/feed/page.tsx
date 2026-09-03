"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { ArticleCard } from "@/components/articles/article-card";
import { Select } from "@/components/ui/select";
import { EmptyState } from "@/components/ui/empty-state";
import { PageSpinner } from "@/components/ui/spinner";
import type { ArticleList, Category, Recommendation } from "@/types/models";

type FeedMode = "latest" | "trending" | "recommended";

export default function FeedPage() {
  const [mode, setMode] = useState<FeedMode>("latest");
  const [articles, setArticles] = useState<ArticleList[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [bookmarkIds, setBookmarkIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<Category[]>("/categories")
      .then(setCategories)
      .catch(() => {});
    api
      .get<{ article_id: string }[]>("/bookmarks")
      .then((items) => setBookmarkIds(new Set(items.map((b) => b.article_id))))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const fetchFeed = async () => {
      setLoading(true);
      try {
        if (mode === "recommended") {
          const data = await api.get<Recommendation[]>(
            "/recommendations?limit=30",
          );
          setArticles(
            data.map((r) => ({
              id: r.id,
              title: r.title,
              slug: r.slug,
              summary: r.summary,
              source_name: r.source_name,
              category_name: r.category_name,
              image_url: r.image_url,
              published_at: r.published_at,
              sentiment: null,
              credibility_score: null,
              tags: [],
              reason: r.reason,
            })),
          );
        } else {
          const endpoint =
            mode === "trending"
              ? "/articles/trending?limit=30"
              : `/articles?limit=30${
                  selectedCategory
                    ? `&category=${encodeURIComponent(selectedCategory)}`
                    : ""
                }`;
          const data = await api.get<ArticleList[]>(endpoint);
          setArticles(data);
        }
      } catch {
        setArticles([]);
      } finally {
        setLoading(false);
      }
    };
    fetchFeed();
  }, [mode, selectedCategory]);

  const handleToggleBookmark = async (id: string) => {
    const isBookmarked = bookmarkIds.has(id);
    setBookmarkIds((prev) => {
      const next = new Set(prev);
      if (isBookmarked) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
    try {
      if (isBookmarked) {
        await api.delete(`/bookmarks/${id}`);
      } else {
        await api.post("/bookmarks", { article_id: id });
      }
    } catch {
      setBookmarkIds((prev) => {
        const next = new Set(prev);
        if (isBookmarked) {
          next.add(id);
        } else {
          next.delete(id);
        }
        return next;
      });
    }
  };

  const modeOptions = useMemo(
    () => [
      { value: "latest", label: "Latest" },
      { value: "trending", label: "Trending" },
      { value: "recommended", label: "Recommended" },
    ],
    [],
  );

  if (loading && articles.length === 0) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-bold">Your Feed</h1>
        <div className="flex flex-wrap gap-2">
          <Select
            value={mode}
            onChange={(e) => setMode(e.target.value as FeedMode)}
            className="w-40"
            aria-label="Feed mode"
          >
            {modeOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
          {mode !== "recommended" && (
            <Select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-48"
              aria-label="Category"
            >
              <option value="">All Categories</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name}
                </option>
              ))}
            </Select>
          )}
        </div>
      </div>

      {mode === "recommended" && (
        <p className="text-sm text-muted-foreground">
          Personalized picks based on your reading preferences and history.
        </p>
      )}

      {articles.length === 0 ? (
        <EmptyState
          title={loading ? "Loading..." : "No articles found"}
          description={
            loading
              ? "Fetching the latest news for you."
              : "Try a different category or check back later."
          }
        />
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {articles.map((article) => (
            <ArticleCard
              key={article.id}
              {...article}
              isBookmarked={bookmarkIds.has(article.id)}
              onToggleBookmark={handleToggleBookmark}
            />
          ))}
        </div>
      )}
    </div>
  );
}
