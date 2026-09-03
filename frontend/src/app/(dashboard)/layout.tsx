"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { cn } from "@/lib/utils";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, initialize, token } = useAuthStore();
  const { sidebarOpen } = useUIStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  useEffect(() => {
    if (!isAuthenticated && token === null && pathname) {
      router.push(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [isAuthenticated, token, pathname, router]);

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar isOpen={sidebarOpen} />
      <div
        className={cn(
          "flex min-w-0 flex-1 flex-col",
          sidebarOpen ? "lg:ml-0" : "lg:ml-0",
        )}
      >
        <Topbar />
        <main className="flex-1 overflow-auto">
          <div className="container mx-auto max-w-7xl px-4 py-6 lg:px-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
