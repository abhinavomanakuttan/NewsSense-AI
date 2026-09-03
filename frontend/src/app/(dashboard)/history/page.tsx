"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { ArticleCard } from "@/components/articles/article-card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageSpinner } from "@/components/ui/spinner";
import { Button } from "@/components/ui/button";
import type { ReadingHistoryList } from "@/types/models";
export default function HistoryPage() {
  const [history, setHistory] = useState<ReadingHistoryList | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchHistory = useCallback(async () => {
    try {
      const data = await api.get<ReadingHistoryList>(
        "/reading-history?limit=100",
      );
      setHistory(data);
    } catch {
      setHistory({ items: [], total: 0 });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleRemove = async (id: string) => {
    setHistory((prev) =>
      prev
        ? {
            items: prev.items.filter((item) => item.id !== id),
            total: Math.max(0, prev.total - 1),
          }
        : prev,
    );
    try {
      await api.delete(`/reading-history/${id}`);
    } catch {
      fetchHistory();
    }
  };

  const handleClear = async () => {
    setHistory({ items: [], total: 0 });
    try {
      await api.delete("/reading-history");
    } catch {
      fetchHistory();
    }
  };

  if (loading) return <PageSpinner />;

  const items = history?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Reading History</h1>
        {items.length > 0 && (
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">
              {history?.total ?? 0} read
            </span>
            <Button variant="outline" size="sm" onClick={handleClear}>
              <Trash2 className="h-4 w-4" />
              Clear history
            </Button>
          </div>
        )}
      </div>

      {items.length === 0 ? (
        <EmptyState
          title="No reading history yet"
          description="Articles you read will appear here so you can pick up where you left off."
          action={
            <Button asChild>
              <Link href="/feed">Start Reading</Link>
            </Button>
          }
        />
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <ArticleCard
              key={item.id}
              id={item.article_id}
              title={item.title || "Untitled article"}
              slug={item.slug || ""}
              summary={item.summary}
              sourceName={item.source_name}
              imageUrl={item.image_url}
              action={
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 text-muted-foreground hover:text-destructive"
                  onClick={(e) => {
                    e.preventDefault();
                    handleRemove(item.id);
                  }}
                  aria-label="Remove from history"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
