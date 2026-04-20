import type { RunSqlResult } from "../lib/runSql";

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

  const cols = Object.keys(result.rows[0]);

  return (
    <div style={{ padding: 8 }}>
      <div style={{ marginBottom: 8, display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
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
      <div style={{ overflowX: "auto" }}>
        <table>
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
    </div>
  );
}

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "NULL";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
