import { Bookmark, BookmarkCheck, Clock } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatScore, formatTimeAgo } from "@/lib/utils";

interface ArticleCardProps {
  id: string;
  title: string;
  slug: string;
  summary?: string | null;
  sourceName?: string | null;
  categoryName?: string | null;
  imageUrl?: string | null;
  publishedAt?: string | null;
  sentiment?: string | null;
  credibilityScore?: number | null;
  isBookmarked?: boolean;
  onToggleBookmark?: (id: string) => void;
  reason?: string | null;
  action?: React.ReactNode;
}

export function ArticleCard({
  id,
  title,
  slug,
  summary,
  sourceName,
  categoryName,
  imageUrl,
  publishedAt,
  sentiment,
  credibilityScore,
  isBookmarked,
  onToggleBookmark,
  reason,
  action,
}: ArticleCardProps) {
  return (
    <Link
      href={`/article/${slug}`}
      className="group flex flex-col overflow-hidden rounded-lg border bg-card transition-shadow hover:shadow-lg"
    >
      {imageUrl && (
        <div className="aspect-video overflow-hidden bg-muted">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt={title}
            className="h-full w-full object-cover transition-transform group-hover:scale-105"
          />
        </div>
      )}
      <div className="flex flex-1 flex-col p-4">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          {categoryName && (
            <Badge variant="secondary" className="bg-primary/10 text-primary">
              {categoryName}
            </Badge>
          )}
          {credibilityScore !== null && credibilityScore !== undefined && (
            <Badge variant={credibilityScore > 0.7 ? "success" : "warning"}>
              {formatScore(credibilityScore)} credible
            </Badge>
          )}
        </div>

        <h2 className="mb-2 font-semibold leading-snug line-clamp-2 group-hover:text-primary">
          {title}
        </h2>

        {summary && (
          <p className="mb-3 text-sm text-muted-foreground line-clamp-2">
            {summary}
          </p>
        )}

        {reason && (
          <p className="mb-3 text-xs italic text-muted-foreground">{reason}</p>
        )}

        <div className="mt-auto flex items-center justify-between text-xs text-muted-foreground">
          <span className="flex items-center gap-1 truncate">{sourceName}</span>
          <span className="flex shrink-0 items-center gap-3">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatTimeAgo(publishedAt)}
            </span>
            {action ??
              (onToggleBookmark && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={(e) => {
                    e.preventDefault();
                    onToggleBookmark(id);
                  }}
                  aria-label={isBookmarked ? "Remove bookmark" : "Add bookmark"}
                >
                  {isBookmarked ? (
                    <BookmarkCheck className="h-4 w-4 text-primary" />
                  ) : (
                    <Bookmark className="h-4 w-4" />
                  )}
                </Button>
              ))}
          </span>
        </div>

        {sentiment && (
          <Badge
            variant={
              sentiment === "positive"
                ? "success"
                : sentiment === "negative"
                  ? "destructive"
                  : "secondary"
            }
            className="mt-2 w-fit"
          >
            {sentiment}
          </Badge>
        )}
      </div>
    </Link>
  );
}
