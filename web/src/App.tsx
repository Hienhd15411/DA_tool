import { useEffect, useRef, useState } from "react";
import type { editor } from "monaco-editor";
import { AuthGate } from "./components/AuthGate";
import { Header } from "./components/Header";
import { SchemaBrowser } from "./components/SchemaBrowser";
import { SqlEditor } from "./components/SqlEditor";
import { ResultTable } from "./components/ResultTable";
import { TabBar, type QueryTab } from "./components/TabBar";
import { TeacherPanel } from "./components/TeacherPanel";
import { QueryHistory } from "./components/QueryHistory";
import { runSql, type RunSqlResult } from "./lib/runSql";
import { pushHistory } from "./lib/queryHistory";
import { useTeacher } from "./lib/useTeacher";
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
const SPLIT_KEY = "datool.split.v1";   // % chiều cao của editor pane

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
  } catch {/* ignore */}
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
  const [splitPct, setSplitPct] = useState<number>(() => {
    try {
      const v = Number(localStorage.getItem(SPLIT_KEY));
      return v >= 20 && v <= 80 ? v : 55;
    } catch { return 55; }
  });
  const [showTeacher, setShowTeacher] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const isTeacher = useTeacher();

  const active = tabs.find((t) => t.id === activeId) ?? tabs[0];
  const activeResult = results[active.id] ?? null;
  const loading = loadingTabId === active.id;

  // Debounce localStorage write — tránh ghi mỗi keystroke (gây lag khi gõ nhanh)
  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        localStorage.setItem(TABS_STORAGE_KEY, JSON.stringify({ tabs, activeId } satisfies StoredState));
      } catch {/* quota */}
    }, 500);
    return () => clearTimeout(timer);
  }, [tabs, activeId]);

  useEffect(() => {
    try { localStorage.setItem(COLLAPSE_KEY, schemaCollapsed ? "1" : "0"); } catch {/* quota */}
  }, [schemaCollapsed]);

  useEffect(() => {
    try { localStorage.setItem(SPLIT_KEY, String(Math.round(splitPct))); } catch {/* quota */}
  }, [splitPct]);

  function setActiveSql(next: string) {
    setTabs((ts) => ts.map((t) => (t.id === activeId ? { ...t, sql: next } : t)));
  }

  async function run() {
    const tabId = active.id;
    const ed = editorRef.current;
    // Editor uncontrolled → đọc nội dung LIVE từ editor, không từ state
    let sql = active.sql;
    if (ed) {
      const sel = ed.getSelection();
      const model = ed.getModel();
      if (sel && !sel.isEmpty() && model) {
        const picked = model.getValueInRange(sel);
        sql = picked.trim() ? picked : ed.getValue();
      } else {
        sql = ed.getValue();
      }
    }
    if (!sql.trim()) return;
    setLoadingTabId(tabId);
    try {
      const r = await runSql(sql, null);
      setResults((prev) => ({ ...prev, [tabId]: r }));
      // Push vào history (localStorage)
      if (r.status === "ok") {
        pushHistory({ sql, status: "ok", exec_ms: r.exec_ms, row_count: r.row_count });
      } else {
        pushHistory({ sql, status: "error", exec_ms: r.exec_ms, error_code: r.error_code });
      }
    } finally {
      setLoadingTabId((cur) => (cur === tabId ? null : cur));
    }
  }

  async function formatActive() {
    const ed = editorRef.current;
    const src = ed ? ed.getValue() : active.sql;
    try {
      const { format } = await import("sql-formatter");
      const formatted = format(src, {
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
      // Push thẳng vào editor → onChange tự sync state
      if (ed) ed.setValue(formatted);
      else setActiveSql(formatted);
    } catch (e) {
      alert("Format fail — SQL có thể còn syntax error:\n" + (e instanceof Error ? e.message : String(e)));
    }
  }

  function clearActive() {
    const ed = editorRef.current;
    if (ed) ed.setValue("");
    else setActiveSql("");
    setResults((prev) => ({ ...prev, [active.id]: null }));
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

  function loadSqlFromHistory(sql: string) {
    // Tạo tab mới cho query được load từ history
    const t: QueryTab = { id: uuid(), title: "History", sql };
    setTabs((ts) => [...ts, t]);
    setActiveId(t.id);
  }

  // Resize handle
  const splitContainerRef = useRef<HTMLDivElement | null>(null);
  const draggingRef = useRef(false);
  function onSplitMouseDown(e: React.MouseEvent) {
    e.preventDefault();
    draggingRef.current = true;
    document.body.style.cursor = "row-resize";
  }
  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!draggingRef.current || !splitContainerRef.current) return;
      const rect = splitContainerRef.current.getBoundingClientRect();
      const pct = ((e.clientY - rect.top) / rect.height) * 100;
      setSplitPct(Math.max(20, Math.min(80, pct)));
    }
    function onUp() {
      draggingRef.current = false;
      document.body.style.cursor = "";
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, []);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <Header
        email={email}
        isTeacher={isTeacher}
        onOpenTeacher={() => setShowTeacher(true)}
        onOpenHistory={() => setShowHistory(true)}
      />
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
              gap: 10,
              alignItems: "center",
              borderBottom: "1px solid var(--border)",
              fontSize: 12,
            }}
          >
            <button
              onClick={run}
              disabled={loading}
              title="Chạy query (Ctrl+Enter). Bôi đen để chạy 1 đoạn."
              style={{ padding: "4px 14px", fontSize: 12 }}
            >
              {loading ? "⏳ Đang chạy…" : "▶ Run (Ctrl+Enter)"}
            </button>
            <button
              className="secondary"
              onClick={formatActive}
              title="Auto-format SQL (UPPERCASE keyword, comma leading, 2-space indent)"
              style={{ padding: "4px 12px", fontSize: 12 }}
            >
              ✨ Format
            </button>
            <button
              className="secondary"
              onClick={clearActive}
              title="Xoá nội dung tab hiện tại"
              style={{ padding: "4px 10px", fontSize: 12 }}
            >
              Xoá
            </button>
            <span className="muted" style={{ marginLeft: "auto" }}>
              <b>Ctrl+Enter</b> · bôi đen để chạy 1 đoạn · max 1000 rows / 2 MB
            </span>
          </div>
          <div ref={splitContainerRef} style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
            <div style={{ height: `${splitPct}%`, minHeight: 100, overflow: "hidden" }}>
              <SqlEditor
                tabId={active.id}
                initialValue={active.sql}
                onChange={setActiveSql}
                onRun={run}
                onReady={(ed) => (editorRef.current = ed)}
              />
            </div>
            <div
              onMouseDown={onSplitMouseDown}
              title="Kéo để điều chỉnh kích thước panel"
              style={{
                height: 6,
                background: "var(--border)",
                cursor: "row-resize",
                flex: "0 0 auto",
                position: "relative",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: "50%",
                  top: "50%",
                  transform: "translate(-50%, -50%)",
                  width: 40,
                  height: 2,
                  background: "var(--text-dim)",
                  borderRadius: 1,
                }}
              />
            </div>
            <div
              style={{
                flex: 1,
                overflow: "auto",
                background: "var(--panel)",
                minHeight: 100,
              }}
            >
              <ResultTable result={activeResult} loading={loading} />
            </div>
          </div>
        </div>
      </div>

      {showTeacher && isTeacher && <TeacherPanel onClose={() => setShowTeacher(false)} />}
      {showHistory && <QueryHistory onPickSql={loadSqlFromHistory} onClose={() => setShowHistory(false)} />}
    </div>
  );
}
