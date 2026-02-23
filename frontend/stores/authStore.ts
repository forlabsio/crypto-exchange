import { create } from "zustand";
import { apiFetch } from "@/lib/api";

interface AuthStore {
  token: string | null;
  setToken: (token: string | null) => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthStore>((set) => ({
  token: null,
  setToken: (token) => set({ token }),
  hydrate: () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    set({ token });
  },
  login: async (email, password) => {
    const data = await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    localStorage.setItem("token", data.access_token);
    set({ token: data.access_token });
  },
  register: async (email, password) => {
    await apiFetch("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },
  logout: () => {
    localStorage.removeItem("token");
    set({ token: null });
  },
}));
