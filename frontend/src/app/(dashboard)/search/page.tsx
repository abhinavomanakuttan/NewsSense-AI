"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight, Search as SearchIcon } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Select } from "@/components/ui/select";
import { formatDate, formatScore } from "@/lib/utils";
import type {
  Category,
  SearchResponse,
  SearchResultItem,
  Source,
} from "@/types/models";

const LANGUAGES = ["en", "es", "fr", "de", "hi", "zh", "ar", "ja"];
const SENTIMENTS = ["positive", "neutral", "negative"];
const SORT_OPTIONS = [
  { value: "relevance", label: "Relevance" },
  { value: "date", label: "Date" },
  { value: "view_count", label: "Most Viewed" },
  { value: "credibility", label: "Credibility" },
];
const PAGE_SIZE = 10;

function renderHighlight(
  highlights: SearchResultItem["highlights"],
  field: string,
): string | null {
  const value = highlights?.[field];
  if (typeof value !== "string") return null;
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/&lt;(\/?)em&gt;/g, "<$1em>");
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [language, setLanguage] = useState("");
  const [sentiment, setSentiment] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sortBy, setSortBy] = useState("relevance");

  const [categories, setCategories] = useState<Category[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<Category[]>("/categories")
      .then(setCategories)
      .catch(() => {});
    api
      .get<Source[]>("/sources?limit=200")
      .then((items) => setSources(items.filter((s) => s.is_active)))
      .catch(() => {});
  }, []);

  const runSearch = async (page = 1) => {
    if (!query.trim()) return;

    setLoading(true);
    setError("");
    setSearched(true);

    try {
      const data = await api.post<SearchResponse>("/search", {
        query,
        page,
        page_size: PAGE_SIZE,
        category: category || null,
        source: source || null,
        language: language || null,
        sentiment: sentiment || null,
        date_from: dateFrom ? `${dateFrom}T00:00:00` : null,
        date_to: dateTo ? `${dateTo}T23:59:59` : null,
        sort_by: sortBy,
        sort_order: "desc",
      });
      setResults(data);
    } catch {
      setResults(null);
      setError("Search failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runSearch(1);
  };

  const hasFilters =
    category || source || language || sentiment || dateFrom || dateTo;

  const clearFilters = () => {
    setCategory("");
    setSource("");
    setLanguage("");
    setSentiment("");
    setDateFrom("");
    setDateTo("");
  };

  const totalPages = results
    ? Math.max(1, Math.ceil(results.total / PAGE_SIZE))
    : 1;

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Search News</h1>

      <form onSubmit={handleSubmit} className="flex gap-3">
        <div className="relative flex-1">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search articles, topics, keywords..."
            className="pl-9"
          />
        </div>
        <Button type="submit" loading={loading}>
          Search
        </Button>
      </form>

      <div className="grid gap-3 rounded-lg border bg-card p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          aria-label="Category"
        >
          <option value="">All Categories</option>
          {categories.map((cat) => (
            <option key={cat.id} value={cat.name}>
              {cat.name}
            </option>
          ))}
        </Select>
        <Select
          value={source}
          onChange={(e) => setSource(e.target.value)}
          aria-label="Source"
        >
          <option value="">All Sources</option>
          {sources.map((s) => (
            <option key={s.id} value={s.name}>
              {s.name}
            </option>
          ))}
        </Select>
        <Select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          aria-label="Language"
        >
          <option value="">All Languages</option>
          {LANGUAGES.map((lang) => (
            <option key={lang} value={lang}>
              {lang.toUpperCase()}
            </option>
          ))}
        </Select>
        <Select
          value={sentiment}
          onChange={(e) => setSentiment(e.target.value)}
          aria-label="Sentiment"
        >
          <option value="">All Sentiment</option>
          {SENTIMENTS.map((s) => (
            <option key={s} value={s}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          ))}
        </Select>
        <Input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          aria-label="From date"
        />
        <Input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          aria-label="To date"
        />
        <Select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          aria-label="Sort by"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </Select>
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={() => runSearch(1)}>
            Apply
          </Button>
          {hasFilters && (
            <Button type="button" variant="ghost" onClick={clearFilters}>
              Clear
            </Button>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {searched && results && (
        <p className="text-sm text-muted-foreground">
          Found {results.total} result{results.total !== 1 ? "s" : ""} for
          &ldquo;{results.query}&rdquo;
          {hasFilters && " with filters applied"}
        </p>
      )}

      {results && results.results.length === 0 && !loading ? (
        <EmptyState
          title="No results found"
          description="Try a different search term, clear some filters, or use more general keywords."
        />
      ) : (
        <div className="space-y-4">
          {results?.results.map((result) => (
            <Link
              key={result.id}
              href={`/article/${result.slug}`}
              className="block rounded-lg border bg-card p-4 transition-shadow hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    {result.category_name && (
                      <Badge variant="secondary">{result.category_name}</Badge>
                    )}
                    <h2
                      className="font-semibold hover:text-primary"
                      dangerouslySetInnerHTML={{
                        __html:
                          renderHighlight(result.highlights, "title") ??
                          result.title,
                      }}
                    />
                  </div>
                  {renderHighlight(result.highlights, "summary") ? (
                    <p
                      className="mb-2 text-sm text-muted-foreground line-clamp-2"
                      dangerouslySetInnerHTML={{
                        __html: renderHighlight(
                          result.highlights,
                          "summary",
                        ) as string,
                      }}
                    />
                  ) : (
                    result.summary && (
                      <p className="mb-2 text-sm text-muted-foreground line-clamp-2">
                        {result.summary}
                      </p>
                    )
                  )}
                  <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                    {result.source_name && <span>{result.source_name}</span>}
                    <span>{formatDate(result.published_at)}</span>
                    <Badge
                      variant="outline"
                      className="px-1.5 py-0 text-[10px]"
                    >
                      {formatScore(result.score)} relevant
                    </Badge>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {searched && loading && (
        <div className="py-12 text-center text-muted-foreground">
          Searching...
        </div>
      )}

      {results && results.total > 0 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {results.page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={results.page <= 1 || loading}
              onClick={() => runSearch(results.page - 1)}
            >
              <ChevronLeft className="mr-1 h-4 w-4" /> Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={results.page >= totalPages || loading}
              onClick={() => runSearch(results.page + 1)}
            >
              Next <ChevronRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
