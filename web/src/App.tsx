import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AuthGate } from "./components/AuthGate";
import { Header } from "./components/Header";
import { ExerciseList, type Exercise } from "./components/ExerciseList";
import { SqlEditor } from "./components/SqlEditor";
import { ResultTable } from "./components/ResultTable";
import { runSql, type RunSqlResult } from "./lib/runSql";
import { envError } from "./supabase";

const INITIAL_SQL = `-- Thử query mẫu
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
  const [selected, setSelected] = useState<Exercise | null>(null);
  const [sql, setSql] = useState(INITIAL_SQL);
  const [result, setResult] = useState<RunSqlResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    try {
      const r = await runSql(sql, selected?.exercise_id ?? null);
      setResult(r);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <Header email={email} />
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <ExerciseList
          selected={selected?.exercise_id ?? null}
          onSelect={(ex) => {
            setSelected(ex);
            if (ex) setSql(`-- ${ex.exercise_id}: ${ex.title}\n\n`);
          }}
        />
        <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          {selected && (
            <div
              style={{
                padding: "0.8rem 1.2rem",
                borderBottom: "1px solid var(--border)",
                maxHeight: "35%",
                overflowY: "auto",
                background: "var(--panel)",
              }}
            >
              <div style={{ fontWeight: 700, marginBottom: 4 }}>
                {selected.exercise_id} — {selected.title}{" "}
                <span className="muted">(Level {selected.level})</span>
              </div>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {selected.description_md}
              </ReactMarkdown>
            </div>
          )}
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
              {selected && (
                <span className="muted" style={{ fontSize: 12 }}>
                  → Log gắn với bài {selected.exercise_id}
                </span>
              )}
            </div>
            <div style={{ flex: 1, minHeight: 200 }}>
              <SqlEditor value={sql} onChange={setSql} onRun={run} />
            </div>
            <div
              style={{
                height: "40%",
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
    </div>
  );
}
