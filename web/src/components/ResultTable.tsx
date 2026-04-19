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
      <div style={{ marginBottom: 8, display: "flex", gap: 16 }}>
        <span className="success">✓ OK</span>
        <span className="muted">{result.row_count} dòng</span>
        <span className="muted">{result.exec_ms} ms</span>
        {result.truncated && (
          <span className="muted" style={{ color: "var(--accent)" }}>
            (đã cắt ở 500 dòng — thêm LIMIT để xem đủ)
          </span>
        )}
      </div>
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
