import { create } from "zustand";

export interface BinanceTicker {
  symbol: string;        // e.g. "BTC_USDT"
  displaySymbol: string; // e.g. "BTC/USDT"
  lastPrice: string;
  priceChangePercent: string;
  highPrice: string;
  lowPrice: string;
  volume: string;
  quoteVolume: string;
  group: string;
}

// Fixed curated list — order within each group is preserved
export const PAIR_GROUPS: Array<{ group: string; pairs: string[] }> = [
  { group: "Market Anchor",         pairs: ["BTC", "ETH"] },
  { group: "High Liquidity Majors", pairs: ["SOL", "XRP", "BNB", "AVAX", "ADA", "DOGE", "DOT", "LINK"] },
  { group: "L2 / Scaling",          pairs: ["ARB", "OP", "MATIC"] },
  { group: "AI / Infra",            pairs: ["RNDR", "FET", "GRT"] },
  { group: "DeFi / Ecosystem",      pairs: ["UNI", "AAVE"] },
  { group: "High Beta / Rotation",  pairs: ["SUI", "APT"] },
];

// Flat ordered list: [{base, group}, ...]
const ALLOWED: Array<{ base: string; group: string }> = PAIR_GROUPS.flatMap(({ group, pairs }) =>
  pairs.map((base) => ({ base, group }))
);

const BINANCE_SYMBOLS = ALLOWED.map(({ base }) => `${base}USDT`);

interface PairListStore {
  allPairs: BinanceTicker[];
  searchQuery: string;
  loading: boolean;
  error: string | null;
  scrollTop: number;
  fetchPairs: () => Promise<void>;
  setSearchQuery: (q: string) => void;
  setScrollTop: (top: number) => void;
  getFilteredPairs: () => BinanceTicker[];
}

export const usePairListStore = create<PairListStore>((set, get) => ({
  allPairs: [],
  searchQuery: "",
  loading: false,
  error: null,
  scrollTop: 0,

  fetchPairs: async () => {
    set({ loading: true, error: null });
    try {
      const symbolsParam = encodeURIComponent(JSON.stringify(BINANCE_SYMBOLS));
      const res = await fetch(
        `https://api.binance.com/api/v3/ticker/24hr?symbols=${symbolsParam}`
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: Array<{
        symbol: string;
        lastPrice: string;
        priceChangePercent: string;
        highPrice: string;
        lowPrice: string;
        volume: string;
        quoteVolume: string;
      }> = await res.json();

      // Build lookup by base symbol
      const lookup = new Map(
        data.map((item) => [item.symbol.slice(0, -4), item])
      );

      // Rebuild in defined order, preserving group info
      const ordered: BinanceTicker[] = [];
      for (const { base, group } of ALLOWED) {
        const item = lookup.get(base);
        if (!item) continue;
        ordered.push({
          symbol: `${base}_USDT`,
          displaySymbol: `${base}/USDT`,
          lastPrice: item.lastPrice,
          priceChangePercent: item.priceChangePercent,
          highPrice: item.highPrice,
          lowPrice: item.lowPrice,
          volume: item.volume,
          quoteVolume: item.quoteVolume,
          group,
        });
      }

      set({ allPairs: ordered });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : String(err) });
    } finally {
      set({ loading: false });
    }
  },

  setSearchQuery: (q: string) => set({ searchQuery: q }),
  setScrollTop: (top: number) => set({ scrollTop: top }),

  getFilteredPairs: () => {
    const { allPairs, searchQuery } = get();
    if (!searchQuery) return allPairs;
    const query = searchQuery.toLowerCase();
    return allPairs.filter(
      (pair) =>
        pair.displaySymbol.toLowerCase().includes(query) ||
        pair.symbol.toLowerCase().includes(query)
    );
  },
}));
