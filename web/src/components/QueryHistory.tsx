import { useEffect, useState } from "react";
import { clearHistory, loadHistory, type HistoryEntry } from "../lib/queryHistory";

export function QueryHistory({
  onPickSql,
  onClose,
}: {
  onPickSql: (sql: string) => void;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<HistoryEntry[]>(loadHistory());
  const [filter, setFilter] = useState("");

  useEffect(() => {
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onEsc);
    return () => document.removeEventListener("keydown", onEsc);
  }, [onClose]);

  const filtered = rows.filter((r) =>
    !filter.trim() || r.sql.toLowerCase().includes(filter.toLowerCase()),
  );

  function reload() {
    setRows(loadHistory());
  }

  function clearAll() {
    if (!confirm("Xoá toàn bộ history? (chỉ local, không đụng query_log trên server)")) return;
    clearHistory();
    reload();
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.6)",
        zIndex: 45,
        display: "flex",
        justifyContent: "flex-end",
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(600px, 90vw)",
          height: "100vh",
          background: "var(--bg)",
          borderLeft: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            padding: "10px 14px",
            background: "var(--panel)",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 700 }}>🕑 Query history <span className="muted" style={{ fontSize: 11 }}>({rows.length} / 50)</span></div>
          <button className="secondary" onClick={onClose} style={{ padding: "3px 10px", fontSize: 12 }}>✕</button>
        </div>
        <div style={{ padding: "8px 14px", display: "flex", gap: 8, borderBottom: "1px solid var(--border)" }}>
          <input
            placeholder="Tìm trong SQL…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            style={{ flex: 1, fontSize: 12, padding: "4px 8px" }}
          />
          <button className="secondary" onClick={reload} style={{ padding: "4px 10px", fontSize: 12 }} title="Reload từ localStorage">
            🔄
          </button>
          <button className="secondary" onClick={clearAll} style={{ padding: "4px 10px", fontSize: 12 }} title="Xoá toàn bộ">
            🗑
          </button>
        </div>
        <div style={{ flex: 1, overflowY: "auto" }}>
          {rows.length === 0 && (
            <div className="muted" style={{ padding: 16, textAlign: "center" }}>
              Chưa có query nào. Chạy query để log.
            </div>
          )}
          {filtered.length === 0 && rows.length > 0 && (
            <div className="muted" style={{ padding: 16, textAlign: "center" }}>
              Không có query match filter.
            </div>
          )}
          {filtered.map((r) => (
            <div
              key={r.id}
              style={{
                padding: "8px 14px",
                borderBottom: "1px solid var(--border)",
                cursor: "pointer",
              }}
              onClick={() => {
                onPickSql(r.sql);
                onClose();
              }}
              title="Click để load vào tab hiện tại"
            >
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 3 }}>
                <span className="muted">{fmtTime(r.ran_at)}</span>
                <span style={{ color: r.status === "ok" ? "var(--success)" : "var(--error)" }}>
                  {r.status}
                  {r.exec_ms !== undefined && ` · ${r.exec_ms}ms`}
                  {r.row_count !== undefined && ` · ${r.row_count} rows`}
                  {r.error_code && ` · ${r.error_code}`}
                </span>
              </div>
              <pre
                style={{
                  margin: 0,
                  background: "var(--panel)",
                  padding: 6,
                  fontSize: 11,
                  maxHeight: 80,
                  overflow: "hidden",
                  whiteSpace: "pre-wrap",
                  fontFamily: "ui-monospace, monospace",
                }}
              >
                {r.sql.slice(0, 300)}
                {r.sql.length > 300 && "…"}
              </pre>
            </div>
          ))}
        </div>
        <div className="muted" style={{ padding: "6px 14px", fontSize: 11, borderTop: "1px solid var(--border)" }}>
          💡 Lưu local trong browser. Đổi máy / clear cache = mất. Giáo viên xem query_log server ở 👨‍🏫 Teacher.
        </div>
      </div>
    </div>
  );
}

function fmtTime(s: string): string {
  const d = new Date(s);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  if (diffMs < 60_000) return `${Math.max(1, Math.floor(diffMs / 1000))}s trước`;
  if (diffMs < 3600_000) return `${Math.floor(diffMs / 60_000)}m trước`;
  if (diffMs < 86_400_000) return `${Math.floor(diffMs / 3600_000)}h trước`;
  return d.toLocaleString("en-GB", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}
