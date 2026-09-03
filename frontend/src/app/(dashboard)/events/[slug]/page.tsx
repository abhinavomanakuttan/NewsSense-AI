"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, CalendarDays, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { ArticleCard } from "@/components/articles/article-card";
import { formatDate, formatScore } from "@/lib/utils";
import type { Event, EventArticle } from "@/types/models";

export default function EventDetailPage() {
  const params = useParams();
  const slug = Array.isArray(params.slug) ? params.slug[0] : params.slug;
  const [event, setEvent] = useState<Event | null>(null);
  const [articles, setArticles] = useState<EventArticle[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEvent = async () => {
      if (!slug) return;
      try {
        const data = await api.get<Event>(`/events/${slug}`);
        setEvent(data);

        const articleData = await api.get<EventArticle[]>(
          `/events/${data.id}/articles`,
        );
        setArticles(articleData);
      } catch {
        setEvent(null);
      } finally {
        setLoading(false);
      }
    };
    fetchEvent();
  }, [slug]);

  if (loading) return <PageSpinner />;

  if (!event) {
    return (
      <div className="py-20 text-center text-muted-foreground">
        Event not found
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <Link
        href="/events"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Events
      </Link>

      <div>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className="gap-1">
            <CalendarDays className="h-3 w-3" />
            {formatDate(event.start_date)}
            {event.end_date && ` — ${formatDate(event.end_date)}`}
          </Badge>
          <Badge variant="outline" className="gap-1">
            <TrendingUp className="h-3 w-3" />
            Importance: {formatScore(event.importance_score)}
          </Badge>
          <Badge variant="secondary">{event.article_count} articles</Badge>
        </div>
        <h1 className="mb-4 text-4xl font-bold tracking-tight">
          {event.title}
        </h1>
        {event.description && (
          <p className="max-w-3xl text-muted-foreground">{event.description}</p>
        )}
      </div>

      {event.timeline && (
        <div className="rounded-lg border bg-card p-4">
          <h2 className="mb-2 text-sm font-semibold text-muted-foreground">
            Timeline
          </h2>
          <p className="whitespace-pre-wrap text-sm">{event.timeline}</p>
        </div>
      )}

      <div className="space-y-4">
        <h2 className="text-2xl font-semibold">Related Articles</h2>
        {articles.length === 0 ? (
          <EmptyState
            title="No articles linked yet"
            description="Articles connected to this event will show up here."
          />
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {articles.map((article) => (
              <ArticleCard
                key={article.id}
                id={article.id}
                title={article.title}
                slug={article.slug}
                summary={article.summary}
                sourceName={article.source_name}
                publishedAt={article.published_at}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
