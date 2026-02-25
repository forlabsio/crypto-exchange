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
let lastOrderbookMs = 0; // throttle orderbook renders to prevent excessive re-renders

export const useMarketStore = create<MarketStore>((set) => ({
  ticker: null,
  orderbook: { bids: [], asks: [] },
  trades: [],
  latestKline: null,
  connected: false,

  connect: (pair: string) => {
    if (ws) ws.close();
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const fullUrl = `${wsUrl}/ws/market/${pair}`;
    console.log("[MarketStore] Connecting to WebSocket:", fullUrl);
    const newWs = new WebSocket(fullUrl);
    ws = newWs;

    // Guard all handlers so stale WS events don't corrupt state after reconnect
    newWs.onopen = () => {
      console.log("[MarketStore] WebSocket connected for pair:", pair);
      if (ws === newWs) set({ connected: true });
    };
    newWs.onclose = (event) => {
      console.log("[MarketStore] WebSocket closed:", event.code, event.reason);
      if (ws === newWs) set({ connected: false });
    };
    newWs.onerror = (error) => {
      console.error("[MarketStore] WebSocket error:", error);
      if (ws === newWs) set({ connected: false });
    };
    newWs.onmessage = (e) => {
      if (ws !== newWs) return; // ignore messages from replaced connections
      try {
        const data = JSON.parse(e.data);
        console.log("[MarketStore] Received message type:", data.type);

        if (data.type === "snapshot") {
          console.log("[MarketStore] Snapshot received - orderbook bids:", data.orderbook?.bids?.length, "asks:", data.orderbook?.asks?.length);
          lastOrderbookMs = Date.now();
          set({
            ticker: data.ticker && data.ticker.last_price ? data.ticker : null,
            orderbook: data.orderbook || { bids: [], asks: [] },
            trades: data.trades || [],
          });
        } else if (data.type === "ticker" && data.ticker?.last_price) {
          set({ ticker: data.ticker });
        } else if (data.type === "orderbook" && data.orderbook) {
          // Throttle orderbook updates to max ~20/sec (50ms) for smooth real-time updates
          const now = Date.now();
          if (now - lastOrderbookMs >= 50) {
            lastOrderbookMs = now;
            console.log("[MarketStore] Orderbook update - bids:", data.orderbook.bids?.length, "asks:", data.orderbook.asks?.length);
            set({ orderbook: data.orderbook });
          } else {
            console.log("[MarketStore] Orderbook update throttled");
          }
        } else if (data.type === "trade" && data.trade) {
          set((state) => ({
            trades: [data.trade, ...state.trades].slice(0, 50),
          }));
        } else if (data.type === "kline" && data.kline) {
          set({ latestKline: { interval: data.interval, kline: data.kline } });
        }
      } catch (err) {
        console.error("[MarketStore] Failed to parse message:", err);
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
