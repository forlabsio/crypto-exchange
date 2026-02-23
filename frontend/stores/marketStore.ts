import { create } from "zustand";

interface Ticker {
  pair: string;
  last_price: string;
  change_pct: string;
  high: string;
  low: string;
  volume: string;
}

interface Trade {
  price: string;
  qty: string;
  time: number;
  is_buyer_maker: boolean;
}

interface MarketStore {
  ticker: Ticker | null;
  orderbook: { bids: string[][]; asks: string[][] };
  trades: Trade[];
  connected: boolean;
  connect: (pair: string) => void;
  disconnect: () => void;
}

let ws: WebSocket | null = null;

export const useMarketStore = create<MarketStore>((set) => ({
  ticker: null,
  orderbook: { bids: [], asks: [] },
  trades: [],
  connected: false,

  connect: (pair: string) => {
    if (ws) ws.close();
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    ws = new WebSocket(`${wsUrl}/ws/market/${pair}`);

    ws.onopen = () => set({ connected: true });
    ws.onclose = () => set({ connected: false });
    ws.onerror = () => set({ connected: false });
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === "snapshot") {
          set({
            ticker: data.ticker && data.ticker.last_price ? data.ticker : null,
            orderbook: data.orderbook || { bids: [], asks: [] },
            trades: data.trades || [],
          });
        }
      } catch {
        // ignore parse errors
      }
    };
  },

  disconnect: () => {
    if (ws) {
      ws.close();
      ws = null;
    }
    set({ connected: false });
  },
}));
