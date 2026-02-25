"use client";
import Link from "next/link";
import { useEffect } from "react";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";

export default function Navbar() {
  const { token, user, logout, hydrate } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    hydrate();
  }, []);

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <nav className="flex items-center justify-between px-6 h-14 border-b flex-shrink-0"
      style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}>
      <div className="flex items-center gap-8">
        <Link href="/exchange/BTC_USDT" className="text-lg font-bold" style={{ color: "var(--blue)" }}>
          ForLabsEX
        </Link>
        <div className="flex items-center gap-6 text-sm" style={{ color: "var(--text-secondary)" }}>
          <Link href="/exchange/BTC_USDT" className="hover:text-white transition-colors">거래소</Link>
          <Link href="/futures/BTC_USDT" className="hover:text-white transition-colors">선물</Link>
<Link href="/announcements" className="hover:text-white transition-colors">공지사항</Link>
          <Link href="/bot-market" className="hover:text-white transition-colors">봇 마켓</Link>
          {token && (
            <Link href="/my-bots" className="hover:text-white transition-colors">내 봇</Link>
          )}
          {user?.role === "admin" && (
            <Link href="/admin/bots" className="hover:text-white transition-colors font-medium" style={{ color: "#f59e0b" }}>
              관리자
            </Link>
          )}
        </div>
      </div>
      <div className="flex items-center gap-4 text-sm">
        {token ? (
          <>
            <Link href="/wallet" style={{ color: "var(--text-secondary)" }} className="hover:text-white transition-colors">자산</Link>
            <button
              type="button"
              onClick={handleLogout}
              className="px-4 py-1.5 rounded text-sm"
              style={{ background: "var(--bg-panel)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
              로그아웃
            </button>
          </>
        ) : (
          <>
            <Link href="/login" style={{ color: "var(--text-secondary)" }} className="hover:text-white transition-colors">로그인</Link>
            <Link href="/register"
              className="px-4 py-1.5 rounded text-sm font-medium text-white"
              style={{ background: "var(--blue)" }}>회원가입</Link>
          </>
        )}
      </div>
    </nav>
  );
}
