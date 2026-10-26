import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "../supabase";

/**
 * Single-user mode: chỉ cho phép email trong whitelist login.
 *
 * Whitelist lấy từ env var VITE_ALLOWED_EMAILS (CSV, comma-separated).
 * Nếu env trống, default = owner email hardcode.
 *
 * Session persist tự động qua Supabase client (persistSession: true trong supabase.ts),
 * nên sau khi login 1 lần, user ko phải login lại trừ khi:
 *   - Logout chủ động
 *   - localStorage bị clear
 *   - Refresh token hết hạn (default 1 tuần, auto refresh nếu active)
 */
const DEFAULT_OWNER_EMAIL = "hienhd15411@gmail.com";

const ALLOWED_EMAILS: Set<string> = (() => {
  const raw = (import.meta.env.VITE_ALLOWED_EMAILS as string | undefined) ?? "";
  const list = raw
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
  if (list.length === 0) list.push(DEFAULT_OWNER_EMAIL);
  return new Set(list);
})();

function isAllowed(email: string): boolean {
  return ALLOWED_EMAILS.has(email.trim().toLowerCase());
}

export function AuthGate({ children }: { children: (session: Session) => ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [recovery, setRecovery] = useState(false);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    // Recovery link: #type=recovery&access_token=…
    const hash = window.location.hash;
    if (hash.includes("type=recovery")) {
      setRecovery(true);
    }

    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data } = supabase.auth.onAuthStateChange((event, s) => {
      setSession(s);
      if (event === "PASSWORD_RECOVERY") {
        setRecovery(true);
      }
    });
    return () => data.subscription.unsubscribe();
  }, []);

  // Nếu session đã có nhưng email không trong whitelist → signOut ngay.
  // Phòng trường hợp whitelist bị thu hẹp sau khi user đã login từ trước.
  useEffect(() => {
    if (session && session.user?.email && !isAllowed(session.user.email)) {
      supabase.auth.signOut();
      setError("Tài khoản này không có quyền truy cập.");
    }
  }, [session]);

  function resetMsgs() {
    setError(null);
    setInfo(null);
  }

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    resetMsgs();
    if (!isAllowed(email)) {
      setError("Tài khoản này không có quyền truy cập.");
      return;
    }
    setBusy(true);
    const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
    setBusy(false);
    if (error) setError(mapError(error.message));
  }

  async function handleForgot() {
    resetMsgs();
    if (!email.trim()) {
      setError("Nhập email trước rồi click 'Quên password'.");
      return;
    }
    if (!isAllowed(email)) {
      setError("Tài khoản này không có quyền truy cập.");
      return;
    }
    setBusy(true);
    const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
      redirectTo: window.location.origin,
    });
    setBusy(false);
    if (error) setError(mapError(error.message));
    else setInfo("Đã gửi email reset password. Check inbox.");
  }

  async function handleUpdatePassword(e: FormEvent) {
    e.preventDefault();
    resetMsgs();
    if (password.length < 6) {
      setError("Password tối thiểu 6 ký tự.");
      return;
    }
    if (password !== password2) {
      setError("Password nhập lại không khớp.");
      return;
    }
    setBusy(true);
    const { error } = await supabase.auth.updateUser({ password });
    setBusy(false);
    if (error) {
      setError(mapError(error.message));
      return;
    }
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    await supabase.auth.signOut();
    setRecovery(false);
    setPassword("");
    setPassword2("");
    setInfo("Đã đổi password. Đăng nhập lại với password mới.");
  }

  if (loading) return <div style={{ padding: 40 }}>Loading…</div>;

  // 1. Recovery flow — chặn vô app, bắt đổi password trước
  if (recovery) {
    return (
      <div
        style={{
          maxWidth: 400,
          margin: "8vh auto",
          padding: 24,
          background: "var(--panel)",
          borderRadius: 8,
        }}
      >
        <h2 style={{ marginTop: 0 }}>Đổi password</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Nhập password mới cho tài khoản{session?.user?.email ? ` ${session.user.email}` : ""}.
        </p>
        <form
          onSubmit={handleUpdatePassword}
          style={{ display: "flex", flexDirection: "column", gap: 12 }}
        >
          <input
            type="password"
            required
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password mới (tối thiểu 6 ký tự)"
          />
          <input
            type="password"
            required
            autoComplete="new-password"
            value={password2}
            onChange={(e) => setPassword2(e.target.value)}
            placeholder="Nhập lại password mới"
          />
          <button type="submit" disabled={busy}>
            {busy ? "Đang xử lý…" : "Đổi password"}
          </button>
          {error && <div className="error">{error}</div>}
          {info && <div className="success">{info}</div>}
        </form>
      </div>
    );
  }

  // 2. Chưa login → form đăng nhập (ko có tab signup — single-user mode)
  if (!session) {
    return (
      <div
        style={{
          maxWidth: 400,
          margin: "10vh auto",
          padding: 24,
          background: "var(--panel)",
          borderRadius: 8,
        }}
      >
        <h2 style={{ marginTop: 0 }}>DA Tool</h2>
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
          Private tool. Chỉ owner mới truy cập được.
        </p>

        <form
          onSubmit={handleLogin}
          style={{ display: "flex", flexDirection: "column", gap: 12 }}
        >
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="email@example.com"
          />
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
          />
          <button type="submit" disabled={busy}>
            {busy ? "Đang xử lý…" : "Đăng nhập"}
          </button>
          <button
            type="button"
            onClick={handleForgot}
            disabled={busy}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--accent)",
              cursor: "pointer",
              fontSize: 13,
              padding: 0,
              textAlign: "left",
            }}
          >
            Quên password?
          </button>
          {error && <div className="error">{error}</div>}
          {info && <div className="success">{info}</div>}
        </form>
      </div>
    );
  }

  return <>{children(session)}</>;
}

function mapError(msg: string): string {
  const m = msg.toLowerCase();
  if (m.includes("invalid login credentials")) return "Email hoặc password sai.";
  if (m.includes("email not confirmed")) return "Email chưa được confirm. Check inbox.";
  if (m.includes("rate limit")) return "Quá nhiều lần thử. Đợi 1 phút rồi thử lại.";
  if (m.includes("password should be")) return "Password quá ngắn (tối thiểu 6 ký tự).";
  if (m.includes("same as the old")) return "Password mới không được trùng password cũ.";
  return msg;
}
