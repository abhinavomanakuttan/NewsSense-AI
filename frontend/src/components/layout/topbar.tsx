"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, Menu, Moon, Sun, User } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { NotificationsMenu } from "@/components/layout/notifications-menu";
import { cn } from "@/lib/utils";
import type { User as UserModel } from "@/types/models";

export function Topbar() {
  const router = useRouter();
  const { isDarkMode, toggleDarkMode, toggleSidebar, sidebarOpen } =
    useUIStore();
  const { user, setUser, logout } = useAuthStore();

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) return;

    api
      .get<UserModel>("/users/me")
      .then((u) => setUser(u))
      .catch(() => {
        logout();
        router.push("/login");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-background px-4 lg:px-6">
      <div className="flex items-center gap-2">
        <button
          onClick={toggleSidebar}
          className="flex h-10 w-10 items-center justify-center rounded-md hover:bg-accent lg:hidden"
          aria-label="Toggle sidebar"
        >
          <Menu className="h-5 w-5" />
        </button>
        {!sidebarOpen && (
          <span className="text-lg font-bold lg:hidden">SmartFeed</span>
        )}
      </div>

      <div className="flex items-center gap-1">
        <NotificationsMenu />

        <button
          onClick={toggleDarkMode}
          className="flex h-10 w-10 items-center justify-center rounded-md hover:bg-accent"
          aria-label="Toggle dark mode"
        >
          {isDarkMode ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
        </button>

        <div className="ml-2 flex items-center gap-3 border-l pl-3">
          <Link
            href="/settings"
            className="flex items-center gap-2 text-sm hover:text-primary"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
              <User className="h-4 w-4" />
            </span>
            <span className={cn("hidden sm:block")}>
              {user?.full_name || user?.username || "Account"}
            </span>
          </Link>
          <button
            onClick={handleLogout}
            className="flex h-10 w-10 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
            aria-label="Log out"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
