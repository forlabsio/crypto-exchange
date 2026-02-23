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
          // Initial full snapshot on connect
          set({
            ticker: data.ticker && data.ticker.last_price ? data.ticker : null,
            orderbook: data.orderbook || { bids: [], asks: [] },
            trades: data.trades || [],
          });
        } else if (data.type === "ticker" && data.ticker?.last_price) {
          // Real-time ticker push from Binance miniTicker stream
          set({ ticker: data.ticker });
        } else if (data.type === "orderbook" && data.orderbook) {
          // Real-time orderbook push from Binance depth20 stream (~100ms)
          set({ orderbook: data.orderbook });
        } else if (data.type === "trade" && data.trade) {
          // Real-time individual trade push
          set((state) => ({
            trades: [data.trade, ...state.trades].slice(0, 50),
          }));
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
