"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  UTCTimestamp,
} from "lightweight-charts";
import { apiFetch } from "@/lib/api";
import styles from "./ChartWidget.module.css";
import {
  KlinePoint,
  calcMA, calcEMA, calcBOLL, calcSAR,
  calcVOL, calcMACD, calcRSI, calcKDJ, calcWR, calcDMI, calcCCI, calcOBV,
} from "@/lib/indicators";

const INTERVALS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"] as const;
const INTERVAL_LABELS: Record<string, string> = {
  "1m": "1분", "5m": "5분", "15m": "15분", "30m": "30분",
  "1h": "1시간", "4h": "4시간", "1d": "1일", "1w": "1주",
};
const INDICATORS = ["MA", "EMA", "BOLL", "SAR", "VOL", "MACD", "RSI", "KDJ", "WR", "DMI", "CCI", "OBV"] as const;

// Cast numeric unix timestamps to UTCTimestamp for lightweight-charts
function toTS<T extends { time: number }>(arr: T[]): (Omit<T, "time"> & { time: UTCTimestamp })[] {
  return arr as unknown as (Omit<T, "time"> & { time: UTCTimestamp })[];
}

export default function ChartWidget({ pair }: { pair: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const klineDataRef = useRef<KlinePoint[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const overlaySeriesRef = useRef<Map<string, ISeriesApi<any>[]>>(new Map());
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const subPaneSeriesRef = useRef<Map<string, ISeriesApi<any>[]>>(new Map());
  const subPaneRef = useRef<Map<string, { paneIndex(): number }>>(new Map());

  const [interval, setIntervalState] = useState("1h");
  const [activeIndicators, setActiveIndicators] = useState<Set<string>>(new Set());

  const toggleIndicator = (name: string) => {
    setActiveIndicators((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  const removeIndicator = useCallback((key: string) => {
    const chart = chartRef.current;
    if (!chart) return;
    const overlaySeries = overlaySeriesRef.current.get(key);
    if (overlaySeries) {
      overlaySeries.forEach((s) => { try { chart.removeSeries(s); } catch { /* ignore */ } });
      overlaySeriesRef.current.delete(key);
    }
    const subSeries = subPaneSeriesRef.current.get(key);
    if (subSeries) {
      subSeries.forEach((s) => { try { chart.removeSeries(s); } catch { /* ignore */ } });
      subPaneSeriesRef.current.delete(key);
    }
    const pane = subPaneRef.current.get(key);
    if (pane !== undefined) {
      try { chart.removePane(pane.paneIndex()); } catch { /* ignore */ }
      subPaneRef.current.delete(key);
    }
  }, []);

  const syncIndicators = useCallback((active: Set<string>) => {
    const chart = chartRef.current;
    const data = klineDataRef.current;
    if (!chart || data.length === 0) return;

    // Remove stale indicators
    const allKeys = new Set([
      ...overlaySeriesRef.current.keys(),
      ...subPaneSeriesRef.current.keys(),
    ]);
    for (const key of allKeys) {
      if (!active.has(key)) removeIndicator(key);
    }

    for (const key of active) {
      if (overlaySeriesRef.current.has(key) || subPaneSeriesRef.current.has(key)) continue;

      if (key === "MA") {
        const periods = [7, 25, 99];
        const colors = ["#f6a600", "#f0c419", "#cd84f1"];
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const series: ISeriesApi<any>[] = [];
        periods.forEach((p, idx) => {
          const s = chart.addSeries(LineSeries, {
            color: colors[idx], lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
          }, 0);
          s.setData(toTS(calcMA(data, p)));
          series.push(s);
        });
        overlaySeriesRef.current.set("MA", series);

      } else if (key === "EMA") {
        const periods = [12, 26];
        const colors = ["#1e90ff", "#ff69b4"];
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const series: ISeriesApi<any>[] = [];
        periods.forEach((p, idx) => {
          const s = chart.addSeries(LineSeries, {
            color: colors[idx], lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
          }, 0);
          s.setData(toTS(calcEMA(data, p)));
          series.push(s);
        });
        overlaySeriesRef.current.set("EMA", series);

      } else if (key === "BOLL") {
        const boll = calcBOLL(data);
        const upper = chart.addSeries(LineSeries, { color: "#f6a600", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, 0);
        const middle = chart.addSeries(LineSeries, { color: "#1e90ff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, 0);
        const lower = chart.addSeries(LineSeries, { color: "#f6a600", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, 0);
        upper.setData(toTS(boll.map((d) => ({ time: d.time, value: d.upper }))));
        middle.setData(toTS(boll.map((d) => ({ time: d.time, value: d.middle }))));
        lower.setData(toTS(boll.map((d) => ({ time: d.time, value: d.lower }))));
        overlaySeriesRef.current.set("BOLL", [upper, middle, lower]);

      } else if (key === "SAR") {
        const sar = calcSAR(data);
        const s = chart.addSeries(LineSeries, {
          color: "#ff6b6b", lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
        }, 0);
        s.setData(toTS(sar));
        overlaySeriesRef.current.set("SAR", [s]);

      } else if (key === "VOL") {
        const pane = chart.addPane();
        const s = chart.addSeries(HistogramSeries, {
          priceFormat: { type: "volume" }, priceScaleId: "vol",
          priceLineVisible: false, lastValueVisible: false,
        }, pane.paneIndex());
        s.setData(toTS(calcVOL(data)));
        subPaneSeriesRef.current.set("VOL", [s]);
        subPaneRef.current.set("VOL", pane);

      } else if (key === "MACD") {
        const { macd, signal, hist } = calcMACD(data);
        const pane = chart.addPane();
        const histS = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, pane.paneIndex());
        const macdS = chart.addSeries(LineSeries, { color: "#1e90ff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane.paneIndex());
        const signalS = chart.addSeries(LineSeries, { color: "#ff69b4", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane.paneIndex());
        histS.setData(toTS(hist));
        macdS.setData(toTS(macd));
        signalS.setData(toTS(signal));
        subPaneSeriesRef.current.set("MACD", [histS, macdS, signalS]);
        subPaneRef.current.set("MACD", pane);

      } else if (key === "RSI") {
        const pane = chart.addPane();
        const s = chart.addSeries(LineSeries, { color: "#9b59b6", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane.paneIndex());
        s.setData(toTS(calcRSI(data)));
        subPaneSeriesRef.current.set("RSI", [s]);
        subPaneRef.current.set("RSI", pane);

      } else if (key === "KDJ") {
        const { k, d, j } = calcKDJ(data);
        const pane = chart.addPane();
        const kS = chart.addSeries(LineSeries, { color: "#f6a600", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane.paneIndex());
        const dS = chart.addSeries(LineSeries, { color: "#1e90ff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane.paneIndex());
        const jS = chart.addSeries(LineSeries, { color: "#00bfff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane.paneIndex());
        kS.setData(toTS(k));
        dS.setData(toTS(d));
        jS.setData(toTS(j));
        subPaneSeriesRef.current.set("KDJ", [kS, dS, jS]);
        subPaneRef.current.set("KDJ", pane);

      } else if (key === "WR") {
        const pane = chart.addPane();
        const s = chart.addSeries(LineSeries, { color: "#9b59b6", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane.paneIndex());
        s.setData(toTS(calcWR(data)));
        subPaneSeriesRef.current.set("WR", [s]);
        subPaneRef.current.set("WR", pane);

      } else if (key === "DMI") {
        const { plusDI, minusDI, adx } = calcDMI(data);
        const pane = chart.addPane();
        const pS = chart.addSeries(LineSeries, { color: "#00ff7f", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane.paneIndex());
        const mS = chart.addSeries(LineSeries, { color: "#ff4444", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane.paneIndex());
        const aS = chart.addSeries(LineSeries, { color: "#f6a600", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane.paneIndex());
        pS.setData(toTS(plusDI));
        mS.setData(toTS(minusDI));
        aS.setData(toTS(adx));
        subPaneSeriesRef.current.set("DMI", [pS, mS, aS]);
        subPaneRef.current.set("DMI", pane);

      } else if (key === "CCI") {
        const pane = chart.addPane();
        const s = chart.addSeries(LineSeries, { color: "#9b59b6", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane.paneIndex());
        s.setData(toTS(calcCCI(data)));
        subPaneSeriesRef.current.set("CCI", [s]);
        subPaneRef.current.set("CCI", pane);

      } else if (key === "OBV") {
        const pane = chart.addPane();
        const s = chart.addSeries(LineSeries, { color: "#1e90ff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane.paneIndex());
        s.setData(toTS(calcOBV(data)));
        subPaneSeriesRef.current.set("OBV", [s]);
        subPaneRef.current.set("OBV", pane);
      }
    }
  }, [removeIndicator]);

  const loadData = useCallback(async (iv: string) => {
    if (!candleSeriesRef.current) return;
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const raw = await apiFetch(`/api/market/${pair}/klines?interval=${iv}&limit=500`);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const klines: KlinePoint[] = raw.map((k: any) => ({
        time: k.time as number,
        open: parseFloat(k.open),
        high: parseFloat(k.high),
        low: parseFloat(k.low),
        close: parseFloat(k.close),
        volume: parseFloat(k.volume),
      }));
      candleSeriesRef.current.setData(toTS(klines));
      klineDataRef.current = klines;
      // Clear and re-render all active indicators with fresh data
      for (const key of [
        ...overlaySeriesRef.current.keys(),
        ...subPaneSeriesRef.current.keys(),
      ]) {
        removeIndicator(key);
      }
      setActiveIndicators((prev) => new Set(prev));
    } catch (e) {
      console.error("Failed to load klines", e);
    }
  }, [pair, removeIndicator]);

  // Create chart once on mount
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: { background: { color: "#0b0e11" }, textColor: "#848e9c" },
      grid: { vertLines: { color: "#2b3139" }, horzLines: { color: "#2b3139" } },
      rightPriceScale: { borderColor: "#2b3139" },
      timeScale: { borderColor: "#2b3139", timeVisible: true, secondsVisible: false },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#0ecb81", downColor: "#f6465d",
      borderUpColor: "#0ecb81", borderDownColor: "#f6465d",
      wickUpColor: "#0ecb81", wickDownColor: "#f6465d",
    });
    chartRef.current = chart;
    candleSeriesRef.current = series;
    return () => {
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
    };
  }, []);

  // Reload klines when pair or interval changes
  useEffect(() => {
    loadData(interval);
  }, [pair, interval, loadData]);

  // Sync indicators when active set changes
  useEffect(() => {
    syncIndicators(activeIndicators);
  }, [activeIndicators, syncIndicators]);

  return (
    <div className="flex flex-col h-full">
      <div className={`flex items-center gap-1 px-3 py-1.5 border-b flex-shrink-0 ${styles.toolbar}`}>
        {INTERVALS.map((iv) => (
          <button key={iv} type="button" onClick={() => setIntervalState(iv)}
            className={`px-2 py-0.5 rounded text-xs transition-colors cursor-pointer ${styles.intervalBtn}`}
            data-active={interval === iv ? "true" : "false"}>
            {INTERVAL_LABELS[iv]}
          </button>
        ))}
        <span className={styles.separator} />
        {INDICATORS.map((name) => (
          <button key={name} type="button" onClick={() => toggleIndicator(name)}
            className={`px-2 py-0.5 rounded text-xs transition-colors cursor-pointer ${styles.indicatorBtn}`}
            data-active={activeIndicators.has(name) ? "true" : "false"}>
            {name}
          </button>
        ))}
        <div className="ml-auto flex items-center">
          <button type="button" className={`px-2 py-0.5 text-xs cursor-pointer ${styles.iconBtn}`}>👁</button>
          <button type="button" className={`px-2 py-0.5 text-xs cursor-pointer ${styles.iconBtn}`}>▾</button>
        </div>
      </div>
      <div ref={containerRef} className="flex-1" />
    </div>
  );
}
