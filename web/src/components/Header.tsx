import { supabase } from "../supabase";

export function Header({ email }: { email: string | undefined }) {
  async function signOut() {
    await supabase.auth.signOut();
  }
  return (
    <header
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "0.6rem 1.2rem",
        borderBottom: "1px solid var(--border)",
        background: "var(--panel)",
      }}
    >
      <div style={{ fontWeight: 700 }}>DA Tool — SQL học qua Shopee case study</div>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <span className="muted">{email}</span>
        <button className="secondary" onClick={signOut}>
          Đăng xuất
        </button>
      </div>
    </header>
  );
}
