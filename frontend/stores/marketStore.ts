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
let reconnectTimer: NodeJS.Timeout | null = null;
let currentPair: string | null = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_DELAY = 30000; // max 30 seconds

export const useMarketStore = create<MarketStore>((set) => ({
  ticker: null,
  orderbook: { bids: [], asks: [] },
  trades: [],
  latestKline: null,
  connected: false,

  connect: (pair: string) => {
    // Clear any pending reconnection
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }

    // Close existing connection
    if (ws) {
      ws.close();
      ws = null;
    }

    currentPair = pair;
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const fullUrl = `${wsUrl}/ws/market/${pair}`;
    console.log("[MarketStore] Connecting to WebSocket:", fullUrl, `(attempt ${reconnectAttempts + 1})`);

    const newWs = new WebSocket(fullUrl);
    ws = newWs;

    // Guard all handlers so stale WS events don't corrupt state after reconnect
    newWs.onopen = () => {
      console.log("[MarketStore] ✅ WebSocket connected for pair:", pair);
      reconnectAttempts = 0; // reset on successful connection
      if (ws === newWs) set({ connected: true });
    };

    newWs.onclose = (event) => {
      console.log("[MarketStore] ❌ WebSocket closed:", event.code, event.reason);
      if (ws === newWs) {
        set({ connected: false });
        // Auto-reconnect with exponential backoff
        scheduleReconnect();
      }
    };

    newWs.onerror = (error) => {
      console.error("[MarketStore] ⚠️ WebSocket error:", error);
      if (ws === newWs) {
        set({ connected: false });
      }
    };

    // Helper function for exponential backoff reconnection
    function scheduleReconnect() {
      if (!currentPair) return; // don't reconnect if disconnect() was called

      reconnectAttempts++;
      // Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), MAX_RECONNECT_DELAY);
      console.log(`[MarketStore] Reconnecting in ${delay}ms... (attempt ${reconnectAttempts})`);

      reconnectTimer = setTimeout(() => {
        if (currentPair) {
          console.log(`[MarketStore] Attempting reconnect for ${currentPair}...`);
          const store = useMarketStore.getState();
          store.connect(currentPair);
        }
      }, delay);
    }
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
            orderbook: {
              bids: data.orderbook?.bids ? [...data.orderbook.bids] : [],
              asks: data.orderbook?.asks ? [...data.orderbook.asks] : [],
            },
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
            // Create new object and arrays to trigger React re-render
            set({
              orderbook: {
                bids: [...data.orderbook.bids],
                asks: [...data.orderbook.asks],
              }
            });
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
    console.log("[MarketStore] Manually disconnecting WebSocket");
    currentPair = null; // signal that we don't want to auto-reconnect
    reconnectAttempts = 0;

    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }

    if (ws) {
      ws.close();
      ws = null;
    }

    set({ connected: false, latestKline: null });
  },
}));
