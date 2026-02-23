"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { usePairListStore } from "@/stores/pairListStore";

function formatPrice(price: string): string {
  const num = parseFloat(price);
  if (isNaN(num)) return price;
  return num.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatChange(change: string): { text: string; positive: boolean } {
  const num = parseFloat(change);
  if (isNaN(num)) return { text: change + "%", positive: true };
  const positive = num >= 0;
  const text = (positive ? "+" : "") + num.toFixed(2) + "%";
  return { text, positive };
}

export default function PairList({ currentPair }: { currentPair: string }) {
  const router = useRouter();
  const { getFilteredPairs, searchQuery, setSearchQuery, fetchPairs, loading, allPairs } =
    usePairListStore();

  useEffect(() => {
    fetchPairs();
  }, [fetchPairs]);

  const pairs = getFilteredPairs();

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Search input */}
      <div
        className="px-3 py-2 sticky top-0 z-10 border-b"
        style={{
          background: "var(--bg-secondary)",
          borderColor: "var(--border)",
        }}
      >
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search"
          className="w-full rounded px-2 py-1 text-xs outline-none"
          style={{
            background: "var(--bg-primary)",
            color: "var(--text-primary)",
            border: "1px solid var(--border)",
          }}
        />
      </div>

      {/* Column headers */}
      <div
        className="grid grid-cols-3 px-3 py-1.5 text-xs sticky top-[41px] z-10 border-b"
        style={{
          background: "var(--bg-secondary)",
          color: "var(--text-secondary)",
          borderColor: "var(--border)",
        }}
      >
        <span>Pair</span>
        <span className="text-right">Price</span>
        <span className="text-right">Change</span>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {loading && allPairs.length === 0 ? (
          <div
            className="flex items-center justify-center h-full text-xs"
            style={{ color: "var(--text-secondary)" }}
          >
            Loading...
          </div>
        ) : (
          pairs.map((ticker) => {
            const isActive = ticker.symbol === currentPair;
            const [base] = ticker.displaySymbol.split("/");
            const { text: changeText, positive } = formatChange(ticker.priceChangePercent);

            return (
              <div
                key={ticker.symbol}
                onClick={() => router.push(`/exchange/${ticker.symbol}`)}
                className="grid grid-cols-3 px-3 py-1.5 text-xs cursor-pointer transition-colors"
                style={{
                  background: isActive ? "var(--bg-panel)" : "transparent",
                  color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    (e.currentTarget as HTMLDivElement).style.background = "var(--bg-panel)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    (e.currentTarget as HTMLDivElement).style.background = "transparent";
                  }
                }}
              >
                {/* Pair column */}
                <span>
                  <span
                    className="font-bold"
                    style={{ color: isActive ? "var(--text-primary)" : "var(--text-primary)" }}
                  >
                    {base}
                  </span>
                  <span style={{ color: "var(--text-secondary)" }}>/USDT</span>
                </span>

                {/* Price column */}
                <span className="text-right" style={{ color: "var(--text-primary)" }}>
                  {formatPrice(ticker.lastPrice)}
                </span>

                {/* Change column */}
                <span
                  className="text-right"
                  style={{ color: positive ? "var(--green)" : "var(--red)" }}
                >
                  {changeText}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
