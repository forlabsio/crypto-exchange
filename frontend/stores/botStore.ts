import { create } from "zustand";
import { apiFetch } from "@/lib/api";

interface Bot {
  id: number;
  name: string;
  description: string;
}

interface BotStore {
  bots: Bot[];
  fetchBots: () => Promise<void>;
  subscribe: (botId: number) => Promise<void>;
  unsubscribe: (botId: number) => Promise<void>;
}

export const useBotStore = create<BotStore>((set) => ({
  bots: [],
  fetchBots: async () => {
    const data = await apiFetch("/api/bots");
    set({ bots: data });
  },
  subscribe: async (botId) => {
    await apiFetch(`/api/bots/${botId}/subscribe`, { method: "POST" });
  },
  unsubscribe: async (botId) => {
    await apiFetch(`/api/bots/${botId}/subscribe`, { method: "DELETE" });
  },
}));
