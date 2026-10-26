import { useEffect, useState, type ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "../supabase";

/**
 * Single-user mode, zero-friction auth:
 *   1. Lần đầu: user gõ password 1 lần → store vào localStorage
 *   2. Lần sau: auto signIn silent → ko hiện form
 *   3. Login invalid → clear localStorage + show form lại
 *
 * Env vars (optional):
 *   VITE_OWNER_EMAIL     — default hienhd15411@gmail.com
 *   VITE_OWNER_PASSWORD  — nếu set, override localStorage (dùng cho deployment mới)
 *   VITE_ALLOWED_EMAILS  — CSV; default chỉ owner
 */
const DEFAULT_OWNER_EMAIL = "hienhd15411@gmail.com";
const REMEMBER_KEY = "datool.auth.pw";

const OWNER_EMAIL = (
  (import.meta.env.VITE_OWNER_EMAIL as string | undefined)?.trim().toLowerCase() ||
  DEFAULT_OWNER_EMAIL
);
const ENV_PASSWORD = (import.meta.env.VITE_OWNER_PASSWORD as string | undefined) ?? "";

const ALLOWED_EMAILS: Set<string> = (() => {
  const raw = (import.meta.env.VITE_ALLOWED_EMAILS as string | undefined) ?? "";
  const list = raw.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  if (list.length === 0) list.push(OWNER_EMAIL);
  return new Set(list);
})();

function isAllowed(email: string): boolean {
  return ALLOWED_EMAILS.has(email.trim().toLowerCase());
}

function readRemembered(): string {
  try {
    return localStorage.getItem(REMEMBER_KEY) ?? "";
  } catch {
    return "";
  }
}
function writeRemembered(pw: string) {
  try {
    localStorage.setItem(REMEMBER_KEY, pw);
  } catch { /* quota */ }
}
function clearRemembered() {
  try {
    localStorage.removeItem(REMEMBER_KEY);
  } catch { /* ignore */ }
}

export function AuthGate({ children }: { children: (session: Session) => ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [recovery, setRecovery] = useState(false);
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  // Mount: watch session + try auto-login từ env hoặc localStorage
  useEffect(() => {
    const hash = window.location.hash;
    if (hash.includes("type=recovery")) {
      setRecovery(true);
    }

    (async () => {
      const { data } = await supabase.auth.getSession();
      setSession(data.session);

      // Auto-login nếu chưa có session + đã có pw (env ưu tiên, fallback localStorage)
      const autoPw = ENV_PASSWORD || readRemembered();
      if (!data.session && autoPw) {
        try {
          const { error } = await supabase.auth.signInWithPassword({
            email: OWNER_EMAIL,
            password: autoPw,
          });
          if (error) {
            // Stored pw sai (bị thay đổi) → clear để user gõ lại
            if (!ENV_PASSWORD && error.message.toLowerCase().includes("invalid")) {
              clearRemembered();
            }
          }
        } catch { /* network err — fall through to form */ }
      }
      setLoading(false);
    })();

    const sub = supabase.auth.onAuthStateChange((event, s) => {
      setSession(s);
      if (event === "PASSWORD_RECOVERY") setRecovery(true);
    });
    return () => sub.data.subscription.unsubscribe();
  }, []);

  // Session có nhưng email không trong whitelist → signOut
  useEffect(() => {
    if (session && session.user?.email && !isAllowed(session.user.email)) {
      supabase.auth.signOut();
      clearRemembered();
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
    if (error) {
      setError(mapError(error.message));
      return;
    }
    // Login OK → nhớ password cho lần sau
    writeRemembered(password);
    setPassword("");
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
    // Cập nhật localStorage với password mới → lần sau auto-login luôn
    writeRemembered(password);
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    setRecovery(false);
    setPassword("");
    setPassword2("");
    setInfo("Đã đổi password. Session hiện tại giữ nguyên.");
  }

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--text-dim)" }}>
        Đang mở DA Tool…
      </div>
    );
  }

  // 1. Recovery flow
  if (recovery) {
    return (
      <AuthCard title="Đổi password">
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

  // 2. Chưa login → form đơn giản
  if (!session) {
    return (
      <AuthCard title="DA Tool">
        <form onSubmit={handleManualLogin} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <input
            type="password"
            required
            autoFocus
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
          />
          <button type="submit" disabled={busy}>
            {busy ? "Đang xử lý…" : "Đăng nhập"}
          </button>
          <div className="muted" style={{ fontSize: 11, textAlign: "center" }}>
            {OWNER_EMAIL} · password sẽ được nhớ cho lần sau
          </div>
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
        maxWidth: 360,
        margin: "15vh auto",
        padding: 24,
        background: "var(--panel)",
        borderRadius: 8,
      }}
    >
      <h2 style={{ marginTop: 0, textAlign: "center" }}>{title}</h2>
      {children}
    </div>
  );
}

function mapError(msg: string): string {
  const m = msg.toLowerCase();
  if (m.includes("invalid login credentials")) return "Password sai.";
  if (m.includes("email not confirmed")) return "Email chưa được confirm trong Supabase.";
  if (m.includes("rate limit")) return "Quá nhiều lần thử. Đợi 1 phút rồi thử lại.";
  if (m.includes("password should be")) return "Password quá ngắn (tối thiểu 6 ký tự).";
  if (m.includes("same as the old")) return "Password mới không được trùng password cũ.";
  if (m.includes("failed to fetch") || m.includes("fetch failed")) {
    return "Không kết nối được Supabase — có thể project đang pause. Vô dashboard → Restore project.";
  }
  return msg;
}
