"use client";

import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { PageSpinner } from "@/components/ui/spinner";
import { useUIStore } from "@/stores/uiStore";
import type { Category, UserPreferences } from "@/types/models";
import { cn } from "@/lib/utils";

const LANGUAGES = ["en", "es", "fr", "de", "hi", "zh", "ar", "ja"];

const EMPTY_PREFS: UserPreferences = {
  preferred_categories: [],
  preferred_sources: [],
  preferred_languages: ["en"],
  preferred_regions: [],
  notification_enabled: true,
  dark_mode: false,
  email_digest_frequency: "daily",
};

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<UserPreferences>(EMPTY_PREFS);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const toggleDarkMode = useUIStore((state) => state.toggleDarkMode);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [prefsData, categoriesData] = await Promise.all([
          api.get<UserPreferences>("/users/me/preferences"),
          api.get<Category[]>("/categories"),
        ]);
        setPrefs({ ...EMPTY_PREFS, ...prefsData });
        setCategories(categoriesData);
      } catch {
        setPrefs(EMPTY_PREFS);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const toggleCategory = (id: string) => {
    setPrefs((prev) => ({
      ...prev,
      preferred_categories: prev.preferred_categories.includes(id)
        ? prev.preferred_categories.filter((c) => c !== id)
        : [...prev.preferred_categories, id],
    }));
  };

  const toggleLanguage = (lang: string) => {
    setPrefs((prev) => ({
      ...prev,
      preferred_languages: prev.preferred_languages.includes(lang)
        ? prev.preferred_languages.filter((l) => l !== lang)
        : [...prev.preferred_languages, lang],
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await api.put("/users/me/preferences", {
        preferred_categories: prefs.preferred_categories,
        preferred_languages: prefs.preferred_languages,
        notification_enabled: prefs.notification_enabled,
        email_digest_frequency: prefs.email_digest_frequency,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <PageSpinner />;

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Settings</h1>
        <Button onClick={handleSave} loading={saving}>
          {saved ? (
            <>
              <Check className="h-4 w-4" />
              Saved
            </>
          ) : (
            "Save Changes"
          )}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>News Preferences</CardTitle>
          <p className="text-sm text-muted-foreground">
            Pick categories to shape your personalized feed.
          </p>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {categories.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No categories available.
              </p>
            ) : (
              categories.map((cat) => {
                const selected = prefs.preferred_categories.includes(cat.id);
                return (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => toggleCategory(cat.id)}
                    className={cn(
                      "rounded-full border px-4 py-1.5 text-sm transition-colors",
                      selected
                        ? "border-primary bg-primary text-primary-foreground"
                        : "hover:border-primary/50",
                    )}
                  >
                    {cat.name}
                  </button>
                );
              })
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Languages</CardTitle>
          <p className="text-sm text-muted-foreground">
            Prefer articles in these languages.
          </p>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {LANGUAGES.map((lang) => {
              const selected = prefs.preferred_languages.includes(lang);
              return (
                <button
                  key={lang}
                  type="button"
                  onClick={() => toggleLanguage(lang)}
                  className={cn(
                    "rounded-full border px-4 py-1.5 text-sm uppercase transition-colors",
                    selected
                      ? "border-primary bg-primary text-primary-foreground"
                      : "hover:border-primary/50",
                  )}
                >
                  {lang}
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Notifications & Digest</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <label className="flex cursor-pointer items-center justify-between">
            <div>
              <p className="font-medium">Email notifications</p>
              <p className="text-sm text-muted-foreground">
                Receive news alerts and updates
              </p>
            </div>
            <input
              type="checkbox"
              checked={prefs.notification_enabled}
              onChange={(e) =>
                setPrefs((prev) => ({
                  ...prev,
                  notification_enabled: e.target.checked,
                }))
              }
              className="h-5 w-5 rounded border-input accent-primary"
            />
          </label>

          <div className="space-y-2">
            <label htmlFor="digest" className="text-sm font-medium">
              Email digest frequency
            </label>
            <Select
              id="digest"
              value={prefs.email_digest_frequency}
              onChange={(e) =>
                setPrefs((prev) => ({
                  ...prev,
                  email_digest_frequency: e.target.value,
                }))
              }
              className="w-48"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="never">Never</option>
            </Select>
          </div>

          <label className="flex cursor-pointer items-center justify-between">
            <div>
              <p className="font-medium">Dark mode</p>
              <p className="text-sm text-muted-foreground">
                Toggle the app theme
              </p>
            </div>
            <input
              type="checkbox"
              checked={prefs.dark_mode}
              onChange={(e) => {
                const checked = e.target.checked;
                setPrefs((prev) => ({ ...prev, dark_mode: checked }));
                if (checked !== useUIStore.getState().isDarkMode) {
                  toggleDarkMode();
                }
              }}
              className="h-5 w-5 rounded border-input accent-primary"
            />
          </label>
        </CardContent>
      </Card>
    </div>
  );
}
