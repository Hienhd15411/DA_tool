import { useEffect, useState, type ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "../supabase";

/**
 * Single-user mode với AUTO-LOGIN:
 *
 * Env vars:
 *   VITE_OWNER_EMAIL     — default hienhd15411@gmail.com
 *   VITE_OWNER_PASSWORD  — nếu có → tự động signInWithPassword khi mount
 *   VITE_ALLOWED_EMAILS  — CSV; nếu không set, chỉ owner được vào
 *
 * Flow:
 *   1. getSession → nếu đã có session & email hợp lệ → render app
 *   2. Chưa có session + có VITE_OWNER_PASSWORD → auto signIn silent
 *   3. Session không hợp lệ (email ≠ whitelist) → signOut
 *   4. Chỉ hiện form login nếu auto-login fail hoặc không config password
 *
 * Session persist (Supabase client default) → login 1 lần, sống cho đến khi
 * refresh token hết hạn (default 60 ngày). Supabase auto-refresh nếu còn active.
 */
const DEFAULT_OWNER_EMAIL = "hienhd15411@gmail.com";

const OWNER_EMAIL = (
  (import.meta.env.VITE_OWNER_EMAIL as string | undefined)?.trim().toLowerCase() ||
  DEFAULT_OWNER_EMAIL
);
const OWNER_PASSWORD = (import.meta.env.VITE_OWNER_PASSWORD as string | undefined) ?? "";

const ALLOWED_EMAILS: Set<string> = (() => {
  const raw = (import.meta.env.VITE_ALLOWED_EMAILS as string | undefined) ?? "";
  const list = raw.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  if (list.length === 0) list.push(OWNER_EMAIL);
  return new Set(list);
})();

function isAllowed(email: string): boolean {
  return ALLOWED_EMAILS.has(email.trim().toLowerCase());
}

export function AuthGate({ children }: { children: (session: Session) => ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoTried, setAutoTried] = useState(false);
  const [recovery, setRecovery] = useState(false);
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  // Mount: watch session + try auto-login
  useEffect(() => {
    const hash = window.location.hash;
    if (hash.includes("type=recovery")) {
      setRecovery(true);
    }

    (async () => {
      const { data } = await supabase.auth.getSession();
      setSession(data.session);

      // Auto-login nếu chưa có session + đã config password
      if (!data.session && OWNER_PASSWORD) {
        try {
          const { error } = await supabase.auth.signInWithPassword({
            email: OWNER_EMAIL,
            password: OWNER_PASSWORD,
          });
          if (error) setError(mapError(error.message));
        } catch (e) {
          setError((e as Error).message);
        }
      }
      setAutoTried(true);
      setLoading(false);
    })();

    const sub = supabase.auth.onAuthStateChange((event, s) => {
      setSession(s);
      if (event === "PASSWORD_RECOVERY") setRecovery(true);
    });
    return () => sub.data.subscription.unsubscribe();
  }, []);

  // Nếu session có nhưng email không trong whitelist → signOut
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

  async function handleManualLogin(e: React.FormEvent) {
    e.preventDefault();
    resetMsgs();
    if (!password) {
      setError("Nhập password.");
      return;
    }
    setBusy(true);
    const { error } = await supabase.auth.signInWithPassword({
      email: OWNER_EMAIL,
      password,
    });
    setBusy(false);
    if (error) setError(mapError(error.message));
    else setPassword("");
  }

  async function handleUpdatePassword(e: React.FormEvent) {
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
    setInfo("Đã đổi password. Reload trang để auto-login lại.");
  }

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--text-dim)" }}>
        Đang mở DA Tool…
      </div>
    );
  }

  // 1. Recovery flow — đặt password mới
  if (recovery) {
    return (
      <AuthCard title="Đổi password">
        <p className="muted" style={{ marginTop: 0 }}>
          Nhập password mới cho tài khoản {session?.user?.email || OWNER_EMAIL}.
        </p>
        <form onSubmit={handleUpdatePassword} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
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
      </AuthCard>
    );
  }

  // 2. Chưa login → fallback form (chỉ khi auto-login không có password hoặc fail)
  if (!session) {
    return (
      <AuthCard title="DA Tool">
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
          Private tool. Owner: {OWNER_EMAIL}
        </p>
        {OWNER_PASSWORD && autoTried && (
          <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
            Auto-login đã thử nhưng fail. Có thể do Supabase đang pause hoặc password env sai.
            Nhập password thủ công bên dưới hoặc wake Supabase project.
          </div>
        )}
        {!OWNER_PASSWORD && (
          <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
            Chưa set <code>VITE_OWNER_PASSWORD</code> ở Netlify → auto-login tắt.
            Nhập password thủ công hoặc set env var rồi redeploy.
          </div>
        )}
        <form onSubmit={handleManualLogin} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
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
          {error && <div className="error">{error}</div>}
          {info && <div className="success">{info}</div>}
        </form>
      </AuthCard>
    );
  }

  return <>{children(session)}</>;
}

function AuthCard({ title, children }: { title: string; children: ReactNode }) {
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
      <h2 style={{ marginTop: 0 }}>{title}</h2>
      {children}
    </div>
  );
}

function mapError(msg: string): string {
  const m = msg.toLowerCase();
  if (m.includes("invalid login credentials")) return "Password sai (hoặc chưa set đúng ở Netlify env var).";
  if (m.includes("email not confirmed")) return "Email chưa được confirm trong Supabase.";
  if (m.includes("rate limit")) return "Quá nhiều lần thử. Đợi 1 phút rồi thử lại.";
  if (m.includes("password should be")) return "Password quá ngắn (tối thiểu 6 ký tự).";
  if (m.includes("same as the old")) return "Password mới không được trùng password cũ.";
  if (m.includes("failed to fetch") || m.includes("fetch failed")) {
    return "Không kết nối được Supabase — project có thể đang pause. Vô dashboard → Restore project.";
  }
  return msg;
}
