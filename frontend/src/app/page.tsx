"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function Home() {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    setIsDark(mediaQuery.matches);
    const handler = (e: MediaQueryListEvent) => setIsDark(e.matches);
    mediaQuery.addEventListener("change", handler);
    return () => mediaQuery.removeEventListener("change", handler);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
  }, [isDark]);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b">
        <div className="container mx-auto flex items-center justify-between px-4 py-4">
          <h1 className="text-2xl font-bold text-primary">SmartFeed AI</h1>
          <nav className="flex items-center gap-4">
            <Link
              href="/login"
              className="text-sm font-medium hover:text-primary"
            >
              Login
            </Link>
            <Link
              href="/register"
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Get Started
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <section className="container mx-auto px-4 py-24 text-center">
          <h2 className="mb-6 text-5xl font-bold tracking-tight">
            AI-Powered News Intelligence
          </h2>
          <p className="mx-auto mb-8 max-w-2xl text-lg text-muted-foreground">
            Aggregate, analyze, and understand news from thousands of sources.
            Get personalized insights powered by advanced AI.
          </p>
          <div className="flex justify-center gap-4">
            <Link
              href="/register"
              className="rounded-lg bg-primary px-8 py-3 font-medium text-primary-foreground hover:bg-primary/90"
            >
              Start Free
            </Link>
            <Link
              href="/login"
              className="rounded-lg border px-8 py-3 font-medium hover:bg-secondary"
            >
              Sign In
            </Link>
          </div>
        </section>

        <section className="border-t py-16">
          <div className="container mx-auto px-4">
            <div className="grid gap-8 md:grid-cols-3">
              {[
                {
                  title: "Multi-Source Aggregation",
                  desc: "Collect news from RSS, APIs, and websites worldwide",
                },
                {
                  title: "AI Processing",
                  desc: "Classification, summarization, NER, and sentiment analysis",
                },
                {
                  title: "Personalized Feed",
                  desc: "Tailored recommendations based on your interests",
                },
              ].map((feature) => (
                <div key={feature.title} className="rounded-lg border p-6">
                  <h3 className="mb-2 text-xl font-semibold">
                    {feature.title}
                  </h3>
                  <p className="text-muted-foreground">{feature.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t py-6 text-center text-sm text-muted-foreground">
        <p>&copy; 2026 SmartFeed AI. All rights reserved.</p>
      </footer>
    </div>
  );
}
