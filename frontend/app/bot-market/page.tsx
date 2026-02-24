"use client";
import { useEffect, useState } from "react";
import { useBotStore, Bot } from "@/stores/botStore";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

const STRATEGY_LABELS: Record<string, string> = {
  alternating: "교차매매",
  rsi: "RSI",
  ma_cross: "MA 크로스",
  boll: "볼린저밴드",
};

const STRATEGY_COLORS: Record<string, string> = {
  alternating: "var(--blue)",
  rsi: "#a78bfa",
  ma_cross: "var(--green)",
  boll: "#fb923c",
};

function StatBox({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{label}</span>
      <span className="text-sm font-semibold" style={{ color: color || "var(--text-primary)" }}>{value}</span>
    </div>
  );
}

function SubscribeModal({ bot, allocation, onAllocationChange, onConfirm, onCancel, loading, usdtBalance }: {
  bot: Bot;
  allocation: number;
  onAllocationChange: (v: number) => void;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
  usdtBalance: number;
}) {
  const stratColor = STRATEGY_COLORS[bot.strategy_type] || "var(--blue)";
  const isFree = bot.monthly_fee === 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.6)" }}>
      <div className="w-full max-w-sm mx-4 rounded-xl p-6 flex flex-col gap-5"
        style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>

        {/* Header */}
        <div>
          <h2 className="text-lg font-bold mb-1" style={{ color: "var(--text-primary)" }}>봇 연동 확인</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            아래 봇을 내 계정에 연동합니다.
          </p>
        </div>

        {/* Bot info */}
        <div className="rounded-lg p-4 flex flex-col gap-3" style={{ background: "var(--bg-base)" }}>
          <div className="flex items-center justify-between">
            <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{bot.name}</span>
            <span className="text-xs px-2 py-0.5 rounded-full font-medium"
              style={{ background: `${stratColor}22`, color: stratColor }}>
              {STRATEGY_LABELS[bot.strategy_type] || bot.strategy_type}
            </span>
          </div>
          {bot.description && (
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              {bot.description}
            </p>
          )}
          <div className="border-t pt-3" style={{ borderColor: "var(--border)" }}>
            <div className="flex items-center justify-between">
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>월 이용료</span>
              <span className="text-base font-bold" style={{ color: isFree ? "var(--green)" : "var(--text-primary)" }}>
                {isFree ? "무료" : `$${bot.monthly_fee.toFixed(2)}/월`}
              </span>
            </div>
            {!isFree && (
              <p className="text-xs mt-1.5" style={{ color: "var(--text-secondary)" }}>
                ※ 테스트 환경 — 실제 결제는 발생하지 않습니다.
              </p>
            )}
          </div>
          <div className="border-t pt-3" style={{ borderColor: "var(--border)" }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>할당 금액 (USDT)</span>
              <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                보유: {usdtBalance.toLocaleString(undefined, { maximumFractionDigits: 2 })} USDT
              </span>
            </div>
            <input
              type="number"
              min={1}
              max={usdtBalance > 0 ? usdtBalance : undefined}
              step={1}
              value={allocation}
              onChange={(e) => onAllocationChange(Math.max(1, Number(e.target.value)))}
              title="할당 금액 (USDT)"
              placeholder="100"
              className="w-full px-3 py-2 rounded-lg text-sm outline-none"
              style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
          </div>
        </div>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="flex-1 py-2.5 rounded-lg text-sm font-medium transition-opacity hover:opacity-80 disabled:opacity-40"
            style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
            취소
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 py-2.5 rounded-lg text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60"
            style={{ background: "var(--blue)" }}>
            {loading ? "처리 중..." : (isFree ? "무료 연동" : "결제 후 연동")}
          </button>
        </div>
      </div>
    </div>
  );
}

function BotCard({ bot, onSubscribe, onUnsubscribe }: {
  bot: Bot;
  onSubscribe: (bot: Bot) => void;
  onUnsubscribe: (id: number) => void;
}) {
  const p = bot.performance;
  const stratColor = STRATEGY_COLORS[bot.strategy_type] || "var(--blue)";
  const isActive = bot.status === "active";

  return (
    <div className="rounded-xl flex flex-col gap-4 p-5"
      style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>

      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <h3 className="font-semibold text-base leading-tight" style={{ color: "var(--text-primary)" }}>
            {bot.name}
          </h3>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2 py-0.5 rounded-full font-medium"
              style={{ background: `${stratColor}22`, color: stratColor }}>
              {STRATEGY_LABELS[bot.strategy_type] || bot.strategy_type}
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full"
              style={{
                background: isActive ? "rgba(14,203,129,0.15)" : "rgba(246,70,93,0.15)",
                color: isActive ? "var(--green)" : "var(--red)",
              }}>
              {isActive ? "Active" : "Evicted"}
            </span>
          </div>
        </div>
      </div>

      {/* Description */}
      {bot.description && (
        <p className="text-xs leading-relaxed line-clamp-2" style={{ color: "var(--text-secondary)" }}>
          {bot.description}
        </p>
      )}

      {/* Stats grid 2x2 */}
      <div className="grid grid-cols-2 gap-3 py-3 px-3 rounded-lg"
        style={{ background: "var(--bg-base)" }}>
        <StatBox
          label="월 수익률"
          value={`${p.monthly_return_pct >= 0 ? "+" : ""}${p.monthly_return_pct.toFixed(2)}%`}
          color={p.monthly_return_pct >= 0 ? "var(--green)" : "var(--red)"}
        />
        <StatBox
          label="최대 낙폭 (MDD)"
          value={`${p.max_drawdown_pct.toFixed(2)}%`}
          color="var(--red)"
        />
        <StatBox
          label="샤프 비율"
          value={p.sharpe_ratio.toFixed(2)}
        />
        <StatBox
          label="승률"
          value={`${p.win_rate.toFixed(1)}%`}
          color={p.win_rate >= 50 ? "var(--green)" : "var(--red)"}
        />
      </div>

      {/* Footer info */}
      <div className="flex items-center justify-between text-xs" style={{ color: "var(--text-secondary)" }}>
        <div className="flex items-center gap-3">
          <span>운용 {bot.operation_days}일</span>
          <span>·</span>
          <span>구독자 {bot.subscriber_count}명</span>
          <span>·</span>
          <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>
            {bot.monthly_fee === 0 ? "무료" : `$${bot.monthly_fee.toFixed(2)}/월`}
          </span>
        </div>
      </div>

      {/* Action button */}
      {bot.is_subscribed ? (
        <button
          type="button"
          onClick={() => onUnsubscribe(bot.id)}
          className="w-full py-2.5 rounded-lg text-sm font-medium transition-opacity hover:opacity-80"
          style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
          연동 해제
        </button>
      ) : (
        <button
          type="button"
          onClick={() => onSubscribe(bot)}
          disabled={!isActive}
          className="w-full py-2.5 rounded-lg text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
          style={{ background: "var(--blue)" }}>
          봇 연동
        </button>
      )}
    </div>
  );
}

export default function BotMarketPage() {
  const { bots, fetchBots, subscribe, unsubscribe } = useBotStore();
  const { token, hydrate } = useAuthStore();
  const router = useRouter();

  const [pendingBot, setPendingBot] = useState<Bot | null>(null);
  const [subscribing, setSubscribing] = useState(false);
  const [usdtBalance, setUsdtBalance] = useState<number>(0);
  const [pendingAllocation, setPendingAllocation] = useState<number>(100);

  useEffect(() => {
    hydrate().then(() => fetchBots().catch(() => {}));
  }, []);

  useEffect(() => {
    if (!token) return;
    fetchUsdtBalance();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const fetchUsdtBalance = () => {
    if (!token) return;
    apiFetch("/api/wallet")
      .then((data: Array<{ asset: string; balance: string }>) => {
        const usdt = data.find((w) => w.asset === "USDT");
        setUsdtBalance(usdt ? parseFloat(usdt.balance) : 0);
      })
      .catch(() => {});
  };

  const handleSubscribeClick = (bot: Bot) => {
    if (!token) { router.push("/login"); return; }
    fetchUsdtBalance();
    setPendingAllocation(100);
    setPendingBot(bot);
  };

  const handleConfirmSubscribe = async () => {
    if (!pendingBot) return;
    if (pendingAllocation <= 0 || (usdtBalance > 0 && pendingAllocation > usdtBalance)) {
      alert(`할당 금액은 1 이상 보유 잔액(${usdtBalance.toFixed(2)} USDT) 이하여야 합니다.`);
      return;
    }
    setSubscribing(true);
    try {
      await subscribe(pendingBot.id, pendingAllocation);
      await fetchBots();
      fetchUsdtBalance();
      setPendingBot(null);
      alert("봇 연동이 완료되었습니다!");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes("Already subscribed")) {
        alert("이미 연동된 봇입니다.");
        setPendingBot(null);
      } else {
        alert("연동 실패: " + msg);
        // Keep modal open so user can adjust and retry
      }
    } finally {
      setSubscribing(false);
    }
  };

  const handleUnsubscribe = async (botId: number) => {
    if (!token) { router.push("/login"); return; }
    try {
      await unsubscribe(botId);
      await fetchBots();
      alert("봇 연동이 해제되었습니다.");
    } catch (e: unknown) {
      alert("해제 실패: " + (e instanceof Error ? e.message : String(e)));
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {pendingBot && (
        <SubscribeModal
          bot={pendingBot}
          allocation={pendingAllocation}
          onAllocationChange={setPendingAllocation}
          onConfirm={handleConfirmSubscribe}
          onCancel={() => setPendingBot(null)}
          loading={subscribing}
          usdtBalance={usdtBalance}
        />
      )}

      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>봇 마켓</h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          봇을 선택하면 내 지갑과 연동하여 자동매매를 시작합니다.
        </p>
      </div>

      {!token && (
        <div className="mb-6 p-4 rounded-lg border" style={{ background: "var(--bg-panel)", borderColor: "var(--border)" }}>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            봇 마켓을 이용하려면{" "}
            <a href="/login" style={{ color: "var(--blue)" }}>로그인</a>
            이 필요합니다.
          </p>
        </div>
      )}

      {bots.length === 0 ? (
        <div className="text-center py-20" style={{ color: "var(--text-secondary)" }}>
          <p className="text-lg mb-2">등록된 봇이 없습니다</p>
          <p className="text-sm">운영팀이 봇을 등록하면 여기에 표시됩니다.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {bots.map((bot) => (
            <BotCard
              key={bot.id}
              bot={bot}
              onSubscribe={handleSubscribeClick}
              onUnsubscribe={handleUnsubscribe}
            />
          ))}
        </div>
      )}
    </div>
  );
}
