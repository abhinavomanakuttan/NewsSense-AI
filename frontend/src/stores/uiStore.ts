import { create } from "zustand";

const DARK_MODE_KEY = "smartfeed_dark_mode";

function getInitialDarkMode(): boolean {
  if (typeof window === "undefined") return false;
  const stored = localStorage.getItem(DARK_MODE_KEY);
  if (stored !== null) return stored === "true";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

interface UIState {
  isDarkMode: boolean;
  sidebarOpen: boolean;
  toggleDarkMode: () => void;
  toggleSidebar: () => void;
}

function applyDarkMode(dark: boolean) {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle("dark", dark);
}

export const useUIStore = create<UIState>((set) => ({
  isDarkMode: getInitialDarkMode(),
  sidebarOpen: true,
  toggleDarkMode: () =>
    set((state) => {
      const newDark = !state.isDarkMode;
      localStorage.setItem(DARK_MODE_KEY, String(newDark));
      applyDarkMode(newDark);
      return { isDarkMode: newDark };
    }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}));

if (typeof window !== "undefined") {
  applyDarkMode(getInitialDarkMode());
}
