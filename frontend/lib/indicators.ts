// lib/indicators.ts

export interface KlinePoint {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ── Overlay indicators (main pane) ──────────────────────────────

/** Simple Moving Average */
export function calcMA(
  data: KlinePoint[],
  period: number
): { time: number; value: number }[] {
  const result: { time: number; value: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) sum += data[i - j].close;
    result.push({ time: data[i].time, value: sum / period });
  }
  return result;
}

/** Exponential Moving Average */
export function calcEMA(
  data: KlinePoint[],
  period: number
): { time: number; value: number }[] {
  if (data.length < period) return [];
  const k = 2 / (period + 1);
  const result: { time: number; value: number }[] = [];
  let ema = data.slice(0, period).reduce((s, d) => s + d.close, 0) / period;
  result.push({ time: data[period - 1].time, value: ema });
  for (let i = period; i < data.length; i++) {
    ema = data[i].close * k + ema * (1 - k);
    result.push({ time: data[i].time, value: ema });
  }
  return result;
}

/** Bollinger Bands */
export function calcBOLL(
  data: KlinePoint[],
  period = 20,
  mult = 2
): { time: number; upper: number; middle: number; lower: number }[] {
  const result: { time: number; upper: number; middle: number; lower: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1).map((d) => d.close);
    const mean = slice.reduce((s, v) => s + v, 0) / period;
    const variance = slice.reduce((s, v) => s + (v - mean) ** 2, 0) / period;
    const std = Math.sqrt(variance);
    result.push({
      time: data[i].time,
      upper: mean + mult * std,
      middle: mean,
      lower: mean - mult * std,
    });
  }
  return result;
}

/** Parabolic SAR */
export function calcSAR(
  data: KlinePoint[],
  step = 0.02,
  maxAF = 0.2
): { time: number; value: number }[] {
  if (data.length < 2) return [];
  const result: { time: number; value: number }[] = [];
  let bull = true;
  let af = step;
  let ep = data[0].high;
  let sar = data[0].low;

  for (let i = 1; i < data.length; i++) {
    const prevSar = sar;
    if (bull) {
      sar = prevSar + af * (ep - prevSar);
      sar = Math.min(sar, data[i - 1].low, i >= 2 ? data[i - 2].low : data[i - 1].low);
      if (data[i].low < sar) {
        bull = false;
        sar = ep;
        ep = data[i].low;
        af = step;
      } else {
        if (data[i].high > ep) {
          ep = data[i].high;
          af = Math.min(af + step, maxAF);
        }
      }
    } else {
      sar = prevSar + af * (ep - prevSar);
      sar = Math.max(sar, data[i - 1].high, i >= 2 ? data[i - 2].high : data[i - 1].high);
      if (data[i].high > sar) {
        bull = true;
        sar = ep;
        ep = data[i].high;
        af = step;
      } else {
        if (data[i].low < ep) {
          ep = data[i].low;
          af = Math.min(af + step, maxAF);
        }
      }
    }
    result.push({ time: data[i].time, value: sar });
  }
  return result;
}

// ── Sub-pane indicators ─────────────────────────────────────────

/** Volume with up/down color */
export function calcVOL(
  data: KlinePoint[]
): { time: number; value: number; color: string }[] {
  return data.map((d) => ({
    time: d.time,
    value: d.volume,
    color: d.close >= d.open ? "#0ecb81" : "#f6465d",
  }));
}

/** MACD (12/26/9) */
export function calcMACD(data: KlinePoint[]): {
  macd: { time: number; value: number }[];
  signal: { time: number; value: number }[];
  hist: { time: number; value: number; color: string }[];
} {
  const ema12 = calcEMA(data, 12);
  const ema26 = calcEMA(data, 26);
  const macdRaw: { time: number; value: number }[] = [];
  const timeToEma12 = new Map(ema12.map((d) => [d.time, d.value]));
  for (const e26 of ema26) {
    const e12 = timeToEma12.get(e26.time);
    if (e12 !== undefined) {
      macdRaw.push({ time: e26.time, value: e12 - e26.value });
    }
  }

  const signalRaw: { time: number; value: number }[] = [];
  if (macdRaw.length >= 9) {
    const k = 2 / 10;
    let sigEma = macdRaw.slice(0, 9).reduce((s, d) => s + d.value, 0) / 9;
    signalRaw.push({ time: macdRaw[8].time, value: sigEma });
    for (let i = 9; i < macdRaw.length; i++) {
      sigEma = macdRaw[i].value * k + sigEma * (1 - k);
      signalRaw.push({ time: macdRaw[i].time, value: sigEma });
    }
  }

  const timeToSig = new Map(signalRaw.map((d) => [d.time, d.value]));
  const hist: { time: number; value: number; color: string }[] = [];
  for (const m of macdRaw) {
    const sig = timeToSig.get(m.time);
    if (sig !== undefined) {
      const val = m.value - sig;
      hist.push({ time: m.time, value: val, color: val >= 0 ? "#0ecb81" : "#f6465d" });
    }
  }

  return { macd: macdRaw, signal: signalRaw, hist };
}

/** RSI */
export function calcRSI(
  data: KlinePoint[],
  period = 14
): { time: number; value: number }[] {
  if (data.length <= period) return [];
  const result: { time: number; value: number }[] = [];
  let gains = 0,
    losses = 0;
  for (let i = 1; i <= period; i++) {
    const diff = data[i].close - data[i - 1].close;
    if (diff > 0) gains += diff;
    else losses -= diff;
  }
  let avgGain = gains / period;
  let avgLoss = losses / period;
  const rsi = (v: number) =>
    v === 0 ? 100 : v === Infinity ? 0 : 100 - 100 / (1 + v);
  result.push({
    time: data[period].time,
    value: rsi(avgGain / (avgLoss || 1e-10)),
  });
  for (let i = period + 1; i < data.length; i++) {
    const diff = data[i].close - data[i - 1].close;
    avgGain = (avgGain * (period - 1) + Math.max(diff, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-diff, 0)) / period;
    result.push({
      time: data[i].time,
      value: rsi(avgGain / (avgLoss || 1e-10)),
    });
  }
  return result;
}

/** KDJ (Stochastic, K=9, D=3) */
export function calcKDJ(
  data: KlinePoint[],
  kPeriod = 9,
  dSmooth = 3
): {
  k: { time: number; value: number }[];
  d: { time: number; value: number }[];
  j: { time: number; value: number }[];
} {
  void dSmooth; // reserved for future use
  const kArr: { time: number; value: number }[] = [];
  const dArr: { time: number; value: number }[] = [];
  const jArr: { time: number; value: number }[] = [];
  let kPrev = 50,
    dPrev = 50;
  for (let i = kPeriod - 1; i < data.length; i++) {
    const slice = data.slice(i - kPeriod + 1, i + 1);
    const highest = Math.max(...slice.map((d) => d.high));
    const lowest = Math.min(...slice.map((d) => d.low));
    const rsv =
      highest === lowest
        ? 50
        : ((data[i].close - lowest) / (highest - lowest)) * 100;
    const k = (2 / 3) * kPrev + (1 / 3) * rsv;
    const d = (2 / 3) * dPrev + (1 / 3) * k;
    const j = 3 * k - 2 * d;
    kArr.push({ time: data[i].time, value: k });
    dArr.push({ time: data[i].time, value: d });
    jArr.push({ time: data[i].time, value: j });
    kPrev = k;
    dPrev = d;
  }
  return { k: kArr, d: dArr, j: jArr };
}

/** Williams %R */
export function calcWR(
  data: KlinePoint[],
  period = 14
): { time: number; value: number }[] {
  const result: { time: number; value: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1);
    const highest = Math.max(...slice.map((d) => d.high));
    const lowest = Math.min(...slice.map((d) => d.low));
    const wr =
      highest === lowest
        ? -50
        : ((highest - data[i].close) / (highest - lowest)) * -100;
    result.push({ time: data[i].time, value: wr });
  }
  return result;
}

/** DMI (+DI, -DI, ADX) */
export function calcDMI(
  data: KlinePoint[],
  period = 14
): {
  plusDI: { time: number; value: number }[];
  minusDI: { time: number; value: number }[];
  adx: { time: number; value: number }[];
} {
  if (data.length < period + 1) return { plusDI: [], minusDI: [], adx: [] };
  const trs: number[] = [];
  const plusDMs: number[] = [];
  const minusDMs: number[] = [];
  for (let i = 1; i < data.length; i++) {
    const hl = data[i].high - data[i].low;
    const hc = Math.abs(data[i].high - data[i - 1].close);
    const lc = Math.abs(data[i].low - data[i - 1].close);
    trs.push(Math.max(hl, hc, lc));
    const upMove = data[i].high - data[i - 1].high;
    const downMove = data[i - 1].low - data[i].low;
    plusDMs.push(upMove > downMove && upMove > 0 ? upMove : 0);
    minusDMs.push(downMove > upMove && downMove > 0 ? downMove : 0);
  }
  const smooth = (arr: number[], p: number) => {
    let s = arr.slice(0, p).reduce((a, b) => a + b, 0);
    const out = [s];
    for (let i = p; i < arr.length; i++) {
      s = s - s / p + arr[i];
      out.push(s);
    }
    return out;
  };
  const atr14 = smooth(trs, period);
  const pDM14 = smooth(plusDMs, period);
  const mDM14 = smooth(minusDMs, period);
  const plusDI: { time: number; value: number }[] = [];
  const minusDI: { time: number; value: number }[] = [];
  const adx: { time: number; value: number }[] = [];
  const dxArr: number[] = [];
  for (let i = 0; i < atr14.length; i++) {
    const pdi = atr14[i] === 0 ? 0 : (pDM14[i] / atr14[i]) * 100;
    const mdi = atr14[i] === 0 ? 0 : (mDM14[i] / atr14[i]) * 100;
    const dx =
      pdi + mdi === 0 ? 0 : (Math.abs(pdi - mdi) / (pdi + mdi)) * 100;
    const t = data[i + period].time;
    plusDI.push({ time: t, value: pdi });
    minusDI.push({ time: t, value: mdi });
    dxArr.push(dx);
  }
  if (dxArr.length >= period) {
    let adxVal = dxArr.slice(0, period).reduce((s, v) => s + v, 0) / period;
    adx.push({ time: plusDI[period - 1].time, value: adxVal });
    for (let i = period; i < dxArr.length; i++) {
      adxVal = (adxVal * (period - 1) + dxArr[i]) / period;
      adx.push({ time: plusDI[i].time, value: adxVal });
    }
  }
  return { plusDI, minusDI, adx };
}

/** CCI */
export function calcCCI(
  data: KlinePoint[],
  period = 14
): { time: number; value: number }[] {
  const result: { time: number; value: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1);
    const tps = slice.map((d) => (d.high + d.low + d.close) / 3);
    const mean = tps.reduce((s, v) => s + v, 0) / period;
    const meanDev =
      tps.reduce((s, v) => s + Math.abs(v - mean), 0) / period;
    result.push({
      time: data[i].time,
      value:
        meanDev === 0 ? 0 : (tps[period - 1] - mean) / (0.015 * meanDev),
    });
  }
  return result;
}

/** OBV */
export function calcOBV(
  data: KlinePoint[]
): { time: number; value: number }[] {
  const result: { time: number; value: number }[] = [];
  let obv = 0;
  result.push({ time: data[0].time, value: 0 });
  for (let i = 1; i < data.length; i++) {
    if (data[i].close > data[i - 1].close) obv += data[i].volume;
    else if (data[i].close < data[i - 1].close) obv -= data[i].volume;
    result.push({ time: data[i].time, value: obv });
  }
  return result;
}
