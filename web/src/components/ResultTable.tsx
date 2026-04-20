import { useMemo, useState } from "react";
import type { RunSqlResult } from "../lib/runSql";

type OkResult = Extract<RunSqlResult, { status: "ok" }>;
type SortState = { col: string; dir: "asc" | "desc" } | null;

export function ResultTable({ result, loading }: { result: RunSqlResult | null; loading: boolean }) {
  if (loading) return <div style={{ padding: 12 }} className="muted">Đang chạy…</div>;
  if (!result) return <div style={{ padding: 12 }} className="muted">Kết quả hiển thị ở đây.</div>;

  if (result.status === "error") {
    return (
      <div style={{ padding: 12 }}>
        <div className="error" style={{ fontWeight: 600 }}>
          ❌ Lỗi ({result.error_code})
        </div>
        <pre style={{ whiteSpace: "pre-wrap", color: "var(--error)" }}>{result.error_message}</pre>
        <div className="muted">Đã ghi vào query_log. Sửa query rồi chạy lại.</div>
      </div>
    );
  }

  if (result.row_count === 0) {
    return (
      <div style={{ padding: 12 }}>
        <div className="success">✓ Query OK ({result.exec_ms} ms)</div>
        <div className="muted">Không có dòng nào trả về.</div>
      </div>
    );
  }

  return <OkTable result={result} />;
}

function OkTable({ result }: { result: OkResult }) {
  const [copied, setCopied] = useState<string | null>(null);
  const [sort, setSort] = useState<SortState>(null);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const cols = Object.keys(result.rows[0]);

  const processed = useMemo(() => {
    let rows = result.rows;
    // filter
    const activeFilters = Object.entries(filters).filter(([, q]) => q.trim());
    if (activeFilters.length > 0) {
      rows = rows.filter((r) =>
        activeFilters.every(([col, q]) => {
          const v = r[col];
          const s = v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);
          return s.toLowerCase().includes(q.toLowerCase());
        }),
      );
    }
    // sort
    if (sort) {
      rows = [...rows].sort((a, b) => {
        const va = a[sort.col], vb = b[sort.col];
        if (va === vb) return 0;
        if (va === null || va === undefined) return 1;
        if (vb === null || vb === undefined) return -1;
        let cmp: number;
        if (typeof va === "number" && typeof vb === "number") cmp = va - vb;
        else cmp = String(va).localeCompare(String(vb), undefined, { numeric: true });
        return sort.dir === "asc" ? cmp : -cmp;
      });
    }
    return rows;
  }, [result.rows, filters, sort]);

  function toggleSort(col: string) {
    setSort((s) => {
      if (!s || s.col !== col) return { col, dir: "asc" };
      if (s.dir === "asc") return { col, dir: "desc" };
      return null; // 3rd click clears sort
    });
  }

  function setFilter(col: string, q: string) {
    setFilters((prev) => ({ ...prev, [col]: q }));
  }

  async function writeClipboard(text: string, key: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(key);
    setTimeout(() => setCopied((c) => (c === key ? null : c)), 1600);
  }

  function copyAll() {
    writeClipboard(toDelimited(cols, processed, "\t"), "all");
  }

  function download() {
    const csv = toDelimited(cols, processed, ",");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `query_result_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function copyCell(v: unknown, cellKey: string) {
    const s = v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);
    writeClipboard(s, cellKey);
  }

  const filteredNote =
    processed.length !== result.rows.length
      ? ` (lọc ${processed.length}/${result.rows.length})`
      : "";

  return (
    <div style={{ padding: 8 }}>
      <div style={{ marginBottom: 8, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <span className="success">✓ OK</span>
        <span className="muted">
          {result.row_count} dòng{filteredNote}
        </span>
        <span className="muted">{result.exec_ms} ms</span>
        {result.truncated && (
          <span
            style={{
              background: "var(--accent-dim)",
              color: "#fff",
              padding: "2px 8px",
              borderRadius: 4,
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            ⚠️ Đã cắt tại {result.row_count}/{result.max_rows} dòng
          </span>
        )}
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          <button
            className="secondary"
            onClick={copyAll}
            title="Copy toàn bộ kết quả (TSV — paste vào Excel/Sheets)"
            style={{ fontSize: 12, padding: "3px 10px" }}
          >
            {copied === "all" ? "✓ Copied" : "📋 Copy all"}
          </button>
          <button
            className="secondary"
            onClick={download}
            title="Download file CSV"
            style={{ fontSize: 12, padding: "3px 10px" }}
          >
            ⬇ Download CSV
          </button>
        </div>
      </div>
      {result.notice && (
        <div
          style={{
            marginBottom: 8,
            padding: "8px 12px",
            background: "rgba(249, 115, 22, 0.1)",
            border: "1px solid var(--accent)",
            borderRadius: 4,
            fontSize: 12,
            color: "var(--accent)",
          }}
        >
          💡 {result.notice}
        </div>
      )}
      <div style={{ overflow: "auto", maxHeight: "calc(100% - 40px)" }}>
        <table className="result-table" style={{ width: "100%" }}>
          <thead style={{ position: "sticky", top: 0, zIndex: 2 }}>
            <tr>
              {cols.map((c) => {
                const s = sort?.col === c ? sort.dir : null;
                return (
                  <th
                    key={c}
                    onClick={() => toggleSort(c)}
                    style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap" }}
                    title="Click để sort · click lại để đảo chiều · click lần 3 để bỏ sort"
                  >
                    {c}
                    {s === "asc" && <span style={{ color: "var(--accent)" }}> ▲</span>}
                    {s === "desc" && <span style={{ color: "var(--accent)" }}> ▼</span>}
                  </th>
                );
              })}
            </tr>
            <tr>
              {cols.map((c) => (
                <th key={c} style={{ padding: "2px 4px", background: "var(--panel)" }}>
                  <input
                    placeholder="Filter…"
                    value={filters[c] ?? ""}
                    onChange={(e) => setFilter(c, e.target.value)}
                    style={{ width: "100%", fontSize: 11, padding: "2px 4px" }}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {processed.map((row, i) => (
              <tr key={i}>
                {cols.map((c) => {
                  const key = `${i}-${c}`;
                  return (
                    <td
                      key={c}
                      onClick={() => copyCell(row[c], key)}
                      title="Click để copy giá trị ô này"
                      style={{
                        cursor: "cell",
                        background: copied === key ? "var(--accent-dim)" : undefined,
                        color: copied === key ? "#fff" : undefined,
                        transition: "background 0.15s",
                      }}
                    >
                      {formatCell(row[c])}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {processed.length === 0 && (
          <div className="muted" style={{ padding: 12, textAlign: "center" }}>
            Filter không match dòng nào — clear filter để xem lại.
          </div>
        )}
      </div>
      <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
        💡 Click cell để copy giá trị · click header để sort · dùng ô filter để lọc · kéo chuột để chọn vùng
      </div>
    </div>
  );
}

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "NULL";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function cellForDelimited(v: unknown, delim: string): string {
  if (v === null || v === undefined) return "";
  const s = typeof v === "object" ? JSON.stringify(v) : String(v);
  if (s.includes(delim) || s.includes("\n") || s.includes("\r") || s.includes('"')) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function toDelimited(cols: string[], rows: Record<string, unknown>[], delim: string): string {
  const header = cols.map((c) => cellForDelimited(c, delim)).join(delim);
  const body = rows.map((r) => cols.map((c) => cellForDelimited(r[c], delim)).join(delim)).join("\n");
  return header + "\n" + body;
}
