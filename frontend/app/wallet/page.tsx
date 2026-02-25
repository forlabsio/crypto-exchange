"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";

interface WalletEntry {
  asset: string;
  balance: string;
  locked: string;
  price_usdt: number;
  value_usdt: number;
}

const ASSET_ICONS: Record<string, string> = {
  BTC: "₿",
  ETH: "Ξ",
  USDT: "$",
  BNB: "B",
  SOL: "◎",
};

const ASSET_COLORS: Record<string, string> = {
  BTC: "#f7931a",
  ETH: "#627eea",
  USDT: "#26a17b",
  BNB: "#f3ba2f",
  SOL: "#9945ff",
};

export default function WalletPage() {
  const [wallets, setWallets] = useState<WalletEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const { token, hydrate } = useAuthStore();
  const router = useRouter();
  const [depositInfo, setDepositInfo] = useState<{address: string} | null>(null);
  const [txHash, setTxHash] = useState("");
  const [depositResult, setDepositResult] = useState("");

  useEffect(() => {
    hydrate();
  }, []);

  useEffect(() => {
    if (token === null && !loading) {
      router.push("/login");
      return;
    }
    if (!token) return;
    apiFetch("/api/wallet")
      .then(setWallets)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    apiFetch("/api/wallet/deposit/address").then(setDepositInfo).catch(() => {});
  }, []);

  const handleVerifyDeposit = async () => {
    try {
      const res = await apiFetch("/api/wallet/deposit/verify", {
        method: "POST",
        body: JSON.stringify({ tx_hash: txHash }),
      });
      setDepositResult(`✓ ${res.amount_usdt} USDT 입금 완료`);
    } catch (e: any) {
      setDepositResult(`✗ ${e.message}`);
    }
  };

  const totalValueUsdt = wallets.reduce((sum, w) => sum + (w.value_usdt || 0), 0);
  const hasNonUsdt = wallets.some((w) => w.asset !== "USDT" && parseFloat(w.balance) > 0);

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--text-primary)" }}>내 자산</h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>페이퍼 트레이딩 가상 지갑</p>
      </div>

      {/* Total summary */}
      {!loading && wallets.length > 0 && (
        <div className="mb-6 p-5 rounded-2xl" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
          <p className="text-xs mb-2" style={{ color: "var(--text-secondary)" }}>총 자산 (USDT 환산)</p>
          <p className="text-3xl font-bold font-mono" style={{ color: "var(--text-primary)" }}>
            {totalValueUsdt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            <span className="text-base font-normal ml-2" style={{ color: "var(--text-secondary)" }}>USDT</span>
          </p>
          {hasNonUsdt && (
            <p className="text-xs mt-2" style={{ color: "var(--text-secondary)" }}>
              현재 시세 기준 환산값 (실시간 변동)
            </p>
          )}
        </div>
      )}

      {/* Asset cards */}
      {loading ? (
        <div className="text-center py-16" style={{ color: "var(--text-secondary)" }}>로딩 중...</div>
      ) : wallets.length === 0 ? (
        <div className="text-center py-16" style={{ color: "var(--text-secondary)" }}>보유 자산 없음</div>
      ) : (
        <div className="flex flex-col gap-3">
          {wallets.map((w) => {
            const balance = parseFloat(w.balance);
            const locked = parseFloat(w.locked);
            const total = balance + locked;
            const color = ASSET_COLORS[w.asset] || "var(--blue)";
            const isNonUsdt = w.asset !== "USDT";

            return (
              <div key={w.asset} className="rounded-xl p-4"
                style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full flex items-center justify-center text-base font-bold flex-shrink-0"
                      style={{ background: `${color}20`, color }}>
                      {ASSET_ICONS[w.asset] || w.asset[0]}
                    </div>
                    <div>
                      <p className="font-semibold" style={{ color: "var(--text-primary)" }}>{w.asset}</p>
                      {isNonUsdt && w.price_usdt > 0 && (
                        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                          1 {w.asset} = ${w.price_usdt.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-mono font-semibold" style={{ color: "var(--text-primary)" }}>
                      {total.toFixed(w.asset === "USDT" ? 2 : 8)} {w.asset}
                    </p>
                    {isNonUsdt && w.value_usdt > 0 && (
                      <p className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
                        ≈ ${w.value_usdt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT
                      </p>
                    )}
                    {locked > 0 && (
                      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                        잠금: {locked.toFixed(8)}
                      </p>
                    )}
                  </div>
                </div>

                {isNonUsdt && w.value_usdt > 0 && totalValueUsdt > 0 && (
                  <div className="mt-3">
                    <div className="flex justify-between text-xs mb-1" style={{ color: "var(--text-secondary)" }}>
                      <span>포트폴리오 비중</span>
                      <span>{((w.value_usdt / totalValueUsdt) * 100).toFixed(1)}%</span>
                    </div>
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--bg-base)" }}>
                      <div className="h-full rounded-full transition-all"
                        style={{ width: `${(w.value_usdt / totalValueUsdt) * 100}%`, background: color }} />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {depositInfo && (
        <div className="p-4 rounded mt-6" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
          <p className="text-xs mb-1" style={{ color: "var(--text-secondary)" }}>입금 주소 (Polygon USDT-PoS)</p>
          <p className="font-mono text-xs break-all" style={{ color: "var(--text-primary)" }}>{depositInfo.address}</p>
          <p className="text-xs mt-2" style={{ color: "var(--text-secondary)" }}>TX Hash 입금 확인:</p>
          <div className="flex gap-2 mt-1">
            <input value={txHash} onChange={e => setTxHash(e.target.value)}
              placeholder="0x..." className="flex-1 px-2 py-1 rounded text-xs outline-none"
              style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
            <button type="button" onClick={handleVerifyDeposit} className="px-3 py-1 rounded text-xs text-white" style={{ background: "var(--blue)" }}>
              확인
            </button>
          </div>
          {depositResult && <p className="text-xs mt-1" style={{ color: depositResult.startsWith("✓") ? "var(--green)" : "var(--red)" }}>{depositResult}</p>}
        </div>
      )}

      <div className="mt-6 flex gap-4 justify-center text-sm">
        <a href="/exchange/BTC_USDT" className="hover:underline" style={{ color: "var(--blue)" }}>거래소로 이동 →</a>
        <a href="/my-bots" className="hover:underline" style={{ color: "var(--text-secondary)" }}>내 봇 →</a>
      </div>
    </div>
  );
}
