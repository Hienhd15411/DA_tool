import { useEffect, useRef, useState } from "react";
import type { editor } from "monaco-editor";
import { AuthGate } from "./components/AuthGate";
import { Header } from "./components/Header";
import { SchemaBrowser } from "./components/SchemaBrowser";
import { SqlEditor } from "./components/SqlEditor";
import { ResultTable } from "./components/ResultTable";
import { TabBar, type QueryTab } from "./components/TabBar";
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

const TABS_STORAGE_KEY = "datool.tabs.v1";

type StoredState = { tabs: QueryTab[]; activeId: string };

function uuid(): string {
  // crypto.randomUUID không có trên 1 số webview cũ → fallback.
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function loadState(): StoredState {
  try {
    const raw = localStorage.getItem(TABS_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as StoredState;
      if (parsed?.tabs?.length) return parsed;
    }
  } catch {
    /* ignore */
  }
  const initial: QueryTab = { id: uuid(), title: "Query 1", sql: INITIAL_SQL };
  return { tabs: [initial], activeId: initial.id };
}

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
  const initial = loadState();
  const [tabs, setTabs] = useState<QueryTab[]>(initial.tabs);
  const [activeId, setActiveId] = useState<string>(initial.activeId);
  // Result per-tab, không persist (sau reload là query lại)
  const [results, setResults] = useState<Record<string, RunSqlResult | null>>({});
  const [loadingTabId, setLoadingTabId] = useState<string | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  const active = tabs.find((t) => t.id === activeId) ?? tabs[0];
  const activeResult = results[active.id] ?? null;
  const loading = loadingTabId === active.id;

  // Persist tabs + activeId (không persist result)
  useEffect(() => {
    try {
      localStorage.setItem(TABS_STORAGE_KEY, JSON.stringify({ tabs, activeId } satisfies StoredState));
    } catch {
      /* quota / private mode */
    }
  }, [tabs, activeId]);

  function setActiveSql(next: string) {
    setTabs((ts) => ts.map((t) => (t.id === activeId ? { ...t, sql: next } : t)));
  }

  async function run() {
    const tabId = active.id;
    // Nếu user bôi đen (select) một đoạn trong editor → chỉ chạy đoạn đó,
    // giống Supabase/DBeaver. Không có selection → chạy toàn bộ tab.
    const ed = editorRef.current;
    let sql = active.sql;
    if (ed) {
      const sel = ed.getSelection();
      const model = ed.getModel();
      if (sel && !sel.isEmpty() && model) {
        const picked = model.getValueInRange(sel);
        if (picked.trim()) sql = picked;
      }
    }
    setLoadingTabId(tabId);
    try {
      const r = await runSql(sql, null);
      setResults((prev) => ({ ...prev, [tabId]: r }));
    } finally {
      setLoadingTabId((cur) => (cur === tabId ? null : cur));
    }
  }

  function addTab() {
    const n = tabs.length + 1;
    const t: QueryTab = { id: uuid(), title: `Query ${n}`, sql: "" };
    setTabs((ts) => [...ts, t]);
    setActiveId(t.id);
  }

  function closeTab(id: string) {
    if (tabs.length <= 1) return;
    const idx = tabs.findIndex((t) => t.id === id);
    const next = tabs.filter((t) => t.id !== id);
    setTabs(next);
    setResults((prev) => {
      const { [id]: _gone, ...rest } = prev;
      return rest;
    });
    if (id === activeId) setActiveId(next[Math.max(0, idx - 1)].id);
  }

  function renameTab(id: string, title: string) {
    setTabs((ts) => ts.map((t) => (t.id === id ? { ...t, title } : t)));
  }

  function clearActive() {
    setActiveSql("");
    setResults((prev) => ({ ...prev, [active.id]: null }));
  }

  function insertAtCursor(text: string) {
    const ed = editorRef.current;
    if (!ed) {
      setActiveSql(active.sql + text);
      return;
    }
    const sel = ed.getSelection();
    if (!sel) return;
    ed.executeEdits("insert", [{ range: sel, text, forceMoveMarkers: true }]);
    ed.focus();
  }

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <Header email={email} />
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <SchemaBrowser onInsert={insertAtCursor} />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <TabBar
            tabs={tabs}
            activeId={active.id}
            onSelect={setActiveId}
            onClose={closeTab}
            onAdd={addTab}
            onRename={renameTab}
          />
          <div
            style={{
              display: "flex",
              padding: "0.5rem 1rem",
              gap: 12,
              alignItems: "center",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <button onClick={run} disabled={loading}>
              {loading ? "Đang chạy…" : "▶ Chạy (Ctrl+Enter)"}
            </button>
            <button className="secondary" onClick={clearActive}>
              Xoá
            </button>
            <span className="muted" style={{ fontSize: 12, marginLeft: "auto" }}>
              Schema: <code>shopee</code> · read-only · timeout 5s · max 500 rows / 2 MB · bôi đen để chạy 1 đoạn
            </span>
          </div>
          <div style={{ flex: 1, minHeight: 200 }}>
            <SqlEditor
              value={active.sql}
              onChange={setActiveSql}
              onRun={run}
              onReady={(ed) => (editorRef.current = ed)}
            />
          </div>
          <div
            style={{
              height: "45%",
              overflow: "auto",
              borderTop: "1px solid var(--border)",
              background: "var(--panel)",
            }}
          >
            <ResultTable result={activeResult} loading={loading} />
          </div>
        </div>
      </div>
    </div>
  );
}
