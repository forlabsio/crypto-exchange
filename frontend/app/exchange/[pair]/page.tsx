"use client";
import { useEffect } from "react";
import { use } from "react";
import { useMarketStore } from "@/stores/marketStore";
import PairList from "@/components/exchange/PairList";
import Orderbook from "@/components/exchange/Orderbook";
import OpenOrders from "@/components/exchange/OpenOrders";
import dynamic from "next/dynamic";
import OrderForm from "@/components/exchange/OrderForm";

const ChartWidget = dynamic(() => import("@/components/exchange/ChartWidget"), { ssr: false });

function formatTurnover(value: number): string {
  if (value >= 1_000_000_000) {
    return (value / 1_000_000_000).toFixed(2) + "B";
  } else if (value >= 1_000_000) {
    return (value / 1_000_000).toFixed(2) + "M";
  }
  return value.toLocaleString();
}

export default function ExchangePage({ params }: { params: Promise<{ pair: string }> }) {
  const { pair } = use(params);
  const { connect, disconnect, ticker } = useMarketStore();

  useEffect(() => {
    connect(pair);
    return () => disconnect();
  }, [pair]);

  const isPositive = ticker ? parseFloat(ticker.change_pct) >= 0 : true;
  const priceColor = isPositive ? "var(--green)" : "var(--red)";

  return (
    <div className="flex" style={{ height: "calc(100vh - 56px)", background: "var(--bg-primary)" }}>

      {/* Col 1: PairList - fixed 200px */}
      <div style={{ width: 200, flexShrink: 0, borderRight: "1px solid var(--border)" }}>
        <PairList currentPair={pair} />
      </div>

      {/* Col 2+3: Main area (chart + orderbook + openorders) - flex-1 */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Ticker header - full width spanning chart+orderbook */}
        <div
          className="flex items-center gap-6 px-4 py-2 flex-shrink-0"
          style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-secondary)" }}
        >
          <span className="font-bold text-base" style={{ color: "var(--text-primary)" }}>
            {pair.replace("_", "/")}
          </span>

          {ticker ? (
            <>
              <span className="text-xl font-bold font-mono" style={{ color: priceColor }}>
                {parseFloat(ticker.last_price).toLocaleString()}
              </span>
              <span className="text-xs" style={{ color: priceColor }}>
                {isPositive ? "+" : ""}{ticker.change_pct}%
              </span>

              <span className="text-xs flex gap-1">
                <span style={{ color: "var(--text-secondary)" }}>High</span>
                <span style={{ color: "var(--text-primary)" }}>{parseFloat(ticker.high).toLocaleString()}</span>
              </span>

              <span className="text-xs flex gap-1">
                <span style={{ color: "var(--text-secondary)" }}>Low</span>
                <span style={{ color: "var(--text-primary)" }}>{parseFloat(ticker.low).toLocaleString()}</span>
              </span>

              <span className="text-xs flex gap-1">
                <span style={{ color: "var(--text-secondary)" }}>Volume(BTC)</span>
                <span style={{ color: "var(--text-primary)" }}>{parseFloat(ticker.volume).toLocaleString()}</span>
              </span>

              <span className="text-xs flex gap-1">
                <span style={{ color: "var(--text-secondary)" }}>Turnover(USDT)</span>
                <span style={{ color: "var(--text-primary)" }}>{formatTurnover(parseFloat(ticker.quote_volume))}</span>
              </span>
            </>
          ) : (
            <span className="text-xs" style={{ color: "var(--text-secondary)" }}>Connecting...</span>
          )}
        </div>

        {/* Middle row: chart (flex-1) + orderbook (280px) */}
        <div className="flex flex-1 min-h-0">

          {/* Chart area */}
          <div className="flex-1 min-w-0">
            <ChartWidget pair={pair} />
          </div>

          {/* Orderbook */}
          <div style={{ width: 280, flexShrink: 0, borderLeft: "1px solid var(--border)" }}>
            <Orderbook />
          </div>
        </div>

        {/* Bottom: OpenOrders */}
        <div style={{ height: 180, flexShrink: 0, borderTop: "1px solid var(--border)" }}>
          <OpenOrders />
        </div>
      </div>

      {/* Col 4: OrderForm - fixed 280px */}
      <div style={{ width: 280, flexShrink: 0, borderLeft: "1px solid var(--border)", overflowY: "auto" }}>
        <OrderForm pair={pair} />
      </div>
    </div>
  );
}
