"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import Link from "next/link";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { register } = useAuthStore();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await register(email, password);
      router.push("/login");
    } catch {
      setError("이미 사용 중인 이메일이거나 오류가 발생했습니다.");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-primary)" }}>
      <div className="w-full max-w-sm p-8 rounded-lg" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
        <h1 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>회원가입</h1>
        {error && <p className="text-sm mb-4" style={{ color: "var(--red)" }}>{error}</p>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <input type="email" value={email} onChange={e => setEmail(e.target.value)}
            placeholder="이메일" required className="w-full px-4 py-2 rounded text-sm outline-none"
            style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          <input type="password" value={password} onChange={e => setPassword(e.target.value)}
            placeholder="비밀번호" required className="w-full px-4 py-2 rounded text-sm outline-none"
            style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          <button type="submit" className="w-full py-2 rounded font-semibold text-white"
            style={{ background: "var(--blue)" }}>회원가입</button>
        </form>
        <p className="mt-4 text-sm text-center" style={{ color: "var(--text-secondary)" }}>
          이미 계정이 있으신가요?{" "}
          <Link href="/login" style={{ color: "var(--blue)" }}>로그인</Link>
        </p>
      </div>
    </div>
  );
}
