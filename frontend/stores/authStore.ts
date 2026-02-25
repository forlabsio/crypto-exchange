import { create } from "zustand";
import { apiFetch } from "@/lib/api";

interface User {
  id: number;
  email: string | null;
  role: string;
  is_subscribed: boolean;
  wallet_address?: string | null;
}

interface AuthStore {
  token: string | null;
  user: User | null;
  setToken: (token: string | null) => void;
  login: (email: string, password: string) => Promise<void>;
  loginWithMetaMask: () => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hydrate: () => Promise<void>;
}

export const useAuthStore = create<AuthStore>((set) => ({
  token: null,
  user: null,
  setToken: (token) => set({ token }),
  hydrate: async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) { set({ token: null, user: null }); return; }
    set({ token });
    try {
      const user = await apiFetch("/api/auth/me");
      set({ user });
    } catch {
      set({ user: null });
    }
  },
  login: async (email, password) => {
    const data = await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    localStorage.setItem("token", data.access_token);
    set({ token: data.access_token });
    const user = await apiFetch("/api/auth/me");
    set({ user });
  },
  loginWithMetaMask: async () => {
    const win = window as any;
    if (!win.ethereum) throw new Error("MetaMask이 설치되지 않았습니다.");

    // Request account
    const accounts: string[] = await win.ethereum.request({ method: "eth_requestAccounts" });
    if (!accounts || accounts.length === 0) {
      throw new Error("MetaMask 계정을 가져올 수 없습니다.");
    }
    const address = accounts[0];

    // Get nonce from backend
    const nonceRes = await apiFetch("/api/auth/metamask/nonce", {
      method: "POST",
      body: JSON.stringify({ address }),
    });

    // Sign the message
    const signature = await win.ethereum.request({
      method: "personal_sign",
      params: [nonceRes.message, address],
    });

    // Verify and get JWT
    const verifyRes = await apiFetch("/api/auth/metamask/verify", {
      method: "POST",
      body: JSON.stringify({ address, signature }),
    });

    const token = verifyRes.access_token;
    // Temporarily set token in localStorage so apiFetch /me can use it
    localStorage.setItem("token", token);
    try {
      // Fetch user info
      const me = await apiFetch("/api/auth/me");
      set({ token, user: me });
    } catch (err) {
      // If /me fails, clean up the token
      localStorage.removeItem("token");
      throw err;
    }
  },
  register: async (email, password) => {
    await apiFetch("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },
  logout: () => {
    localStorage.removeItem("token");
    set({ token: null, user: null });
  },
}));
