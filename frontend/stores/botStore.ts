import { create } from "zustand";
import { apiFetch } from "@/lib/api";

export interface BotPerformance {
  win_rate: number;
  monthly_return_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  calculated_at?: string | null;
}

export interface Bot {
  id: number;
  name: string;
  description: string;
  strategy_type: string;
  status: string;
  monthly_fee: number;
  subscriber_count: number;
  operation_days: number;
  performance: BotPerformance;
  is_subscribed: boolean;
  subscribed_at?: string;
  allocated_usdt?: number;
  pnl_usdt?: number;
}

export interface BotTrade {
  id: number;
  pair: string;
  side: string;
  type: string;
  quantity: number;
  price: number | null;
  filled_quantity: number;
  status: string;
  created_at: string;
}

interface BotStore {
  bots: Bot[];
  myBots: Bot[];
  trades: Record<number, BotTrade[]>;
  fetchBots: () => Promise<void>;
  fetchMyBots: () => Promise<void>;
  fetchBotTrades: (botId: number) => Promise<void>;
  subscribe: (botId: number, allocatedUsdt?: number) => Promise<void>;
  unsubscribe: (botId: number, settle?: boolean) => Promise<void>;
}

export const useBotStore = create<BotStore>((set) => ({
  bots: [],
  myBots: [],
  trades: {},
  fetchBots: async () => {
    const data = await apiFetch("/api/bots");
    set({ bots: data });
  },
  fetchMyBots: async () => {
    const data = await apiFetch("/api/bots/my");
    set({ myBots: data });
  },
  fetchBotTrades: async (botId: number) => {
    const data = await apiFetch(`/api/bots/${botId}/trades`);
    set((s) => ({ trades: { ...s.trades, [botId]: data } }));
  },
  subscribe: async (botId, allocatedUsdt = 100) => {
    await apiFetch(`/api/bots/${botId}/subscribe`, {
      method: "POST",
      body: JSON.stringify({ allocated_usdt: allocatedUsdt }),
    });
  },
  unsubscribe: async (botId, settle = false) => {
    await apiFetch(`/api/bots/${botId}/subscribe?settle=${settle}`, { method: "DELETE" });
  },
}));
