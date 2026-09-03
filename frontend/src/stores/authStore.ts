import { create } from "zustand";
import type { User } from "@/types/models";

interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  user: User | null;
  initialize: () => void;
  setToken: (token: string) => void;
  setUser: (user: User | null) => void;
  logout: () => void;
}

function getInitialToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export const useAuthStore = create<AuthState>((set) => ({
  token: getInitialToken(),
  isAuthenticated: Boolean(getInitialToken()),
  user: null,
  initialize: () => {
    const token = getInitialToken();
    set({ token, isAuthenticated: Boolean(token) });
  },
  setToken: (token: string) => {
    localStorage.setItem("access_token", token);
    set({ token, isAuthenticated: true });
  },
  setUser: (user: User | null) => set({ user }),
  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({ token: null, isAuthenticated: false, user: null });
  },
}));
