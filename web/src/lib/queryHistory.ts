// LocalStorage-backed query history. Max 50 entries per user session.
// Nội dung: {sql, ran_at, status, exec_ms, row_count, error_code}

const KEY = "datool.history.v1";
const MAX = 50;

export type HistoryEntry = {
  id: string;
  sql: string;
  ran_at: string;       // ISO
  status: "ok" | "error";
  exec_ms?: number;
  row_count?: number;
  error_code?: string;
};

export function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as HistoryEntry[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function pushHistory(entry: Omit<HistoryEntry, "id" | "ran_at">): HistoryEntry[] {
  const id =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);
  const row: HistoryEntry = { ...entry, id, ran_at: new Date().toISOString() };
  const cur = loadHistory();
  // De-dupe: nếu SQL + status trùng entry mới nhất → skip (tránh spam Ctrl+Enter)
  if (cur.length > 0 && cur[0].sql === row.sql && cur[0].status === row.status) {
    return cur;
  }
  const next = [row, ...cur].slice(0, MAX);
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch {/* quota */}
  return next;
}

export function clearHistory(): void {
  try { localStorage.removeItem(KEY); } catch {/* ignore */}
}
