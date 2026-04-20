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
    DATE_TRUNC('week', d.full_date)::date AS week_start
  , SUM(o.total_amount)                   AS gmv
  , COUNT(*)                              AS orders
FROM shopee.fact_orders o
JOIN shopee.dim_date d ON d.date_key = o.order_date_key
WHERE o.payment_status = 'paid'
GROUP BY 1
ORDER BY 1`;

const TABS_STORAGE_KEY = "datool.tabs.v1";
const COLLAPSE_KEY = "datool.schema.collapsed";

type StoredState = { tabs: QueryTab[]; activeId: string };

function uuid(): string {
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
  const [results, setResults] = useState<Record<string, RunSqlResult | null>>({});
  const [loadingTabId, setLoadingTabId] = useState<string | null>(null);
  const [schemaCollapsed, setSchemaCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem(COLLAPSE_KEY) === "1"; } catch { return false; }
  });
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  const active = tabs.find((t) => t.id === activeId) ?? tabs[0];
  const activeResult = results[active.id] ?? null;
  const loading = loadingTabId === active.id;

  useEffect(() => {
    try {
      localStorage.setItem(TABS_STORAGE_KEY, JSON.stringify({ tabs, activeId } satisfies StoredState));
    } catch {/* quota */}
  }, [tabs, activeId]);

  useEffect(() => {
    try { localStorage.setItem(COLLAPSE_KEY, schemaCollapsed ? "1" : "0"); } catch {/* quota */}
  }, [schemaCollapsed]);

  function setActiveSql(next: string) {
    setTabs((ts) => ts.map((t) => (t.id === activeId ? { ...t, sql: next } : t)));
  }

  async function run() {
    const tabId = active.id;
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

  async function formatActive() {
    try {
      // Lazy load sql-formatter (~80KB gzipped) — chỉ tải khi user bấm lần đầu
      const { format } = await import("sql-formatter");
      const formatted = format(active.sql, {
        language: "postgresql",
        keywordCase: "upper",
        dataTypeCase: "upper",
        functionCase: "upper",
        identifierCase: "preserve",
        indentStyle: "standard",
        logicalOperatorNewline: "before",
        expressionWidth: 80,
        linesBetweenQueries: 2,
        tabWidth: 2,
        useTabs: false,
      });
      setActiveSql(formatted);
    } catch (e) {
      alert("Format fail — SQL có thể còn syntax error:\n" + (e instanceof Error ? e.message : String(e)));
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
        <SchemaBrowser
          onInsert={insertAtCursor}
          collapsed={schemaCollapsed}
          onToggleCollapsed={() => setSchemaCollapsed((v) => !v)}
        />
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
              padding: "0.4rem 1rem",
              gap: 12,
              alignItems: "center",
              borderBottom: "1px solid var(--border)",
              fontSize: 12,
            }}
          >
            <button
              className="secondary"
              onClick={formatActive}
              title="Auto-format SQL: UPPERCASE keywords, comma-leading, 2-space indent"
              style={{ padding: "4px 12px", fontSize: 12 }}
            >
              ✨ Format
            </button>
            {loading && <span className="muted">Đang chạy…</span>}
            <span className="muted" style={{ marginLeft: "auto" }}>
              <b>Ctrl+Enter</b> chạy · bôi đen để chạy 1 đoạn · <b>Ctrl+Space</b> gợi ý · max 1000 rows / 2 MB
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
