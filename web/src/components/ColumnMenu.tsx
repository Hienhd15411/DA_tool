import { useEffect, useMemo, useRef, useState } from "react";

export type ColFilter = {
  text?: string;                   // "Filter by condition" — substring match
  allowedValues?: Set<string>;     // "Filter by values" — set whitelist (undefined = all allowed)
};

export type SortDir = "asc" | "desc";

export function ColumnMenu({
  col,
  values,          // all raw values of column (for value picker)
  currentFilter,
  currentSort,     // 'asc' | 'desc' | null
  onSort,
  onApplyFilter,
  onClear,
  onClose,
  anchorRect,
}: {
  col: string;
  values: unknown[];
  currentFilter: ColFilter;
  currentSort: SortDir | null;
  onSort: (dir: SortDir) => void;
  onApplyFilter: (next: ColFilter) => void;
  onClear: () => void;
  onClose: () => void;
  anchorRect: DOMRect | null;
}) {
  // State local trong menu, chỉ apply khi OK
  const [text, setText] = useState(currentFilter.text ?? "");
  const [search, setSearch] = useState("");
  const [allowed, setAllowed] = useState<Set<string>>(
    currentFilter.allowedValues ?? new Set(uniqueStringValues(values)),
  );
  const [expandCond, setExpandCond] = useState(!!currentFilter.text);
  const [expandVals, setExpandVals] = useState(!!currentFilter.allowedValues);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const uniqueVals = useMemo(() => uniqueStringValues(values).sort(cmpNatural), [values]);
  const allUnique = useMemo(() => new Set(uniqueVals), [uniqueVals]);
  const filtered = useMemo(
    () => (search.trim() ? uniqueVals.filter((v) => v.toLowerCase().includes(search.toLowerCase())) : uniqueVals),
    [uniqueVals, search],
  );

  // Click outside → close
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) onClose();
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  function toggleVal(v: string) {
    setAllowed((prev) => {
      const next = new Set(prev);
      if (next.has(v)) next.delete(v);
      else next.add(v);
      return next;
    });
  }

  function selectAll() {
    setAllowed(new Set(uniqueVals));
  }
  function clearAll() {
    setAllowed(new Set());
  }

  function apply() {
    const next: ColFilter = {};
    if (expandCond && text.trim()) next.text = text;
    if (expandVals && allowed.size !== allUnique.size) next.allowedValues = allowed;
    onApplyFilter(next);
    onClose();
  }

  function clearAndClose() {
    onClear();
    onClose();
  }

  // Position menu below anchor
  const style: React.CSSProperties = anchorRect
    ? {
        position: "fixed",
        top: Math.min(anchorRect.bottom + 4, window.innerHeight - 440),
        left: Math.min(anchorRect.left, window.innerWidth - 320),
        zIndex: 100,
      }
    : { position: "fixed", top: 50, left: 50, zIndex: 100 };

  return (
    <div
      ref={menuRef}
      style={{
        ...style,
        width: 300,
        maxHeight: 430,
        display: "flex",
        flexDirection: "column",
        background: "var(--panel)",
        border: "1px solid var(--border)",
        borderRadius: 6,
        boxShadow: "0 6px 24px rgba(0,0,0,0.5)",
        fontSize: 13,
        color: "var(--text)",
      }}
      onClick={(e) => e.stopPropagation()}
    >
      <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)", fontWeight: 600 }}>
        Column: <code>{col}</code>
      </div>

      <button
        className="secondary"
        style={menuItem(currentSort === "asc")}
        onClick={() => { onSort("asc"); onClose(); }}
      >
        ↑ Sort A → Z (ASC)
      </button>
      <button
        className="secondary"
        style={menuItem(currentSort === "desc")}
        onClick={() => { onSort("desc"); onClose(); }}
      >
        ↓ Sort Z → A (DESC)
      </button>

      <div style={{ borderTop: "1px solid var(--border)" }} />

      <button
        className="secondary"
        style={menuItem(false)}
        onClick={() => setExpandCond((v) => !v)}
      >
        {expandCond ? "▾" : "▸"} Filter by condition
      </button>
      {expandCond && (
        <div style={{ padding: "4px 12px 8px 20px" }}>
          <input
            autoFocus
            placeholder="Contains…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            style={{ width: "100%", fontSize: 12, padding: "4px 6px" }}
          />
        </div>
      )}

      <button
        className="secondary"
        style={menuItem(false)}
        onClick={() => setExpandVals((v) => !v)}
      >
        {expandVals ? "▾" : "▸"} Filter by values
      </button>
      {expandVals && (
        <div style={{ padding: "4px 12px 4px 20px", display: "flex", flexDirection: "column", gap: 6, flex: 1, minHeight: 0 }}>
          <input
            placeholder="Search values…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: "100%", fontSize: 12, padding: "4px 6px" }}
          />
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
            <div>
              <a onClick={selectAll} style={linkStyle}>Select all {uniqueVals.length}</a>
              {" · "}
              <a onClick={clearAll} style={linkStyle}>Clear</a>
            </div>
            <span className="muted">Chọn {allowed.size}/{uniqueVals.length}</span>
          </div>
          <div style={{ flex: 1, overflowY: "auto", border: "1px solid var(--border)", borderRadius: 4, padding: 6, minHeight: 120, maxHeight: 180 }}>
            {filtered.length === 0 && <div className="muted" style={{ fontSize: 11 }}>Không có value match</div>}
            {filtered.map((v) => (
              <label
                key={v}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "2px 4px",
                  cursor: "pointer",
                  borderRadius: 3,
                  fontSize: 12,
                }}
              >
                <input type="checkbox" checked={allowed.has(v)} onChange={() => toggleVal(v)} />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                  {v === "" ? <em className="muted">(empty)</em> : v === "NULL" ? <em className="muted">NULL</em> : v}
                </span>
              </label>
            ))}
          </div>
        </div>
      )}

      <div style={{ padding: "8px 12px", display: "flex", gap: 8, justifyContent: "flex-end", borderTop: "1px solid var(--border)" }}>
        <button className="secondary" onClick={clearAndClose} style={{ fontSize: 12 }} title="Xoá filter + sort cột này">
          Clear
        </button>
        <button onClick={apply} style={{ fontSize: 12 }}>OK</button>
      </div>
    </div>
  );
}

function menuItem(active: boolean): React.CSSProperties {
  return {
    textAlign: "left",
    background: active ? "var(--accent-dim)" : "transparent",
    color: active ? "#fff" : "var(--text)",
    padding: "6px 12px",
    border: "none",
    borderRadius: 0,
    fontWeight: 400,
    fontSize: 13,
    cursor: "pointer",
  };
}

const linkStyle: React.CSSProperties = {
  color: "var(--accent)",
  cursor: "pointer",
  textDecoration: "underline",
};

function uniqueStringValues(values: unknown[]): string[] {
  const set = new Set<string>();
  for (const v of values) {
    if (v === null || v === undefined) set.add("NULL");
    else if (typeof v === "object") set.add(JSON.stringify(v));
    else set.add(String(v));
  }
  return [...set];
}

function cmpNatural(a: string, b: string): number {
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
}
