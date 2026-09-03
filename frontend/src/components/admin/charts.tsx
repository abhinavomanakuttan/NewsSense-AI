"use client";

import { cn } from "@/lib/utils";

export interface ChartPoint {
  label: string;
  value: number;
}

export function BarChart({
  points,
  height = 180,
}: {
  points: ChartPoint[];
  height?: number;
}) {
  const max = Math.max(...points.map((p) => p.value), 1);
  return (
    <div>
      <div className="flex items-end gap-1.5" style={{ height }}>
        {points.map((p) => (
          <div
            key={p.label}
            className="flex flex-1 flex-col items-center justify-end gap-1 self-stretch"
          >
            <span className="text-xs font-semibold text-primary">
              {p.value}
            </span>
            <div
              className="w-full rounded-t bg-primary/80"
              style={{
                height: `${Math.max((p.value / max) * 100, p.value > 0 ? 4 : 2)}%`,
              }}
              title={`${p.label}: ${p.value}`}
            />
          </div>
        ))}
      </div>
      <div className="mt-1 flex gap-1.5">
        {points.map((p) => (
          <span
            key={p.label}
            className="flex-1 truncate text-center text-[10px] text-muted-foreground"
          >
            {p.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export function LabeledBars({
  items,
  className,
}: {
  items: ChartPoint[];
  className?: string;
}) {
  const max = Math.max(...items.map((it) => it.value), 1);
  return (
    <div className={cn("space-y-3", className)}>
      {items.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No data yet
        </p>
      ) : (
        items.map((it) => (
          <div key={it.label}>
            <div className="mb-1 flex items-center justify-between gap-2 text-xs">
              <span className="truncate font-medium">{it.label}</span>
              <span className="shrink-0 text-muted-foreground">{it.value}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${(it.value / max) * 100}%` }}
              />
            </div>
          </div>
        ))
      )}
    </div>
  );
}
