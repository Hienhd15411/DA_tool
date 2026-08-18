import { supabase } from "../supabase";

export function Header({
  email,
  isTeacher,
  onOpenTeacher,
  onOpenHistory,
}: {
  email: string | undefined;
  isTeacher: boolean;
  onOpenTeacher: () => void;
  onOpenHistory: () => void;
}) {
  async function signOut() {
    await supabase.auth.signOut();
  }
  return (
    <header
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "0.5rem 1.2rem",
        borderBottom: "1px solid var(--border)",
        background: "var(--panel)",
      }}
    >
      <div style={{ fontWeight: 700 }}>DA Tool — SQL học qua Shopee case study</div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button
          className="secondary"
          onClick={onOpenHistory}
          title="Lịch sử query (50 câu gần nhất)"
          style={{ fontSize: 12, padding: "4px 10px" }}
        >
          🕑 History
        </button>
        {isTeacher && (
          <button
            onClick={onOpenTeacher}
            title="Teacher dashboard: xem query_log của học viên"
            style={{ fontSize: 12, padding: "4px 10px" }}
          >
            👨‍🏫 Teacher
          </button>
        )}
        <span className="muted" style={{ fontSize: 12 }}>{email}</span>
        <button className="secondary" onClick={signOut} style={{ fontSize: 12, padding: "4px 10px" }}>
          Đăng xuất
        </button>
      </div>
    </header>
  );
}
