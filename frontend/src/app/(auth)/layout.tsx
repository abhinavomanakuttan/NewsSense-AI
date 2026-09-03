"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Newspaper } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { initialize, isAuthenticated } = useAuthStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  useEffect(() => {
    if (isAuthenticated) {
      router.replace("/feed");
    }
  }, [isAuthenticated, router]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4">
      <div className="mb-8 flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary">
          <Newspaper className="h-6 w-6 text-primary-foreground" />
        </span>
        <span className="text-2xl font-bold">SmartFeed AI</span>
      </div>
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}
