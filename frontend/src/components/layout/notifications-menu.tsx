"use client";

import { useEffect, useRef, useState } from "react";
import { Bell, CheckCheck } from "lucide-react";
import { api } from "@/lib/api";
import { formatTimeAgo } from "@/lib/utils";
import type { Notification } from "@/types/models";
import { cn } from "@/lib/utils";

const PING_INTERVAL_MS = 30_000;
const MAX_RECONNECT_DELAY_MS = 30_000;

function buildWsUrl(token: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/v1/ws/notifications?token=${encodeURIComponent(token)}`;
}

export function NotificationsMenu() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const ref = useRef<HTMLDivElement>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptRef = useRef(0);
  const openRef = useRef(open);
  openRef.current = open;

  const fetchNotifications = async () => {
    try {
      const data = await api.get<{
        notifications: Notification[];
        unread_count: number;
      }>("/notifications?limit=20");
      setNotifications(data.notifications);
      setUnread(data.unread_count);
    } catch {
      // Ignore - notifications are non-critical
    } finally {
      setLoading(false);
    }
  };

  const connect = () => {
    const token = localStorage.getItem("access_token");
    if (!token) return;

    const socket = new WebSocket(buildWsUrl(token));
    socketRef.current = socket;

    socket.onopen = () => {
      attemptRef.current = 0;
      pingRef.current = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: "ping" }));
        }
      }, PING_INTERVAL_MS);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "notification" && data.notification) {
          const notification = data.notification as Notification;
          setNotifications((prev) => [
            notification,
            ...prev.filter((n) => n.id !== notification.id),
          ]);
          setUnread((prev) => prev + 1);
        }
      } catch {
        // Ignore malformed frames
      }
    };

    socket.onclose = () => {
      if (pingRef.current) {
        clearInterval(pingRef.current);
        pingRef.current = null;
      }
      socketRef.current = null;
      const delay = Math.min(
        1000 * 2 ** attemptRef.current,
        MAX_RECONNECT_DELAY_MS,
      );
      attemptRef.current += 1;
      reconnectRef.current = setTimeout(connect, delay);
    };

    socket.onerror = () => {
      socket.close();
    };
  };

  useEffect(() => {
    fetchNotifications();
    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (pingRef.current) clearInterval(pingRef.current);
      socketRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const markAsRead = async (id: string) => {
    try {
      await api.put(`/notifications/${id}/read`);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
      );
      setUnread((prev) => Math.max(0, prev - 1));
    } catch {
      // ignore
    }
  };

  const markAllRead = async () => {
    try {
      await api.put("/notifications/read-all");
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnread(0);
    } catch {
      // ignore
    }
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="relative flex h-10 w-10 items-center justify-center rounded-md hover:bg-accent"
        aria-label="Notifications"
      >
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-destructive-foreground">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-12 z-50 w-96 max-w-[calc(100vw-2rem)] overflow-hidden rounded-lg border bg-card shadow-lg">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <h3 className="text-sm font-semibold">Notifications</h3>
            {unread > 0 && (
              <button
                onClick={markAllRead}
                className="flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <CheckCheck className="h-3.5 w-3.5" />
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {loading ? (
              <p className="p-4 text-center text-sm text-muted-foreground">
                Loading...
              </p>
            ) : notifications.length === 0 ? (
              <p className="p-4 text-center text-sm text-muted-foreground">
                No notifications yet
              </p>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  onClick={() => !n.is_read && markAsRead(n.id)}
                  className={cn(
                    "block w-full border-b px-4 py-3 text-left transition-colors last:border-0 hover:bg-accent",
                    !n.is_read && "bg-primary/5",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium">{n.title}</p>
                    {!n.is_read && (
                      <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary" />
                    )}
                  </div>
                  {n.body && (
                    <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                      {n.body}
                    </p>
                  )}
                  <p className="mt-1 text-xs text-muted-foreground">
                    {formatTimeAgo(n.created_at)}
                  </p>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
