"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TokenResponse } from "@/types/api";

function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/feed";
  const setToken = useAuthStore((state) => state.setToken);
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    username: "",
    password: "",
    confirm: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange =
    (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
    };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (form.password !== form.confirm) {
      setError("Passwords do not match");
      return;
    }
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);
    try {
      await api.post("/auth/register", {
        full_name: form.full_name,
        email: form.email,
        username: form.username,
        password: form.password,
      });

      const data = await api.post<TokenResponse>("/auth/login", {
        email: form.email,
        password: form.password,
      });
      setToken(data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      router.push(next);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else if (err?.message) {
        setError(err.message);
      } else {
        setError("Unable to register. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-2xl">Create your account</CardTitle>
        <p className="text-sm text-muted-foreground">
          Get personalized news intelligence in minutes
        </p>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}
          <div className="space-y-2">
            <label htmlFor="full_name" className="text-sm font-medium">
              Full Name
            </label>
            <Input
              id="full_name"
              type="text"
              placeholder="Jane Doe"
              value={form.full_name}
              onChange={handleChange("full_name")}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="email" className="text-sm font-medium">
              Email
            </label>
            <Input
              id="email"
              type="email"
              required
              placeholder="you@example.com"
              value={form.email}
              onChange={handleChange("email")}
              autoComplete="email"
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="username" className="text-sm font-medium">
              Username
            </label>
            <Input
              id="username"
              type="text"
              required
              placeholder="janedoe"
              value={form.username}
              onChange={handleChange("username")}
              autoComplete="username"
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                Password
              </label>
              <Input
                id="password"
                type="password"
                required
                placeholder="Min 8 characters"
                value={form.password}
                onChange={handleChange("password")}
                autoComplete="new-password"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="confirm" className="text-sm font-medium">
                Confirm
              </label>
              <Input
                id="confirm"
                type="password"
                required
                placeholder="Repeat password"
                value={form.confirm}
                onChange={handleChange("confirm")}
                autoComplete="new-password"
              />
            </div>
          </div>
          <Button type="submit" className="w-full" loading={loading}>
            Create Account
          </Button>
        </form>

        <p className="mt-4 text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link
            href={`/login${next ? `?next=${encodeURIComponent(next)}` : ""}`}
            className="font-medium text-primary hover:underline"
          >
            Sign in
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={null}>
      <RegisterForm />
    </Suspense>
  );
}
