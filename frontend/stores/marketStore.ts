import { create } from "zustand";

interface Ticker {
  pair: string;
  last_price: string;
  change_pct: string;
  high: string;
  low: string;
  volume: string;
  quote_volume: string;
}

interface Trade {
  price: string;
  qty: string;
  time: number;
  is_buyer_maker: boolean;
}

interface Kline {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_closed: boolean;
}

interface MarketStore {
  ticker: Ticker | null;
  orderbook: { bids: string[][]; asks: string[][] };
  trades: Trade[];
  latestKline: { interval: string; kline: Kline } | null;
  connected: boolean;
  connect: (pair: string) => void;
  disconnect: () => void;
}

let ws: WebSocket | null = null;
let lastOrderbookMs = 0; // throttle orderbook renders to max ~5/sec

export const useMarketStore = create<MarketStore>((set) => ({
  ticker: null,
  orderbook: { bids: [], asks: [] },
  trades: [],
  latestKline: null,
  connected: false,

  connect: (pair: string) => {
    if (ws) ws.close();
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const newWs = new WebSocket(`${wsUrl}/ws/market/${pair}`);
    ws = newWs;

    // Guard all handlers so stale WS events don't corrupt state after reconnect
    newWs.onopen = () => {
      if (ws === newWs) set({ connected: true });
    };
    newWs.onclose = () => {
      if (ws === newWs) set({ connected: false });
    };
    newWs.onerror = () => {
      if (ws === newWs) set({ connected: false });
    };
    newWs.onmessage = (e) => {
      if (ws !== newWs) return; // ignore messages from replaced connections
      try {
        const data = JSON.parse(e.data);
        if (data.type === "snapshot") {
          lastOrderbookMs = Date.now();
          set({
            ticker: data.ticker && data.ticker.last_price ? data.ticker : null,
            orderbook: data.orderbook || { bids: [], asks: [] },
            trades: data.trades || [],
          });
        } else if (data.type === "ticker" && data.ticker?.last_price) {
          set({ ticker: data.ticker });
        } else if (data.type === "orderbook" && data.orderbook) {
          // Throttle orderbook updates to max 5/sec (200ms) to reduce re-renders
          const now = Date.now();
          if (now - lastOrderbookMs >= 200) {
            lastOrderbookMs = now;
            set({ orderbook: data.orderbook });
          }
        } else if (data.type === "trade" && data.trade) {
          set((state) => ({
            trades: [data.trade, ...state.trades].slice(0, 50),
          }));
        } else if (data.type === "kline" && data.kline) {
          set({ latestKline: { interval: data.interval, kline: data.kline } });
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
    set({ connected: false, latestKline: null });
  },
}));
