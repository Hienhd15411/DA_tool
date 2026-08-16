import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "../supabase";

type Mode = "login" | "signup";

export function AuthGate({ children }: { children: (session: Session) => ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);

  function resetMsgs() {
    setError(null);
    setInfo(null);
  }

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    resetMsgs();
    setBusy(true);
    const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
    setBusy(false);
    if (error) setError(mapError(error.message));
  }

  async function handleSignup(e: FormEvent) {
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
    const { data, error } = await supabase.auth.signUp({
      email: email.trim(),
      password,
    });
    setBusy(false);
    if (error) {
      setError(mapError(error.message));
      return;
    }
    if (data.session) {
      // Auto-confirm ON — login luôn
      return;
    }
    // Auto-confirm OFF ở Supabase → cần verify email
    setInfo("Đã tạo tài khoản. Check email để confirm rồi quay lại đăng nhập.");
    setMode("login");
    setPassword("");
    setPassword2("");
  }

  async function handleForgot() {
    resetMsgs();
    if (!email.trim()) {
      setError("Nhập email trước rồi click 'Quên password'.");
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

  if (loading) return <div style={{ padding: 40 }}>Loading…</div>;

  if (!session) {
    const isLogin = mode === "login";
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
        <h2 style={{ marginTop: 0 }}>DA Tool</h2>
        <div style={{ display: "flex", gap: 4, marginBottom: 16 }}>
          <button
            type="button"
            onClick={() => {
              setMode("login");
              resetMsgs();
            }}
            style={tabStyle(isLogin)}
          >
            Đăng nhập
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("signup");
              resetMsgs();
            }}
            style={tabStyle(!isLogin)}
          >
            Đăng ký
          </button>
        </div>

        <form
          onSubmit={isLogin ? handleLogin : handleSignup}
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
            autoComplete={isLogin ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={isLogin ? "Password" : "Password (tối thiểu 6 ký tự)"}
          />
          {!isLogin && (
            <input
              type="password"
              required
              autoComplete="new-password"
              value={password2}
              onChange={(e) => setPassword2(e.target.value)}
              placeholder="Nhập lại password"
            />
          )}
          <button type="submit" disabled={busy}>
            {busy ? "Đang xử lý…" : isLogin ? "Đăng nhập" : "Tạo tài khoản"}
          </button>
          {isLogin && (
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
          )}
          {error && <div className="error">{error}</div>}
          {info && <div className="success">{info}</div>}
        </form>
      </div>
    );
  }

  return <>{children(session)}</>;
}

function tabStyle(active: boolean): React.CSSProperties {
  return {
    flex: 1,
    padding: "8px 12px",
    background: active ? "var(--accent)" : "transparent",
    color: active ? "#fff" : "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 4,
    cursor: "pointer",
    fontWeight: active ? 600 : 400,
  };
}

function mapError(msg: string): string {
  const m = msg.toLowerCase();
  if (m.includes("invalid login credentials")) return "Email hoặc password sai.";
  if (m.includes("email not confirmed")) return "Email chưa được confirm. Check inbox.";
  if (m.includes("user already registered")) return "Email này đã đăng ký. Chuyển sang tab Đăng nhập.";
  if (m.includes("rate limit")) return "Quá nhiều lần thử. Đợi 1 phút rồi thử lại.";
  if (m.includes("password should be")) return "Password quá ngắn (tối thiểu 6 ký tự).";
  return msg;
}
