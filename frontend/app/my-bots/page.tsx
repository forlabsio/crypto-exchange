"use client";
import { useEffect, useState } from "react";
import { useBotStore, Bot, BotTrade } from "@/stores/botStore";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";

const STRATEGY_LABELS: Record<string, string> = {
  alternating: "교차매매",
  rsi: "RSI",
  ma_cross: "MA 크로스",
  boll: "볼린저밴드",
};

const STRATEGY_COLORS: Record<string, string> = {
  alternating: "#6366f1",
  rsi: "#f59e0b",
  ma_cross: "#3b82f6",
  boll: "#8b5cf6",
};

function TradesTable({ trades }: { trades: BotTrade[] }) {
  if (!trades || trades.length === 0) {
    return (
      <p className="text-sm text-center py-6" style={{ color: "var(--text-secondary)" }}>
        거래 내역이 없습니다.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full" style={{ fontSize: "11px", tableLayout: "fixed" }}>
        <colgroup>
          <col style={{ width: "22%" }} />
          <col style={{ width: "16%" }} />
          <col style={{ width: "12%" }} />
          <col style={{ width: "20%" }} />
          <col style={{ width: "18%" }} />
          <col style={{ width: "12%" }} />
        </colgroup>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            {["시간", "페어", "구분", "수량", "가격", "상태"].map((h) => (
              <th key={h} className="py-2 px-1.5 text-left font-medium" style={{ color: "var(--text-secondary)" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => {
            const d = new Date(t.created_at);
            const timeStr = `${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
            const pair = t.pair.replace("_", "/");
            const qty = t.quantity < 0.001 ? t.quantity.toFixed(6) : t.quantity.toFixed(4);
            const price = t.price
              ? t.price >= 1000
                ? t.price.toLocaleString(undefined, { maximumFractionDigits: 0 })
                : t.price.toFixed(2)
              : "-";
            return (
              <tr key={t.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td className="py-1.5 px-1.5 font-mono" style={{ color: "var(--text-secondary)", whiteSpace: "nowrap" }}>{timeStr}</td>
                <td className="py-1.5 px-1.5 font-medium" style={{ color: "var(--text-primary)", whiteSpace: "nowrap" }}>{pair}</td>
                <td className="py-1.5 px-1.5 font-medium" style={{ color: t.side === "buy" ? "var(--green)" : "var(--red)", whiteSpace: "nowrap" }}>
                  {t.side === "buy" ? "매수" : "매도"}
                </td>
                <td className="py-1.5 px-1.5 font-mono" style={{ color: "var(--text-primary)", whiteSpace: "nowrap" }}>{qty}</td>
                <td className="py-1.5 px-1.5 font-mono" style={{ color: "var(--text-primary)", whiteSpace: "nowrap" }}>{price}</td>
                <td className="py-1.5 px-1.5" style={{ whiteSpace: "nowrap" }}>
                  <span className="px-1.5 py-0.5 rounded" style={{
                    background: t.status === "filled" ? "rgba(14,203,129,0.15)" : "rgba(255,255,255,0.05)",
                    color: t.status === "filled" ? "var(--green)" : "var(--text-secondary)",
                  }}>
                    {t.status === "filled" ? "체결" : t.status === "open" ? "미체결" : "취소"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

interface BotPosition {
  pair: string;
  base: string;
  net_qty: number;
  price_usdt: number;
  value_usdt: number;
}

function UnsubscribeModal({
  bot,
  position,
  onClose,
  onConfirm,
  loading,
}: {
  bot: Bot;
  position: BotPosition;
  onClose: () => void;
  onConfirm: (settle: boolean) => void;
  loading: boolean;
}) {
  const hasPosition = position.net_qty > 0;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)" }}
      onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="w-full max-w-sm rounded-2xl p-6 flex flex-col gap-4"
        style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
        <div>
          <h3 className="text-base font-bold mb-1" style={{ color: "var(--text-primary)" }}>
            봇 연동 해제
          </h3>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            <span style={{ color: "var(--text-primary)" }}>{bot.name}</span> 봇 연동을 해제합니다.
          </p>
        </div>

        {hasPosition ? (
          <div className="rounded-xl p-4" style={{ background: "var(--bg-base)", border: "1px solid var(--border)" }}>
            <p className="text-xs mb-2" style={{ color: "var(--text-secondary)" }}>현재 봇이 보유 중인 포지션</p>
            <p className="text-lg font-bold font-mono" style={{ color: "var(--text-primary)" }}>
              {position.net_qty.toFixed(8)} {position.base}
            </p>
            {position.value_usdt > 0 && (
              <p className="text-sm font-mono mt-0.5" style={{ color: "var(--text-secondary)" }}>
                ≈ ${position.value_usdt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT
              </p>
            )}
          </div>
        ) : (
          <div className="rounded-xl p-3 text-sm text-center" style={{ background: "var(--bg-base)", color: "var(--text-secondary)" }}>
            보유 중인 포지션 없음
          </div>
        )}

        <div className="flex flex-col gap-2">
          {hasPosition && (
            <button
              type="button"
              disabled={loading}
              onClick={() => onConfirm(true)}
              className="w-full py-2.5 rounded-xl text-sm font-medium transition-opacity hover:opacity-80 disabled:opacity-40"
              style={{ background: "var(--blue)", color: "#fff" }}>
              {loading ? "처리 중..." : `전량 매도 후 해제 (${position.base} → USDT)`}
            </button>
          )}
          <button
            type="button"
            disabled={loading}
            onClick={() => onConfirm(false)}
            className="w-full py-2.5 rounded-xl text-sm font-medium transition-opacity hover:opacity-80 disabled:opacity-40"
            style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: hasPosition ? "var(--text-secondary)" : "var(--red)" }}>
            {loading ? "처리 중..." : hasPosition ? `그냥 해제 (${position.base} 보유 유지)` : "연동 해제"}
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={onClose}
            className="w-full py-2 text-sm transition-opacity hover:opacity-70"
            style={{ color: "var(--text-secondary)", background: "none", border: "none" }}>
            취소
          </button>
        </div>
      </div>
    </div>
  );
}

function MyBotCard({ bot }: { bot: Bot }) {
  const { trades, fetchBotTrades, unsubscribe, fetchMyBots } = useBotStore();
  const [showTrades, setShowTrades] = useState(false);
  const [unsubModal, setUnsubModal] = useState<BotPosition | null>(null);
  const [unsubscribing, setUnsubscribing] = useState(false);
  const p = bot.performance;
  const isActive = bot.status === "active";
  const strategyColor = STRATEGY_COLORS[bot.strategy_type] || "var(--blue)";
  const allocatedUsdt = bot.allocated_usdt ?? 100;

  const handleToggleTrades = async () => {
    if (!showTrades && !trades[bot.id]) {
      await fetchBotTrades(bot.id);
    }
    setShowTrades((v) => !v);
  };

  const handleUnsubscribeClick = async () => {
    try {
      const pos = await import("@/lib/api").then(({ apiFetch }) =>
        apiFetch(`/api/bots/${bot.id}/position`)
      );
      setUnsubModal(pos);
    } catch {
      setUnsubModal({ pair: "", base: "", net_qty: 0, price_usdt: 0, value_usdt: 0 });
    }
  };

  const handleUnsubscribeConfirm = async (settle: boolean) => {
    setUnsubscribing(true);
    try {
      await unsubscribe(bot.id, settle);
      await fetchMyBots();
      setUnsubModal(null);
    } catch {
      setUnsubscribing(false);
    }
  };

  return (
    <>
    {unsubModal && (
      <UnsubscribeModal
        bot={bot}
        position={unsubModal}
        onClose={() => setUnsubModal(null)}
        onConfirm={handleUnsubscribeConfirm}
        loading={unsubscribing}
      />
    )}
    <div className="rounded-2xl overflow-hidden"
      style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>

      {/* Top accent bar */}
      <div className="h-1" style={{ background: strategyColor }} />

      <div className="p-5 flex flex-col gap-4">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-lg" style={{ color: "var(--text-primary)" }}>{bot.name}</h3>
              <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{
                background: isActive ? "rgba(14,203,129,0.12)" : "rgba(246,70,93,0.12)",
                color: isActive ? "var(--green)" : "var(--red)",
              }}>
                {isActive ? "운영 중" : "중단"}
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
              <span className="px-2 py-0.5 rounded-md font-medium"
                style={{ background: `${strategyColor}18`, color: strategyColor }}>
                {STRATEGY_LABELS[bot.strategy_type] || bot.strategy_type}
              </span>
              {bot.subscribed_at && (
                <span>연동 {new Date(bot.subscribed_at).toLocaleDateString("ko-KR")}</span>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={handleUnsubscribeClick}
            disabled={unsubscribing}
            className="text-xs px-3 py-1.5 rounded-lg transition-opacity hover:opacity-70 disabled:opacity-40"
            style={{ background: "rgba(246,70,93,0.08)", border: "1px solid rgba(246,70,93,0.25)", color: "var(--red)" }}>
            {unsubscribing ? "해제 중..." : "연동 해제"}
          </button>
        </div>

        {/* Investment amount highlight */}
        <div className="rounded-xl p-4 flex items-center justify-between"
          style={{ background: "var(--bg-base)", border: "1px solid var(--border)" }}>
          <div>
            <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>평가 금액</p>
            <p className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
              ${(allocatedUsdt + (bot.pnl_usdt ?? 0)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              <span className="text-sm font-normal ml-1" style={{ color: "var(--text-secondary)" }}>USDT</span>
            </p>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
              원금 ${allocatedUsdt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>수익/손실</p>
            {bot.pnl_usdt !== undefined ? (
              <>
                <p className="text-xl font-bold font-mono" style={{ color: bot.pnl_usdt >= 0 ? "var(--green)" : "var(--red)" }}>
                  {bot.pnl_usdt >= 0 ? "+" : ""}{bot.pnl_usdt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
                <p className="text-xs font-mono" style={{ color: p.monthly_return_pct >= 0 ? "var(--green)" : "var(--red)" }}>
                  ({p.monthly_return_pct >= 0 ? "+" : ""}{p.monthly_return_pct.toFixed(2)}%)
                </p>
              </>
            ) : (
              <p className="text-xl font-bold" style={{ color: p.monthly_return_pct >= 0 ? "var(--green)" : "var(--red)" }}>
                {p.monthly_return_pct >= 0 ? "+" : ""}{p.monthly_return_pct.toFixed(2)}%
              </p>
            )}
          </div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: "승률", value: `${p.win_rate.toFixed(1)}%`, color: p.win_rate >= 50 ? "var(--green)" : "var(--red)" },
            { label: "최대낙폭(MDD)", value: `${p.max_drawdown_pct.toFixed(2)}%`, color: "var(--red)" },
            { label: "샤프 비율", value: p.sharpe_ratio.toFixed(2), color: "var(--text-primary)" },
          ].map(({ label, value, color }) => (
            <div key={label} className="rounded-lg p-3 text-center" style={{ background: "var(--bg-base)" }}>
              <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>{label}</p>
              <p className="text-sm font-semibold" style={{ color }}>{value}</p>
            </div>
          ))}
        </div>

        {/* Trades toggle */}
        <button
          type="button"
          onClick={handleToggleTrades}
          className="text-xs flex items-center justify-center gap-1.5 py-2 rounded-lg transition-colors w-full"
          style={{
            background: showTrades ? "rgba(59,130,246,0.08)" : "var(--bg-base)",
            border: "1px solid var(--border)",
            color: "var(--blue)",
            cursor: "pointer",
          }}>
          {showTrades ? "▲ 거래 내역 닫기" : "▼ 최근 거래 내역 보기"}
        </button>

        {showTrades && (
          <div className="rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)" }}>
            <TradesTable trades={trades[bot.id] ?? []} />
          </div>
        )}
      </div>
    </div>
    </>
  );
}

function SummaryBar({ bots }: { bots: Bot[] }) {
  const totalInvested = bots.reduce((s, b) => s + (b.allocated_usdt ?? 100), 0);
  const totalPnl = bots.reduce((s, b) => s + (b.pnl_usdt ?? 0), 0);
  const totalValue = totalInvested + totalPnl;
  const activeBots = bots.filter((b) => b.status === "active").length;

  return (
    <div className="grid grid-cols-3 gap-3 mb-6">
      <div className="rounded-xl p-4" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
        <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>연동된 봇</p>
        <p className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{bots.length}개</p>
      </div>
      <div className="rounded-xl p-4" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
        <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>운영 중</p>
        <p className="text-lg font-bold" style={{ color: activeBots > 0 ? "var(--green)" : "var(--text-primary)" }}>{activeBots}개</p>
      </div>
      <div className="rounded-xl p-4" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
        <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>총 평가 금액</p>
        <p className="text-lg font-bold font-mono" style={{ color: "var(--text-primary)" }}>
          ${totalValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
        <p className="text-xs font-mono mt-0.5" style={{ color: totalPnl >= 0 ? "var(--green)" : "var(--red)" }}>
          {totalPnl >= 0 ? "+" : ""}{totalPnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT
        </p>
      </div>
    </div>
  );
}

export default function MyBotsPage() {
  const { myBots, fetchMyBots } = useBotStore();
  const { token, hydrate } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    hydrate().then(() => {
      if (!localStorage.getItem("token")) { router.push("/login"); return; }
      fetchMyBots().catch(() => {});
    });
  }, []);

  useEffect(() => {
    if (!token) return;
    const timer = setInterval(() => { fetchMyBots().catch(() => {}); }, 10000);
    return () => clearInterval(timer);
  }, [token]);

  if (!token) return null;

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--text-primary)" }}>내 봇</h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          연동한 자동매매 봇을 관리하고 성과를 확인하세요.
        </p>
      </div>

      {myBots.length === 0 ? (
        <div className="text-center py-24 rounded-2xl" style={{ border: "1px dashed var(--border)" }}>
          <p className="text-4xl mb-4">🤖</p>
          <p className="text-base font-medium mb-1" style={{ color: "var(--text-primary)" }}>연동된 봇이 없습니다</p>
          <p className="text-sm mb-5" style={{ color: "var(--text-secondary)" }}>봇 마켓에서 원하는 전략의 봇을 선택해보세요</p>
          <a href="/bot-market"
            className="inline-block text-sm px-5 py-2.5 rounded-xl font-medium transition-opacity hover:opacity-80"
            style={{ background: "var(--blue)", color: "#fff" }}>
            봇 마켓 보기 →
          </a>
        </div>
      ) : (
        <>
          <SummaryBar bots={myBots} />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {myBots.map((bot) => <MyBotCard key={bot.id} bot={bot} />)}
          </div>
        </>
      )}
    </div>
  );
}
