"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MessageSquarePlus, Plus, SendHorizonal, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageSpinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import type {
  ChatMessageItem,
  ChatSource,
  ConversationItem,
} from "@/types/models";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
}

const GREETING: Message = {
  role: "assistant",
  content:
    "Hello! I'm your AI news assistant. Ask me anything about current events, topics, or the latest news.",
};

function formatDate(value: string | null): string {
  if (!value) return "";
  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export default function ChatbotPage() {
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const endRef = useRef<HTMLDivElement>(null);

  const fetchConversations = useCallback(async () => {
    try {
      const data = await api.get<{
        conversations: ConversationItem[];
        total: number;
      }>("/chat/conversations?limit=50");
      setConversations(data.conversations);
    } catch {
      setConversations([]);
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const scrollToBottom = () => {
    setTimeout(() => {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 50);
  };

  const resetChat = (newConversationId: string | null = null) => {
    setConversationId(newConversationId);
    setMessages([GREETING]);
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    scrollToBottom();

    try {
      const data = await api.post<{
        answer: string;
        sources: ChatSource[];
        conversation_id: string;
      }>("/chat", {
        message: text,
        conversation_id: conversationId ?? undefined,
      });
      setConversationId(data.conversation_id);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer, sources: data.sources },
      ]);
      fetchConversations();
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I encountered an error. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  };

  const loadConversation = async (id: string) => {
    setLoading(true);
    try {
      const history = await api.get<ChatMessageItem[]>(
        `/chat/conversations/${id}`,
      );
      setConversationId(id);
      setMessages(
        history.map((m) => ({
          role: m.role,
          content: m.content,
          sources: m.sources ?? undefined,
        })),
      );
      scrollToBottom();
    } catch {
      resetChat(null);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    try {
      await api.delete(`/chat/conversations/${id}`);
    } catch {
      fetchConversations();
      return;
    }
    if (conversationId === id) resetChat(null);
  };

  if (listLoading) return <PageSpinner />;

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      <aside className="hidden w-64 shrink-0 flex-col rounded-lg border bg-card md:flex">
        <div className="border-b p-3">
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start"
            onClick={() => resetChat(null)}
          >
            <Plus className="h-4 w-4" />
            New conversation
          </Button>
        </div>
        <div className="flex-1 space-y-1 overflow-y-auto p-2">
          {conversations.length === 0 ? (
            <p className="px-2 py-4 text-center text-sm text-muted-foreground">
              No conversations yet
            </p>
          ) : (
            conversations.map((c) => (
              <div
                key={c.id}
                className={cn(
                  "group flex cursor-pointer items-center justify-between rounded-md px-2 py-2 text-sm hover:bg-secondary",
                  conversationId === c.id && "bg-secondary",
                )}
                onClick={() => loadConversation(c.id)}
              >
                <span className="min-w-0 flex-1 truncate">
                  <span className="block truncate">
                    {c.title || "Untitled"}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {formatDate(c.updated_at)}
                  </span>
                </span>
                <button
                  onClick={(ev) => {
                    ev.stopPropagation();
                    handleDelete(c.id);
                  }}
                  className="ml-2 rounded p-1 text-muted-foreground opacity-0 hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                  aria-label="Delete conversation"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-3xl font-bold">AI News Assistant</h1>
          {conversationId && (
            <button
              onClick={() => resetChat(null)}
              className="flex items-center gap-1 text-sm text-muted-foreground hover:text-primary"
            >
              <MessageSquarePlus className="h-4 w-4" />
              New conversation
            </button>
          )}
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto rounded-lg border bg-card p-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn(
                "flex",
                msg.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              <div
                className={cn(
                  "max-w-[80%] rounded-lg px-4 py-3",
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary",
                )}
              >
                <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-2 border-t pt-2 text-xs text-muted-foreground">
                    <p className="mb-1 font-medium">Sources:</p>
                    {msg.sources.map((s, j) => (
                      <a
                        key={j}
                        href={s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block hover:text-primary"
                      >
                        {s.title}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="rounded-lg bg-secondary px-4 py-3">
                <div className="flex gap-1">
                  <div className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground" />
                  <div
                    className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground"
                    style={{ animationDelay: "0.1s" }}
                  />
                  <div
                    className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground"
                    style={{ animationDelay: "0.2s" }}
                  />
                </div>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <form onSubmit={handleSend} className="mt-4 flex gap-3">
          <Input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about news, events, or topics..."
            disabled={loading}
          />
          <Button type="submit" disabled={loading || !input.trim()}>
            <SendHorizonal className="h-4 w-4" />
            Send
          </Button>
        </form>
      </div>
    </div>
  );
}
