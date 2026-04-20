import { useRef, useState } from "react";
import type { editor } from "monaco-editor";
import { AuthGate } from "./components/AuthGate";
import { Header } from "./components/Header";
import { SchemaBrowser } from "./components/SchemaBrowser";
import { SqlEditor } from "./components/SqlEditor";
import { ResultTable } from "./components/ResultTable";
import { runSql, type RunSqlResult } from "./lib/runSql";
import { envError } from "./supabase";

const INITIAL_SQL = `-- Query mẫu: GMV theo tuần 3 tháng qua
SELECT
  DATE_TRUNC('week', d.full_date)::date AS week_start,
  SUM(o.total_amount) AS gmv,
  COUNT(*)            AS orders
FROM shopee.fact_orders o
JOIN shopee.dim_date    d ON d.date_key = o.order_date_key
WHERE o.payment_status = 'paid'
GROUP BY 1
ORDER BY 1;`;

export default function App() {
  if (envError) {
    return (
      <div style={{ maxWidth: 520, margin: "10vh auto", padding: 24, background: "var(--panel)", borderRadius: 8 }}>
        <h2 className="error">⚠️ Config chưa sẵn sàng</h2>
        <p>{envError}</p>
        <p className="muted">
          Sau khi set env vars, vào Netlify → <b>Deploys</b> → <b>Trigger deploy</b> → <b>Clear cache and deploy site</b>.
        </p>
      </div>
    );
  }
  return (
    <AuthGate>
      {(session) => <Workbench email={session.user.email} />}
    </AuthGate>
  );
}

function Workbench({ email }: { email: string | undefined }) {
  const [sql, setSql] = useState(INITIAL_SQL);
  const [result, setResult] = useState<RunSqlResult | null>(null);
  const [loading, setLoading] = useState(false);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  async function run() {
    setLoading(true);
    try {
      const r = await runSql(sql, null);
      setResult(r);
    } finally {
      setLoading(false);
    }
  }

  function insertAtCursor(text: string) {
    const ed = editorRef.current;
    if (!ed) {
      setSql((prev) => prev + text);
      return;
    }
    const sel = ed.getSelection();
    if (!sel) return;
    ed.executeEdits("insert", [
      { range: sel, text, forceMoveMarkers: true },
    ]);
    ed.focus();
  }

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <Header email={email} />
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <SchemaBrowser onInsert={insertAtCursor} />
        <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", padding: "0.5rem 1rem", gap: 12, alignItems: "center", borderBottom: "1px solid var(--border)" }}>
            <button onClick={run} disabled={loading}>
              {loading ? "Đang chạy…" : "▶ Chạy (Ctrl+Enter)"}
            </button>
            <button
              className="secondary"
              onClick={() => {
                setSql("");
                setResult(null);
              }}
            >
              Xoá
            </button>
            <span className="muted" style={{ fontSize: 12, marginLeft: "auto" }}>
              Schema: <code>shopee</code> · read-only · timeout 5s · max 500 rows / 2 MB
            </span>
          </div>
          <div style={{ flex: 1, minHeight: 200 }}>
            <SqlEditor value={sql} onChange={setSql} onRun={run} onReady={(ed) => (editorRef.current = ed)} />
          </div>
          <div
            style={{
              height: "45%",
              overflow: "auto",
              borderTop: "1px solid var(--border)",
              background: "var(--panel)",
            }}
          >
            <ResultTable result={result} loading={loading} />
          </div>
        </div>
      </div>
    </div>
  );
}
