"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  BookOpen,
  Calendar,
  Globe,
  Radio,
  Search,
  Shield,
  TrendingUp,
  Users,
} from "lucide-react";
import { api } from "@/lib/api";
import { BarChart, LabeledBars } from "@/components/admin/charts";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageSpinner } from "@/components/ui/spinner";
import { formatTimeAgo } from "@/lib/utils";
import type {
  AnalyticsEventItem,
  AnalyticsOverview,
  CategoryStats,
  DailyCount,
  SentimentStats,
  SourceStats,
  UserActivityStats,
} from "@/types/models";

const DAY_RANGES = [7, 14, 30] as const;

export default function AdminPage() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [activity, setActivity] = useState<UserActivityStats[]>([]);
  const [articlesTrend, setArticlesTrend] = useState<DailyCount[]>([]);
  const [categories, setCategories] = useState<CategoryStats[]>([]);
  const [sources, setSources] = useState<SourceStats[]>([]);
  const [sentiment, setSentiment] = useState<SentimentStats[]>([]);
  const [events, setEvents] = useState<AnalyticsEventItem[]>([]);
  const [days, setDays] = useState<number>(14);
  const [error, setError] = useState("");

  const fetchSeries = useCallback(async (range: number) => {
    try {
      const [activityData, trendData] = await Promise.all([
        api.get<UserActivityStats[]>(`/analytics/activity?days=${range}`),
        api.get<DailyCount[]>(`/analytics/articles-trend?days=${range}`),
      ]);
      setActivity(activityData);
      setArticlesTrend(trendData);
      setError("");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load analytics. Admin access required.",
      );
    }
  }, []);

  useEffect(() => {
    const load = async () => {
      try {
        const [
          overviewData,
          categoryData,
          sourceData,
          sentimentData,
          eventData,
        ] = await Promise.all([
          api.get<AnalyticsOverview>("/analytics/overview"),
          api.get<CategoryStats[]>("/analytics/categories"),
          api.get<SourceStats[]>("/analytics/sources"),
          api.get<SentimentStats[]>("/analytics/sentiment"),
          api.get<{ events: AnalyticsEventItem[] }>(
            "/analytics/events?limit=8",
          ),
        ]);
        setOverview(overviewData);
        setCategories(categoryData);
        setSources(sourceData);
        setSentiment(sentimentData);
        setEvents(eventData.events);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load analytics. Admin access required.",
        );
      }
    };
    load();
  }, []);

  useEffect(() => {
    fetchSeries(days);
  }, [days, fetchSeries]);

  if (error) {
    return (
      <div className="py-20 text-center text-destructive">
        <p className="text-lg font-semibold">Access denied</p>
        <p className="mt-2 text-sm">{error}</p>
      </div>
    );
  }

  if (!overview) return <PageSpinner />;

  const stats = [
    { label: "Total Users", value: overview.total_users, icon: Users },
    {
      label: "Active Today",
      value: overview.active_users_today,
      icon: Activity,
    },
    { label: "Total Articles", value: overview.total_articles, icon: BookOpen },
    { label: "Articles Today", value: overview.articles_today, icon: Radio },
    { label: "Total Sources", value: overview.total_sources, icon: Globe },
    { label: "Active Sources", value: overview.active_sources, icon: Radio },
    { label: "Total Searches", value: overview.total_searches, icon: Search },
    { label: "Total Events", value: overview.total_events, icon: Calendar },
  ];

  const shortDate = (iso: string) => iso.slice(5);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Shield className="h-7 w-7 text-primary" />
          <h1 className="text-3xl font-bold">Admin Dashboard</h1>
        </div>
        <div className="flex items-center gap-1 rounded-lg border p-1">
          {DAY_RANGES.map((range) => (
            <button
              key={range}
              type="button"
              onClick={() => setDays(range)}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                days === range
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {range}d
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <Card key={stat.label}>
              <CardContent className="flex items-center gap-4 p-6">
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <Icon className="h-6 w-6 text-primary" />
                </span>
                <div>
                  <p className="text-3xl font-bold text-primary">
                    {stat.value}
                  </p>
                  <p className="text-sm text-muted-foreground">{stat.label}</p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-primary" /> Daily User Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <BarChart
              height={160}
              points={activity.map((day) => ({
                label: shortDate(day.date),
                value: day.active_users,
              }))}
            />
            <div className="mt-4 grid grid-cols-3 gap-4 border-t pt-4 text-center">
              {(
                [
                  ["Page Views", "page_views"],
                  ["Searches", "searches"],
                  ["Bookmarks", "bookmarks"],
                ] as const
              ).map(([label, key]) => (
                <div key={key}>
                  <p className="text-xl font-bold text-primary">
                    {activity.reduce((sum, day) => sum + day[key], 0)}
                  </p>
                  <p className="text-xs text-muted-foreground">{label}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" /> Articles Over Time
            </CardTitle>
          </CardHeader>
          <CardContent>
            <BarChart
              height={160}
              points={articlesTrend.map((day) => ({
                label: shortDate(day.date),
                value: day.count,
              }))}
            />
            <div className="mt-4 flex items-center justify-between border-t pt-4 text-sm">
              <span className="text-muted-foreground">Total in period</span>
              <span className="text-xl font-bold text-primary">
                {articlesTrend.reduce((sum, day) => sum + day.count, 0)}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Articles by Category</CardTitle>
          </CardHeader>
          <CardContent>
            <LabeledBars
              items={categories.map((c) => ({
                label: c.category ?? "Uncategorized",
                value: c.article_count,
              }))}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Articles by Source</CardTitle>
          </CardHeader>
          <CardContent>
            <LabeledBars
              items={sources.map((s) => ({
                label: s.source,
                value: s.article_count,
              }))}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sentiment</CardTitle>
          </CardHeader>
          <CardContent>
            <LabeledBars
              items={sentiment.map((s) => ({
                label: s.sentiment,
                value: s.count,
              }))}
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Events</CardTitle>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <EmptyState
              title="No events recorded"
              description="Tracked analytics events will appear here."
            />
          ) : (
            <div className="divide-y">
              {events.map((event) => (
                <div
                  key={event.id}
                  className="flex items-center justify-between gap-4 py-3"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <Badge variant="secondary">{event.event_type}</Badge>
                    <span className="truncate text-sm text-muted-foreground">
                      {event.user_id
                        ? `user ${event.user_id.slice(0, 8)}`
                        : "anonymous"}
                    </span>
                  </div>
                  <div className="flex shrink-0 items-center gap-3 text-sm text-muted-foreground">
                    {event.value !== null && (
                      <span className="font-semibold text-primary">
                        {event.value}
                      </span>
                    )}
                    <span>{formatTimeAgo(event.timestamp)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Link
              href="/admin/system-health"
              className="rounded-lg border p-4 text-sm font-medium transition-colors hover:border-primary/50"
            >
              System Health
            </Link>
            <Link
              href="/feed"
              className="rounded-lg border p-4 text-sm font-medium transition-colors hover:border-primary/50"
            >
              View Live Feed
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
