"use client";
import { useState } from "react";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";
import Link from "next/link";
import styles from "./login.module.css";

export default function LoginPage() {
  const { login, loginWithMetaMask } = useAuthStore();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleMetaMask = async () => {
    setError("");
    setLoading(true);
    try {
      await loginWithMetaMask();
      router.push("/exchange/BTC_USDT");
    } catch (e: any) {
      setError(e.message || "MetaMask 로그인 실패");
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push("/exchange/BTC_USDT");
    } catch {
      setError("이메일 또는 비밀번호가 올바르지 않습니다.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-primary)" }}>
      <div className="w-full max-w-sm p-8 rounded-lg" style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}>
        <h1 className="text-xl font-bold mb-6 text-center" style={{ color: "var(--text-primary)" }}>로그인</h1>

        {/* MetaMask Button */}
        <button
          type="button"
          onClick={handleMetaMask}
          disabled={loading}
          className="w-full py-3 rounded font-medium mb-4 flex items-center justify-center gap-2"
          style={{ background: "#f6851b", color: "white" }}>
          {loading ? "처리 중..." : "🦊 MetaMask로 로그인"}
        </button>

        <div className="text-center text-xs mb-4" style={{ color: "var(--text-secondary)" }}>또는 이메일로 로그인</div>

        <form onSubmit={handleLogin} className="flex flex-col gap-3">
          <input type="email" placeholder="이메일" value={email} onChange={e => setEmail(e.target.value)}
            required
            className="px-3 py-2 rounded text-sm outline-none"
            style={{ background: "var(--bg-panel)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          <input type="password" placeholder="비밀번호" value={password} onChange={e => setPassword(e.target.value)}
            required
            className="px-3 py-2 rounded text-sm outline-none"
            style={{ background: "var(--bg-panel)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          {error && <p className="text-xs" style={{ color: "var(--red)" }}>{error}</p>}
          <button type="submit" disabled={loading}
            className="py-2 rounded font-medium text-white"
            style={{ background: "var(--blue)" }}>
            {loading ? "로그인 중..." : "로그인"}
          </button>
        </form>
        <p className={`mt-4 text-sm text-center ${styles.registerPrompt}`}>
          계정이 없으신가요?{" "}
          <Link href="/register" className={styles.registerLink}>회원가입</Link>
        </p>
      </div>
    </div>
  );
}
