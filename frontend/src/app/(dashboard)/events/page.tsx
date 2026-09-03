"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CalendarDays, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { PageSpinner } from "@/components/ui/spinner";
import { formatDate, formatScore } from "@/lib/utils";
import type { Event } from "@/types/models";

export default function EventsPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const data = await api.get<Event[]>("/events?limit=50");
        setEvents(data);
      } catch {
        setEvents([]);
      } finally {
        setLoading(false);
      }
    };
    fetchEvents();
  }, []);

  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">News Events</h1>
        <Badge variant="outline" className="gap-1">
          <TrendingUp className="h-3 w-3" />
          {events.length} events
        </Badge>
      </div>

      {events.length === 0 ? (
        <EmptyState
          title="No events yet"
          description="Tracked news events will appear here as the pipeline detects them."
        />
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          {events.map((event) => (
            <Link
              key={event.id}
              href={`/events/${event.slug}`}
              className="rounded-lg border bg-card p-6 transition-shadow hover:shadow-md"
            >
              <div className="mb-2 flex items-center gap-2">
                <CalendarDays className="h-4 w-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">
                  {formatDate(event.start_date)}
                  {event.end_date && ` — ${formatDate(event.end_date)}`}
                </span>
              </div>
              <h2 className="mb-2 text-xl font-semibold hover:text-primary">
                {event.title}
              </h2>
              {event.summary && (
                <p className="mb-3 text-sm text-muted-foreground line-clamp-2">
                  {event.summary}
                </p>
              )}
              <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                <Badge variant="secondary">
                  {event.article_count} articles
                </Badge>
                <span>Importance: {formatScore(event.importance_score)}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
