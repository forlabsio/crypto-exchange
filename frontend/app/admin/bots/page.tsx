"use client";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

const STRATEGY_TYPES = [
  { value: "alternating", label: "교차매매" },
  { value: "rsi", label: "RSI" },
  { value: "ma_cross", label: "MA 크로스" },
  { value: "boll", label: "볼린저밴드" },
];

const PAIRS = ["BTC_USDT", "ETH_USDT", "BNB_USDT", "SOL_USDT"];

interface AdminBot {
  id: number;
  name: string;
  description: string;
  strategy_type: string;
  strategy_config: Record<string, unknown>;
  status: string;
  max_drawdown_limit: number;
  monthly_fee: number;
  subscriber_count: number;
  created_at: string | null;
}

interface AdminSubscription {
  id: number;
  user_id: number;
  user_email: string | null;
  user_wallet: string | null;
  bot_id: number;
  bot_name: string | null;
  allocated_usdt: number;
  fee_paid_usdt: number;
  started_at: string | null;
  next_renewal_at: string | null;
}

interface FeeIncomeSummary {
  unsettled_total: number;
  unsettled: FeeIncomeItem[];
  settled_total: number;
  settled: FeeIncomeItem[];
}

interface FeeIncomeItem {
  id: number;
  user_id: number;
  bot_id: number;
  amount_usdt: number;
  period: string;
  charged_at: string | null;
  settled_at: string | null;
}

interface FormState {
  name: string;
  description: string;
  strategy_type: string;
  max_drawdown_limit: number;
  monthly_fee: number;
  // common config
  pair: string;
  trade_pct: number;
  signal_interval: number;
  // rsi
  rsi_period: number;
  overbought: number;
  oversold: number;
  // ma_cross
  fast_period: number;
  slow_period: number;
  // boll
  period: number;
  deviation: number;
}

const DEFAULT_FORM: FormState = {
  name: "",
  description: "",
  strategy_type: "alternating",
  max_drawdown_limit: 20,
  monthly_fee: 0,
  pair: "BTC_USDT",
  trade_pct: 10,
  signal_interval: 300,
  rsi_period: 14,
  overbought: 70,
  oversold: 30,
  fast_period: 5,
  slow_period: 20,
  period: 20,
  deviation: 2.0,
};

function buildStrategyConfig(form: FormState): Record<string, unknown> {
  const base = { pair: form.pair, trade_pct: form.trade_pct, signal_interval: form.signal_interval };
  switch (form.strategy_type) {
    case "rsi":
      return { ...base, rsi_period: form.rsi_period, overbought: form.overbought, oversold: form.oversold };
    case "ma_cross":
      return { ...base, fast_period: form.fast_period, slow_period: form.slow_period };
    case "boll":
      return { ...base, period: form.period, deviation: form.deviation };
    default:
      return base;
  }
}

function parseFormFromBot(bot: AdminBot): FormState {
  const c = bot.strategy_config || {};
  return {
    name: bot.name,
    description: bot.description,
    strategy_type: bot.strategy_type,
    max_drawdown_limit: bot.max_drawdown_limit,
    monthly_fee: bot.monthly_fee,
    pair: (c.pair as string) || "BTC_USDT",
    trade_pct: (c.trade_pct as number) || 10,
    signal_interval: (c.signal_interval as number) || 300,
    rsi_period: (c.rsi_period as number) || 14,
    overbought: (c.overbought as number) || 70,
    oversold: (c.oversold as number) || 30,
    fast_period: (c.fast_period as number) || 5,
    slow_period: (c.slow_period as number) || 20,
    period: (c.period as number) || 20,
    deviation: (c.deviation as number) || 2.0,
  };
}

function InputRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>{label}</label>
      {children}
    </div>
  );
}

const inputCls = "w-full px-3 py-2 rounded-lg text-sm outline-none";
const inputStyle = { background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-primary)" };

function BotModal({ initial, onClose, onSave }: {
  initial?: AdminBot | null;
  onClose: () => void;
  onSave: () => void;
}) {
  const [form, setForm] = useState<FormState>(initial ? parseFormFromBot(initial) : DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const set = (key: keyof FormState, value: string | number) =>
    setForm((f) => ({ ...f, [key]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const body = {
        name: form.name,
        description: form.description,
        strategy_type: form.strategy_type,
        strategy_config: buildStrategyConfig(form),
        max_drawdown_limit: form.max_drawdown_limit,
        monthly_fee: form.monthly_fee,
      };
      if (initial) {
        await apiFetch(`/api/admin/bots/${initial.id}`, { method: "PUT", body: JSON.stringify(body) });
      } else {
        await apiFetch("/api/admin/bots", { method: "POST", body: JSON.stringify(body) });
      }
      onSave();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.6)" }}>
      <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-xl p-6 flex flex-col gap-4"
        style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>

        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            {initial ? "봇 수정" : "새 봇 등록"}
          </h2>
          <button type="button" onClick={onClose} className="text-xl leading-none" style={{ color: "var(--text-secondary)" }}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <InputRow label="봇 이름">
            <input className={inputCls} style={inputStyle} value={form.name}
              onChange={(e) => set("name", e.target.value)} required placeholder="Alpha RSI Bot" />
          </InputRow>

          <InputRow label="설명">
            <textarea className={inputCls} style={{ ...inputStyle, resize: "vertical" }} rows={2}
              value={form.description} onChange={(e) => set("description", e.target.value)}
              placeholder="봇 설명을 입력하세요" />
          </InputRow>

          <InputRow label="전략 타입">
            <select className={inputCls} style={inputStyle} value={form.strategy_type}
              onChange={(e) => set("strategy_type", e.target.value)}>
              {STRATEGY_TYPES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </InputRow>

          {/* Common params */}
          <div className="grid grid-cols-3 gap-2">
            <InputRow label="거래 페어">
              <select className={inputCls} style={inputStyle} value={form.pair}
                onChange={(e) => set("pair", e.target.value)}>
                {PAIRS.map((p) => <option key={p} value={p}>{p.replace("_", "/")}</option>)}
              </select>
            </InputRow>
            <InputRow label="거래 비율 (%)">
              <input type="number" className={inputCls} style={inputStyle} value={form.trade_pct}
                min={1} max={100} onChange={(e) => set("trade_pct", Number(e.target.value))} />
            </InputRow>
            <InputRow label="신호 주기 (초)">
              <input type="number" className={inputCls} style={inputStyle} value={form.signal_interval}
                min={60} onChange={(e) => set("signal_interval", Number(e.target.value))} />
            </InputRow>
          </div>

          {/* RSI params */}
          {form.strategy_type === "rsi" && (
            <div className="grid grid-cols-3 gap-2">
              <InputRow label="RSI 기간">
                <input type="number" className={inputCls} style={inputStyle} value={form.rsi_period}
                  onChange={(e) => set("rsi_period", Number(e.target.value))} />
              </InputRow>
              <InputRow label="과매수">
                <input type="number" className={inputCls} style={inputStyle} value={form.overbought}
                  onChange={(e) => set("overbought", Number(e.target.value))} />
              </InputRow>
              <InputRow label="과매도">
                <input type="number" className={inputCls} style={inputStyle} value={form.oversold}
                  onChange={(e) => set("oversold", Number(e.target.value))} />
              </InputRow>
            </div>
          )}

          {/* MA Cross params */}
          {form.strategy_type === "ma_cross" && (
            <div className="grid grid-cols-2 gap-2">
              <InputRow label="단기 MA">
                <input type="number" className={inputCls} style={inputStyle} value={form.fast_period}
                  onChange={(e) => set("fast_period", Number(e.target.value))} />
              </InputRow>
              <InputRow label="장기 MA">
                <input type="number" className={inputCls} style={inputStyle} value={form.slow_period}
                  onChange={(e) => set("slow_period", Number(e.target.value))} />
              </InputRow>
            </div>
          )}

          {/* Bollinger params */}
          {form.strategy_type === "boll" && (
            <div className="grid grid-cols-2 gap-2">
              <InputRow label="기간">
                <input type="number" className={inputCls} style={inputStyle} value={form.period}
                  onChange={(e) => set("period", Number(e.target.value))} />
              </InputRow>
              <InputRow label="표준편차 배수">
                <input type="number" step="0.1" className={inputCls} style={inputStyle} value={form.deviation}
                  onChange={(e) => set("deviation", Number(e.target.value))} />
              </InputRow>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            <InputRow label="최대 낙폭 한도 (%)">
              <input type="number" className={inputCls} style={inputStyle} value={form.max_drawdown_limit}
                onChange={(e) => set("max_drawdown_limit", Number(e.target.value))} />
            </InputRow>
            <InputRow label="월 구독료 ($)">
              <input type="number" step="0.01" className={inputCls} style={inputStyle} value={form.monthly_fee}
                onChange={(e) => set("monthly_fee", Number(e.target.value))} />
            </InputRow>
          </div>

          {error && <p className="text-xs" style={{ color: "var(--red)" }}>{error}</p>}

          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 py-2.5 rounded-lg text-sm font-medium"
              style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
              취소
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 py-2.5 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--blue)" }}>
              {saving ? "저장 중..." : "저장"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function BotsTab({
  bots,
  onEdit,
  onDelete,
  onNew,
}: {
  bots: AdminBot[];
  onEdit: (bot: AdminBot) => void;
  onDelete: (bot: AdminBot) => void;
  onNew: () => void;
}) {
  const STRATEGY_LABELS: Record<string, string> = {
    alternating: "교차매매", rsi: "RSI", ma_cross: "MA 크로스", boll: "볼린저밴드",
  };

  return (
    <>
      <div className="flex items-center justify-between mb-6">
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          총 {bots.length}개 봇
        </p>
        <button
          type="button"
          onClick={onNew}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white"
          style={{ background: "var(--blue)" }}>
          + 새 봇 등록
        </button>
      </div>

      {bots.length === 0 ? (
        <div className="text-center py-20" style={{ color: "var(--text-secondary)" }}>
          <p className="text-lg mb-2">등록된 봇이 없습니다</p>
        </div>
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "var(--bg-panel)", borderBottom: "1px solid var(--border)" }}>
                {["봇 이름", "전략", "상태", "구독자", "구독료", "등록일", ""].map((h) => (
                  <th key={h} className="py-3 px-4 text-left font-medium" style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bots.map((bot) => (
                <tr key={bot.id} style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-base)" }}>
                  <td className="py-3 px-4 font-medium" style={{ color: "var(--text-primary)" }}>{bot.name}</td>
                  <td className="py-3 px-4" style={{ color: "var(--text-secondary)" }}>
                    {STRATEGY_LABELS[bot.strategy_type] || bot.strategy_type}
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{
                      background: bot.status === "active" ? "rgba(14,203,129,0.15)" : "rgba(246,70,93,0.15)",
                      color: bot.status === "active" ? "var(--green)" : "var(--red)",
                    }}>
                      {bot.status === "active" ? "Active" : "Evicted"}
                    </span>
                  </td>
                  <td className="py-3 px-4" style={{ color: "var(--text-primary)" }}>{bot.subscriber_count}명</td>
                  <td className="py-3 px-4" style={{ color: "var(--text-primary)" }}>
                    {bot.monthly_fee === 0 ? "무료" : `$${bot.monthly_fee}`}
                  </td>
                  <td className="py-3 px-4 text-xs" style={{ color: "var(--text-secondary)" }}>
                    {bot.created_at ? new Date(bot.created_at).toLocaleDateString("ko-KR") : "-"}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => onEdit(bot)}
                        className="text-xs px-2.5 py-1 rounded transition-opacity hover:opacity-70"
                        style={{ background: "var(--bg-panel)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                        수정
                      </button>
                      {bot.status === "active" && (
                        <button
                          type="button"
                          onClick={() => onDelete(bot)}
                          className="text-xs px-2.5 py-1 rounded transition-opacity hover:opacity-70"
                          style={{ background: "rgba(246,70,93,0.15)", border: "1px solid rgba(246,70,93,0.3)", color: "var(--red)" }}>
                          퇴출
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function SubscriptionsTab() {
  const [subs, setSubs] = useState<AdminSubscription[]>([]);
  const [feeIncome, setFeeIncome] = useState<FeeIncomeSummary | null>(null);
  const [settling, setSettling] = useState(false);
  const [settleMsg, setSettleMsg] = useState("");

  const loadData = async () => {
    try {
      const [subsData, feeData] = await Promise.all([
        apiFetch("/api/admin/subscriptions"),
        apiFetch("/api/admin/fee-income"),
      ]);
      setSubs(subsData);
      setFeeIncome(feeData);
    } catch {
      // silently handled
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSettle = async () => {
    if (!confirm("미정산 수수료를 모두 정산 완료 처리하시겠습니까?")) return;
    setSettling(true);
    setSettleMsg("");
    try {
      const res = await apiFetch("/api/admin/fee-income/settle", { method: "POST" });
      setSettleMsg(res.message || "정산 완료");
      await loadData();
    } catch (e: unknown) {
      setSettleMsg(e instanceof Error ? e.message : "정산 실패");
    } finally {
      setSettling(false);
    }
  };

  const handleCancelSub = async (sub: AdminSubscription) => {
    if (!confirm(`"${sub.user_email}" 사용자의 "${sub.bot_name}" 구독을 강제 해지하시겠습니까?`)) return;
    try {
      await apiFetch(`/api/admin/subscriptions/${sub.id}`, { method: "DELETE" });
      await loadData();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "해지 실패");
    }
  };

  const fmtDate = (iso: string | null) =>
    iso ? new Date(iso).toLocaleDateString("ko-KR") : "-";

  return (
    <>
      {/* Settle button and summary */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="text-sm" style={{ color: "var(--text-secondary)" }}>
            미정산 수수료:{" "}
            <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
              ${feeIncome ? feeIncome.unsettled_total.toFixed(2) : "0.00"}
            </span>
          </div>
          {settleMsg && (
            <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(14,203,129,0.15)", color: "var(--green)" }}>
              {settleMsg}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={handleSettle}
          disabled={settling}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
          style={{ background: "var(--blue)" }}>
          {settling ? "처리 중..." : "정산 완료"}
        </button>
      </div>

      {/* Subscriptions table */}
      {subs.length === 0 ? (
        <div className="text-center py-20" style={{ color: "var(--text-secondary)" }}>
          <p className="text-lg mb-2">활성 구독이 없습니다</p>
        </div>
      ) : (
        <div className="rounded-xl overflow-hidden mb-8" style={{ border: "1px solid var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "var(--bg-panel)", borderBottom: "1px solid var(--border)" }}>
                {["사용자", "봇", "투자금", "구독료 누계", "시작일", "갱신일", "해지"].map((h) => (
                  <th key={h} className="py-3 px-4 text-left font-medium" style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {subs.map((sub) => (
                <tr key={sub.id} style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-base)" }}>
                  <td className="py-3 px-4" style={{ color: "var(--text-primary)" }}>
                    <div className="font-medium">{sub.user_email || "-"}</div>
                    {sub.user_wallet && (
                      <div className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
                        {sub.user_wallet.slice(0, 8)}...{sub.user_wallet.slice(-6)}
                      </div>
                    )}
                  </td>
                  <td className="py-3 px-4" style={{ color: "var(--text-secondary)" }}>{sub.bot_name || "-"}</td>
                  <td className="py-3 px-4 font-medium" style={{ color: "var(--text-primary)" }}>
                    ${sub.allocated_usdt.toFixed(2)}
                  </td>
                  <td className="py-3 px-4" style={{ color: "var(--text-secondary)" }}>
                    ${sub.fee_paid_usdt.toFixed(2)}
                  </td>
                  <td className="py-3 px-4 text-xs" style={{ color: "var(--text-secondary)" }}>
                    {fmtDate(sub.started_at)}
                  </td>
                  <td className="py-3 px-4 text-xs" style={{ color: "var(--text-secondary)" }}>
                    {fmtDate(sub.next_renewal_at)}
                  </td>
                  <td className="py-3 px-4">
                    <button
                      type="button"
                      onClick={() => handleCancelSub(sub)}
                      className="text-xs px-2.5 py-1 rounded transition-opacity hover:opacity-70"
                      style={{ background: "rgba(246,70,93,0.15)", border: "1px solid rgba(246,70,93,0.3)", color: "var(--red)" }}>
                      해지
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Fee income summary */}
      {feeIncome && (
        <div className="rounded-xl p-5" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>수수료 수입 현황</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg p-4" style={{ background: "var(--bg-base)", border: "1px solid var(--border)" }}>
              <div className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>미정산 합계</div>
              <div className="text-lg font-bold" style={{ color: "var(--red)" }}>
                ${feeIncome.unsettled_total.toFixed(2)}
              </div>
              <div className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
                {feeIncome.unsettled.length}건
              </div>
            </div>
            <div className="rounded-lg p-4" style={{ background: "var(--bg-base)", border: "1px solid var(--border)" }}>
              <div className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>정산 완료 합계</div>
              <div className="text-lg font-bold" style={{ color: "var(--green)" }}>
                ${feeIncome.settled_total.toFixed(2)}
              </div>
              <div className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
                {feeIncome.settled.length}건
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default function AdminBotsPage() {
  const { token, user, hydrate } = useAuthStore();
  const router = useRouter();
  const [bots, setBots] = useState<AdminBot[]>([]);
  const [modal, setModal] = useState<{ open: boolean; bot: AdminBot | null }>({ open: false, bot: null });
  const [activeTab, setActiveTab] = useState<"bots" | "subscriptions">("bots");

  useEffect(() => {
    hydrate().then(() => {
      const t = localStorage.getItem("token");
      if (!t) { router.push("/login"); return; }
    });
  }, []);

  useEffect(() => {
    if (user && user.role !== "admin") { router.push("/"); }
    if (user && user.role === "admin") { loadBots(); }
  }, [user]);

  const loadBots = async () => {
    try {
      const data = await apiFetch("/api/admin/bots");
      setBots(data);
    } catch {
      // handled by redirect
    }
  };

  const handleDelete = async (bot: AdminBot) => {
    if (!confirm(`"${bot.name}" 봇을 퇴출하시겠습니까? 모든 구독자의 연동이 해제됩니다.`)) return;
    await apiFetch(`/api/admin/bots/${bot.id}`, { method: "DELETE" });
    loadBots();
  };

  if (!user || user.role !== "admin") {
    return (
      <div className="flex items-center justify-center h-64" style={{ color: "var(--text-secondary)" }}>
        접근 권한이 없습니다.
      </div>
    );
  }

  const tabBase = "px-4 py-2 text-sm font-medium rounded-lg transition-colors";
  const tabActive = { background: "var(--blue)", color: "#fff" };
  const tabInactive = { background: "transparent", color: "var(--text-secondary)", border: "1px solid var(--border)" };

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>봇 관리</h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>관리자 전용</p>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-2 mb-6">
        <button
          type="button"
          className={tabBase}
          style={activeTab === "bots" ? tabActive : tabInactive}
          onClick={() => setActiveTab("bots")}>
          봇 목록
        </button>
        <button
          type="button"
          className={tabBase}
          style={activeTab === "subscriptions" ? tabActive : tabInactive}
          onClick={() => setActiveTab("subscriptions")}>
          구독 관리
        </button>
      </div>

      {activeTab === "bots" && (
        <BotsTab
          bots={bots}
          onEdit={(bot) => setModal({ open: true, bot })}
          onDelete={handleDelete}
          onNew={() => setModal({ open: true, bot: null })}
        />
      )}

      {activeTab === "subscriptions" && <SubscriptionsTab />}

      {modal.open && (
        <BotModal
          initial={modal.bot}
          onClose={() => setModal({ open: false, bot: null })}
          onSave={() => { setModal({ open: false, bot: null }); loadBots(); }}
        />
      )}
    </div>
  );
}
