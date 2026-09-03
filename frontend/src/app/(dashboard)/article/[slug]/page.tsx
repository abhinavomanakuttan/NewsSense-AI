"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Bookmark, BookmarkCheck, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageSpinner } from "@/components/ui/spinner";
import { formatDate, formatScore } from "@/lib/utils";
import type { Article } from "@/types/models";

export default function ArticlePage() {
  const params = useParams();
  const slug = Array.isArray(params.slug) ? params.slug[0] : params.slug;
  const [article, setArticle] = useState<Article | null>(null);
  const [loading, setLoading] = useState(true);
  const [isBookmarked, setIsBookmarked] = useState(false);
  const recordedRef = useRef(false);

  useEffect(() => {
    const fetchArticle = async () => {
      if (!slug) return;
      setLoading(true);
      try {
        const data = await api.get<Article>(`/articles/${slug}`);
        setArticle(data);
      } catch {
        setArticle(null);
      } finally {
        setLoading(false);
      }
    };
    fetchArticle();
  }, [slug]);

  useEffect(() => {
    if (!article) return;
    api
      .get<{ article_id: string }[]>("/bookmarks")
      .then((items) =>
        setIsBookmarked(items.some((b) => b.article_id === article.id)),
      )
      .catch(() => {});
  }, [article]);

  useEffect(() => {
    if (!article || recordedRef.current) return;
    recordedRef.current = true;
    api
      .post("/reading-history", {
        article_id: article.id,
        read_duration_seconds: 30,
        scroll_depth: 0,
      })
      .catch(() => {});
  }, [article]);

  const handleToggleBookmark = async () => {
    if (!article) return;
    const next = !isBookmarked;
    setIsBookmarked(next);
    try {
      if (next) {
        await api.post("/bookmarks", { article_id: article.id });
      } else {
        await api.delete(`/bookmarks/${article.id}`);
      }
    } catch {
      setIsBookmarked(!next);
    }
  };

  if (loading) return <PageSpinner />;

  if (!article) {
    return (
      <div className="py-20 text-center text-muted-foreground">
        Article not found
      </div>
    );
  }

  return (
    <article className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center justify-between">
        <Link
          href="/feed"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Feed
        </Link>
        <Button
          variant={isBookmarked ? "secondary" : "outline"}
          size="sm"
          onClick={handleToggleBookmark}
        >
          {isBookmarked ? (
            <BookmarkCheck className="h-4 w-4" />
          ) : (
            <Bookmark className="h-4 w-4" />
          )}
          {isBookmarked ? "Saved" : "Save"}
        </Button>
      </div>

      <div className="mb-6">
        <div className="mb-3 flex flex-wrap gap-2">
          {article.category_name && (
            <Badge variant="secondary" className="bg-primary/10 text-primary">
              {article.category_name}
            </Badge>
          )}
          {article.sentiment && (
            <Badge
              variant={
                article.sentiment === "positive"
                  ? "success"
                  : article.sentiment === "negative"
                    ? "destructive"
                    : "secondary"
              }
            >
              {article.sentiment}
            </Badge>
          )}
          {article.credibility_score !== null &&
            article.credibility_score !== undefined && (
              <Badge variant="outline">
                Credibility: {formatScore(article.credibility_score)}
              </Badge>
            )}
        </div>

        <h1 className="mb-4 text-4xl font-bold tracking-tight">
          {article.title}
        </h1>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
          {article.author && <span>By {article.author}</span>}
          {article.source_name && <span>{article.source_name}</span>}
          <span>{formatDate(article.published_at)}</span>
        </div>
      </div>

      {article.summary && (
        <div className="mb-8 rounded-lg bg-muted p-4 italic text-muted-foreground">
          {article.summary}
        </div>
      )}

      <div className="prose prose-lg max-w-none dark:prose-invert">
        <div className="whitespace-pre-wrap leading-relaxed">
          {article.content || "Full content not available."}
        </div>
      </div>

      {article.tags.length > 0 && (
        <div className="mt-8 flex flex-wrap gap-2">
          {article.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full bg-secondary px-3 py-1 text-sm"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="mt-8">
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-primary hover:underline"
        >
          Read original source
          <ExternalLink className="h-4 w-4" />
        </a>
      </div>
    </article>
  );
}
