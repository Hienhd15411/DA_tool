import { useState } from "react";
import { useSchema, type SchemaTable } from "../lib/useSchema";

export function SchemaBrowser({
  onInsert,
  collapsed,
  onToggleCollapsed,
}: {
  onInsert: (text: string) => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}) {
  const { tables, error } = useSchema();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("");

  // Collapsed state: chỉ hiện 1 strip nhỏ với nút mở lại
  if (collapsed) {
    return (
      <div
        style={{
          width: 32,
          borderRight: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          paddingTop: 8,
          background: "var(--bg)",
        }}
      >
        <button
          onClick={onToggleCollapsed}
          title="Mở Dataset browser"
          className="secondary"
          style={{ padding: "4px 6px", fontSize: 14, writingMode: "vertical-rl" }}
        >
          ▸ Dataset
        </button>
      </div>
    );
  }

  const toggle = (name: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const filtered = tables?.filter(
    (t) =>
      !filter ||
      t.table_name.includes(filter.toLowerCase()) ||
      t.columns.some((c) => c.name.toLowerCase().includes(filter.toLowerCase())),
  );

  const byGroup = {
    fact:  filtered?.filter((t) => t.group === "fact")  ?? [],
    dim:   filtered?.filter((t) => t.group === "dim")   ?? [],
    other: filtered?.filter((t) => t.group === "other") ?? [],
  };

  return (
    <div
      style={{
        width: 300,
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <div style={{ padding: "0.7rem", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
          <div style={{ fontWeight: 700, fontSize: 13 }}>
            🗂️ Dataset · <code>shopee</code>
          </div>
          <button
            onClick={onToggleCollapsed}
            title="Ẩn Dataset browser"
            className="secondary"
            style={{ padding: "2px 8px", fontSize: 11 }}
          >
            ◂ Ẩn
          </button>
        </div>
        <input
          placeholder="Tìm bảng hoặc cột..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{ width: "100%", fontSize: 12 }}
        />
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "0.5rem" }}>
        {error && (
          <div className="error" style={{ padding: 8, fontSize: 12 }}>
            ❌ {error}
            <div className="muted" style={{ marginTop: 4 }}>
              Chạy lại workflow migrate để apply migration 009.
            </div>
          </div>
        )}

        {!tables && !error && <div className="muted">Đang tải schema…</div>}

        {tables && tables.length === 0 && (
          <div className="muted">Schema rỗng. Chạy seed database trước.</div>
        )}

        {(["fact", "dim", "other"] as const).map((group) =>
          byGroup[group].length > 0 ? (
            <div key={group} style={{ marginBottom: 8 }}>
              <div
                className="muted"
                style={{
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  padding: "4px 6px",
                  color: group === "fact" ? "#f97316" : group === "dim" ? "#60a5fa" : "#94a3b8",
                }}
              >
                {group === "fact" ? "Fact tables" : group === "dim" ? "Dim tables" : "Other"}
              </div>
              {byGroup[group].map((t) => (
                <TableNode
                  key={t.table_name}
                  table={t}
                  expanded={expanded.has(t.table_name)}
                  onToggle={() => toggle(t.table_name)}
                  onInsert={onInsert}
                />
              ))}
            </div>
          ) : null,
        )}
      </div>

      <div
        style={{
          borderTop: "1px solid var(--border)",
          padding: "0.5rem 0.7rem",
          fontSize: 11,
          color: "var(--text-dim)",
        }}
      >
        💡 Click tên bảng/cột để insert vào editor
      </div>
    </div>
  );
}

function TableNode({
  table,
  expanded,
  onToggle,
  onInsert,
}: {
  table: SchemaTable;
  expanded: boolean;
  onToggle: () => void;
  onInsert: (text: string) => void;
}) {
  return (
    <div style={{ marginBottom: 2 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <button
          className="secondary"
          onClick={onToggle}
          style={{
            background: "transparent",
            padding: "2px 4px",
            width: 20,
            fontSize: 12,
            color: "var(--text-dim)",
          }}
          aria-label={expanded ? "collapse" : "expand"}
        >
          {expanded ? "▾" : "▸"}
        </button>
        <button
          onClick={() => onInsert(`shopee.${table.table_name}`)}
          style={{
            flex: 1,
            textAlign: "left",
            background: "transparent",
            color: "var(--text)",
            padding: "2px 4px",
            fontSize: 13,
            fontFamily: "ui-monospace, monospace",
          }}
          title="Click để chèn 'shopee.tên_bảng' vào editor"
        >
          {table.table_name}{" "}
          <span className="muted" style={{ fontSize: 11 }}>
            ({formatNum(table.row_count)})
          </span>
        </button>
      </div>
      {expanded && (
        <div style={{ paddingLeft: 24, marginTop: 2, marginBottom: 4 }}>
          {table.columns.map((c) => (
            <button
              key={c.name}
              onClick={() => onInsert(c.name)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                background: "transparent",
                color: "var(--text)",
                padding: "1px 6px",
                fontSize: 12,
                fontFamily: "ui-monospace, monospace",
              }}
              title={`Click để chèn '${c.name}' — ${c.type}`}
            >
              <span>{c.name}</span>{" "}
              <span className="muted">{c.type}</span>
              {!c.nullable && <span style={{ color: "#f97316", fontSize: 10 }}> NOT NULL</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function formatNum(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "k";
  return String(n);
}
