"use client";
import { useEffect, useLayoutEffect, useRef } from "react";
import Link from "next/link";
import { usePairListStore, PAIR_GROUPS } from "@/stores/pairListStore";

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
  const { getFilteredPairs, searchQuery, setSearchQuery, fetchPairs, loading, allPairs, error, scrollTop, setScrollTop } =
    usePairListStore();
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => { fetchPairs(); }, [fetchPairs]);

  useLayoutEffect(() => {
    if (listRef.current && scrollTop > 0) {
      listRef.current.scrollTop = scrollTop;
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const pairs = getFilteredPairs();
  const isSearching = searchQuery.trim().length > 0;

  const grouped = isSearching
    ? [{ groupLabel: null, items: pairs }]
    : PAIR_GROUPS.map(({ group }) => ({
        groupLabel: group,
        items: pairs.filter((p) => p.group === group),
      })).filter(({ items }) => items.length > 0);

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Search */}
      <div className="px-3 py-2 flex-shrink-0 border-b"
        style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search"
          className="w-full rounded px-2 py-1 text-xs outline-none"
          style={{ background: "var(--bg-primary)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
        />
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-3 px-3 py-1.5 text-xs flex-shrink-0 border-b"
        style={{ background: "var(--bg-secondary)", color: "var(--text-secondary)", borderColor: "var(--border)" }}>
        <span>Pair</span>
        <span className="text-right">Price</span>
        <span className="text-right">Change</span>
      </div>

      {/* List */}
      <div ref={listRef} className="flex-1 overflow-y-auto"
        onScroll={(e) => setScrollTop((e.currentTarget as HTMLDivElement).scrollTop)}>
        {loading && allPairs.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-xs" style={{ color: "var(--text-secondary)" }}>
            Loading...
          </div>
        ) : error && allPairs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-xs gap-2" style={{ color: "var(--text-secondary)" }}>
            <span>Failed to load</span>
            <button type="button" onClick={() => fetchPairs()}
              className="px-2 py-1 rounded text-xs bg-[var(--bg-panel)] text-[var(--blue)] border border-[var(--border)]">
              Retry
            </button>
          </div>
        ) : (
          grouped.map(({ groupLabel, items }) => (
            <div key={groupLabel ?? "_search"}>
              {groupLabel && (
                <div className="px-3 pt-2.5 pb-1 text-xs font-semibold"
                  style={{ color: "var(--text-secondary)", background: "var(--bg-secondary)", borderBottom: "1px solid var(--border)", letterSpacing: "0.03em" }}>
                  {groupLabel}
                </div>
              )}
              {items.map((item) => {
                const isActive = item.symbol === currentPair;
                const [base] = item.displaySymbol.split("/");
                const { text: changeText, positive } = formatChange(item.priceChangePercent);
                return (
                  <Link key={item.symbol} href={`/exchange/${item.symbol}`} scroll={false}
                    className="grid grid-cols-3 px-3 py-1.5 text-xs no-underline transition-colors"
                    style={{ display: "grid", background: isActive ? "var(--bg-panel)" : "transparent", textDecoration: "none" }}
                    onMouseEnter={(e) => { if (!isActive) (e.currentTarget as HTMLAnchorElement).style.background = "var(--bg-panel)"; }}
                    onMouseLeave={(e) => { if (!isActive) (e.currentTarget as HTMLAnchorElement).style.background = "transparent"; }}>
                    <span>
                      <span className="font-bold" style={{ color: "var(--text-primary)" }}>{base}</span>
                      <span style={{ color: "var(--text-secondary)" }}>/USDT</span>
                    </span>
                    <span className="text-right" style={{ color: "var(--text-primary)" }}>{formatPrice(item.lastPrice)}</span>
                    <span className="text-right" style={{ color: positive ? "var(--green)" : "var(--red)" }}>{changeText}</span>
                  </Link>
                );
              })}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
