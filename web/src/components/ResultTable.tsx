import { useState } from "react";
import type { RunSqlResult } from "../lib/runSql";

type OkResult = Extract<RunSqlResult, { status: "ok" }>;

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
  const cols = Object.keys(result.rows[0]);

  async function copy(fmt: "tsv" | "csv" | "json" | "md") {
    const text =
      fmt === "json" ? toJson(result.rows)
      : fmt === "md"  ? toMarkdown(cols, result.rows)
      : toDelimited(cols, result.rows, fmt === "csv" ? "," : "\t");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(fmt);
      setTimeout(() => setCopied(null), 1800);
    } catch {
      // Fallback: tạo textarea tạm để copy (trường hợp clipboard API bị block)
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(fmt);
      setTimeout(() => setCopied(null), 1800);
    }
  }

  function download() {
    const csv = toDelimited(cols, result.rows, ",");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `query_result_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const btn = (fmt: "tsv" | "csv" | "json" | "md", label: string, title: string) => (
    <button
      key={fmt}
      className="secondary"
      onClick={() => copy(fmt)}
      title={title}
      style={{ fontSize: 11, padding: "2px 8px" }}
    >
      {copied === fmt ? "✓ Copied" : `📋 ${label}`}
    </button>
  );

  return (
    <div style={{ padding: 8 }}>
      <div style={{ marginBottom: 8, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <span className="success">✓ OK</span>
        <span className="muted">{result.row_count} dòng</span>
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
          {btn("tsv", "TSV", "Copy tab-separated — dán vào Excel / Google Sheets")}
          {btn("csv", "CSV", "Copy comma-separated")}
          {btn("md", "MD", "Copy Markdown table")}
          {btn("json", "JSON", "Copy JSON array")}
          <button
            className="secondary"
            onClick={download}
            title="Tải xuống file .csv"
            style={{ fontSize: 11, padding: "2px 8px" }}
          >
            ⬇ CSV
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
      <div style={{ overflowX: "auto", userSelect: "text" }}>
        <table className="result-table">
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, i) => (
              <tr key={i}>
                {cols.map((c) => (
                  <td key={c}>{formatCell(row[c])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
        💡 Kéo chuột để chọn ô → Ctrl+C paste vào Excel/Sheets (giữ đúng cột). Hoặc dùng nút 📋 TSV để copy toàn bộ.
      </div>
    </div>
  );
}

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "NULL";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

// --- Export formatters --------------------------------------------------

function cellForDelimited(v: unknown, delim: string): string {
  if (v === null || v === undefined) return "";
  const s = typeof v === "object" ? JSON.stringify(v) : String(v);
  // Quote nếu chứa delim, newline, hoặc dấu nháy kép. Escape `"` → `""`.
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

function toJson(rows: Record<string, unknown>[]): string {
  return JSON.stringify(rows, null, 2);
}

function toMarkdown(cols: string[], rows: Record<string, unknown>[]): string {
  const esc = (v: unknown) => {
    if (v === null || v === undefined) return "";
    const s = typeof v === "object" ? JSON.stringify(v) : String(v);
    return s.replace(/\|/g, "\\|").replace(/\n/g, " ");
  };
  const header = "| " + cols.join(" | ") + " |";
  const sep    = "| " + cols.map(() => "---").join(" | ") + " |";
  const body   = rows.map((r) => "| " + cols.map((c) => esc(r[c])).join(" | ") + " |").join("\n");
  return [header, sep, body].join("\n");
}
