"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BookmarkX } from "lucide-react";
import { api } from "@/lib/api";
import { ArticleCard } from "@/components/articles/article-card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageSpinner } from "@/components/ui/spinner";
import { Button } from "@/components/ui/button";
import type { Bookmark } from "@/types/models";

export default function BookmarksPage() {
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchBookmarks = useCallback(async () => {
    try {
      const data = await api.get<Bookmark[]>("/bookmarks?limit=100");
      setBookmarks(data);
    } catch {
      setBookmarks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBookmarks();
  }, [fetchBookmarks]);

  const handleRemove = async (articleId: string) => {
    setBookmarks((prev) => prev.filter((b) => b.article_id !== articleId));
    try {
      await api.delete(`/bookmarks/${articleId}`);
    } catch {
      fetchBookmarks();
    }
  };

  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Bookmarks</h1>
        {bookmarks.length > 0 && (
          <span className="text-sm text-muted-foreground">
            {bookmarks.length} saved
          </span>
        )}
      </div>

      {bookmarks.length === 0 ? (
        <EmptyState
          title="No bookmarks yet"
          description="Save articles you want to read later by clicking the bookmark icon."
          action={
            <Button asChild>
              <Link href="/feed">Browse the Feed</Link>
            </Button>
          }
        />
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {bookmarks.map((bm) => (
            <ArticleCard
              key={bm.id}
              id={bm.article_id}
              title={bm.title || "Untitled article"}
              slug={bm.slug || ""}
              summary={bm.summary}
              sourceName={bm.source_name}
              imageUrl={bm.image_url}
              publishedAt={bm.published_at}
              isBookmarked
              onToggleBookmark={() => handleRemove(bm.article_id)}
            />
          ))}
        </div>
      )}

      {bookmarks.length > 0 && (
        <div className="flex justify-end">
          <Button
            variant="outline"
            size="sm"
            onClick={async () => {
              setBookmarks([]);
              await Promise.allSettled(
                bookmarks.map((b) => api.delete(`/bookmarks/${b.article_id}`)),
              );
            }}
          >
            <BookmarkX className="h-4 w-4" />
            Remove all
          </Button>
        </div>
      )}
    </div>
  );
}
