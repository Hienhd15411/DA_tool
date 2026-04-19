import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "../supabase";

export function AuthGate({ children }: { children: (session: Session) => React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);

  async function signIn(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.origin },
    });
    if (error) setError(error.message);
    else setSent(true);
  }

  if (loading) return <div style={{ padding: 40 }}>Loading…</div>;

  if (!session) {
    return (
      <div style={{ maxWidth: 380, margin: "10vh auto", padding: 24, background: "var(--panel)", borderRadius: 8 }}>
        <h2>DA Tool — Đăng nhập</h2>
        <p className="muted">
          Nhập email để nhận magic link. Không cần password.
        </p>
        {sent ? (
          <p className="success">
            ✉️ Đã gửi email. Check inbox rồi click link để đăng nhập.
          </p>
        ) : (
          <form onSubmit={signIn} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ban@example.com"
            />
            <button type="submit">Gửi magic link</button>
            {error && <div className="error">{error}</div>}
          </form>
        )}
      </div>
    );
  }

  return <>{children(session)}</>;
}
