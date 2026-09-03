"use client";

import { useEffect, useState } from "react";
import { Activity, CheckCircle2, Database, Server, Wifi } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageSpinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

interface SystemHealth {
  status: string;
  services: Record<string, string>;
}

const SERVICE_ICONS: Record<string, React.ReactNode> = {
  api: <Server className="h-4 w-4" />,
  database: <Database className="h-4 w-4" />,
  redis: <Wifi className="h-4 w-4" />,
  celery: <Activity className="h-4 w-4" />,
};

export default function SystemHealthPage() {
  const [health, setHealth] = useState<SystemHealth | null>(null);

  useEffect(() => {
    api
      .get<SystemHealth>("/admin/system/health")
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  if (!health) return <PageSpinner />;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-3xl font-bold">System Health</h1>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle2
              className={cn(
                "h-5 w-5",
                health.status === "healthy"
                  ? "text-green-500"
                  : "text-destructive",
              )}
            />
            {health.status}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Object.entries(health.services).map(([name, status]) => (
              <div
                key={name}
                className="flex items-center justify-between rounded-lg border px-4 py-3"
              >
                <span className="flex items-center gap-2 text-sm font-medium capitalize">
                  {SERVICE_ICONS[name] ?? <Server className="h-4 w-4" />}
                  {name}
                </span>
                <span
                  className={cn(
                    "rounded-full px-2.5 py-0.5 text-xs font-semibold",
                    status === "up"
                      ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200"
                      : "bg-destructive/10 text-destructive",
                  )}
                >
                  {status}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
