import { useEffect, useMemo, useRef, useState } from "react";
import type { RunSqlResult } from "../lib/runSql";
import { ColumnMenu, type ColFilter, type SortDir } from "./ColumnMenu";

type OkResult = Extract<RunSqlResult, { status: "ok" }>;
type SortState = { col: string; dir: SortDir } | null;
// Persistent selection sau khi user click header/rownum (giống Excel)
type Selection = { type: "col"; name: string } | { type: "row"; idx: number } | null;

const DRAG_THRESHOLD = 4; // px — movement > ngưỡng này = drag, không phải click

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
  const [selected, setSelected] = useState<Selection>(null);
  const [sort, setSort] = useState<SortState>(null);
  const [filters, setFilters] = useState<Record<string, ColFilter>>({});
  const [openMenu, setOpenMenu] = useState<{ col: string; rect: DOMRect | null } | null>(null);
  // Ưu tiên columns từ backend (preserve thứ tự gốc). Fallback Object.keys
  // chỉ khi backend cũ chưa có field này — JS sẽ sort integer-like keys sai.
  const cols = result.columns?.length ? result.columns : Object.keys(result.rows[0]);

  // Drag detection: lưu toạ độ mousedown để phân biệt click vs drag
  const dragStart = useRef<{ x: number; y: number } | null>(null);

  const processed = useMemo(() => {
    let rows = result.rows;
    const activeFilters = Object.entries(filters).filter(([, f]) => f.text || f.allowedValues);
    if (activeFilters.length > 0) {
      rows = rows.filter((r) =>
        activeFilters.every(([col, f]) => {
          const s = stringify(r[col]);
          if (f.text && !s.toLowerCase().includes(f.text.toLowerCase())) return false;
          if (f.allowedValues && !f.allowedValues.has(s)) return false;
          return true;
        }),
      );
    }
    if (sort) {
      rows = [...rows].sort((a, b) => {
        const va = a[sort.col], vb = b[sort.col];
        if (va === vb) return 0;
        if (va === null || va === undefined) return 1;
        if (vb === null || vb === undefined) return -1;
        let cmp: number;
        if (typeof va === "number" && typeof vb === "number") cmp = va - vb;
        else cmp = String(va).localeCompare(String(vb), undefined, { numeric: true });
        return sort.dir === "asc" ? cmp : -cmp;
      });
    }
    return rows;
  }, [result.rows, filters, sort]);

  // Click outside table → clear persistent selection
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      const t = e.target as HTMLElement;
      if (!t.closest(".result-table")) setSelected(null);
    }
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, []);

  function applySort(col: string, dir: SortDir) {
    setSort({ col, dir });
  }

  function applyFilter(col: string, next: ColFilter) {
    setFilters((prev) => {
      const copy = { ...prev };
      if (!next.text && !next.allowedValues) delete copy[col];
      else copy[col] = next;
      return copy;
    });
  }

  function clearCol(col: string) {
    setFilters((prev) => {
      const { [col]: _gone, ...rest } = prev;
      return rest;
    });
    setSort((s) => (s?.col === col ? null : s));
  }

  async function writeClipboard(text: string, key: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(key);
    setTimeout(() => setCopied((c) => (c === key ? null : c)), 1400);
  }

  function copyAll() {
    writeClipboard(toDelimited(cols, processed, "\t"), "all");
  }

  function copyRow(r: Record<string, unknown>, idx: number) {
    writeClipboard(cols.map((c) => cellForDelimited(r[c], "\t")).join("\t"), `row-${idx}`);
  }

  function copyColumn(col: string) {
    const lines = [col, ...processed.map((r) => stringify(r[col]))];
    writeClipboard(lines.join("\n"), `col-${col}`);
  }

  function copyCell(v: unknown, key: string) {
    writeClipboard(stringify(v), key);
  }

  function download() {
    const csv = toDelimited(cols, processed, ",");
    // ﻿ = UTF-8 BOM → Excel đọc Unicode đúng
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `query_result_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // Helpers: chặn copy khi user đang drag-select hoặc vừa drag xong.
  function wasDrag(e: React.MouseEvent): boolean {
    const start = dragStart.current;
    if (!start) return false;
    const dx = Math.abs(e.clientX - start.x);
    const dy = Math.abs(e.clientY - start.y);
    return dx > DRAG_THRESHOLD || dy > DRAG_THRESHOLD;
  }

  function hasTextSel(): boolean {
    const s = window.getSelection();
    return !!s && !s.isCollapsed && s.toString().length > 0;
  }

  function onCellMouseDown(e: React.MouseEvent) {
    dragStart.current = { x: e.clientX, y: e.clientY };
  }

  function onCellClick(
    e: React.MouseEvent,
    handler: () => void,
    clearSel = true,
  ) {
    if (wasDrag(e)) return; // drag → không override, để native selection
    if (hasTextSel()) return; // có selection text → không override
    if (clearSel) setSelected(null);
    handler();
  }

  const filteredNote =
    processed.length !== result.rows.length
      ? ` (lọc ${processed.length}/${result.rows.length})`
      : "";

  const allValuesByCol = useMemo(() => {
    const m: Record<string, unknown[]> = {};
    for (const c of cols) m[c] = result.rows.map((r) => r[c]);
    return m;
  }, [cols, result.rows]);

  return (
    <div style={{ padding: 8 }}>
      <div style={{ marginBottom: 8, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <span className="success">✓ OK</span>
        <span className="muted">
          {result.row_count} dòng{filteredNote}
        </span>
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
          <button
            className="secondary"
            onClick={copyAll}
            title="Copy toàn bộ (TSV — paste vào Excel/Sheets)"
            style={{ fontSize: 12, padding: "3px 10px" }}
          >
            {copied === "all" ? "✓ Copied" : "📋 Copy all"}
          </button>
          <button
            className="secondary"
            onClick={download}
            title="Download file CSV"
            style={{ fontSize: 12, padding: "3px 10px" }}
          >
            ⬇ Download CSV
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
      <div style={{ overflow: "auto", maxHeight: "calc(100% - 40px)" }}>
        <table className="result-table" style={{ width: "auto" }}>
          <thead style={{ position: "sticky", top: 0, zIndex: 2 }}>
            <tr>
              <th
                className="rownum-header"
                title="Cột số thứ tự"
                style={{ background: "var(--panel-light)", textAlign: "center", width: 44, userSelect: "none" }}
              >
                #
              </th>
              {cols.map((c) => {
                const isSelected = selected?.type === "col" && selected.name === c;
                return (
                  <HeaderCell
                    key={c}
                    col={c}
                    sortDir={sort?.col === c ? sort.dir : null}
                    hasFilter={!!filters[c]}
                    isSelected={isSelected}
                    onOpenMenu={(rect) => setOpenMenu({ col: c, rect })}
                    onSelectCol={(e) => {
                      if (wasDrag(e) || hasTextSel()) return;
                      // Toggle: click lần 2 trên cùng col → deselect
                      if (isSelected) {
                        setSelected(null);
                      } else {
                        setSelected({ type: "col", name: c });
                        copyColumn(c);
                      }
                    }}
                    onMouseDown={onCellMouseDown}
                  />
                );
              })}
            </tr>
          </thead>
          <tbody>
            {processed.map((row, i) => {
              const isRowSelected = selected?.type === "row" && selected.idx === i;
              const isRowFlash = copied === `row-${i}`;
              return (
                <tr
                  key={i}
                  className={isRowSelected ? "row-selected" : isRowFlash ? "row-copied" : undefined}
                >
                  <td
                    className="rownum"
                    title="Click để chọn + copy cả dòng. Click lại để bỏ chọn."
                    onMouseDown={onCellMouseDown}
                    onClick={(e) => {
                      if (wasDrag(e) || hasTextSel()) return;
                      if (isRowSelected) {
                        setSelected(null);
                      } else {
                        setSelected({ type: "row", idx: i });
                        copyRow(row, i);
                      }
                    }}
                    style={{
                      textAlign: "center",
                      background: isRowSelected
                        ? "var(--accent)"
                        : isRowFlash
                          ? "var(--accent-dim)"
                          : "var(--panel-light)",
                      color: isRowSelected || isRowFlash ? "#fff" : "var(--text-dim)",
                      cursor: "pointer",
                      userSelect: "none",
                      fontWeight: 600,
                      fontSize: 11,
                    }}
                  >
                    {i + 1}
                  </td>
                  {cols.map((c) => {
                    const key = `${i}-${c}`;
                    const isCellCopied = copied === key;
                    const isInSelectedCol = selected?.type === "col" && selected.name === c;
                    const isInSelectedRow = isRowSelected;
                    return (
                      <td
                        key={c}
                        onMouseDown={onCellMouseDown}
                        onClick={(e) => onCellClick(e, () => copyCell(row[c], key))}
                        title="Click copy ô · bôi đen nhiều ô để chọn vùng rồi Ctrl+C"
                        style={{
                          cursor: "cell",
                          background: isCellCopied
                            ? "var(--accent-dim)"
                            : isInSelectedCol || isInSelectedRow
                              ? "rgba(249, 115, 22, 0.22)"
                              : undefined,
                          color: isCellCopied ? "#fff" : undefined,
                          transition: "background 0.12s",
                        }}
                      >
                        {formatCell(row[c])}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
        {processed.length === 0 && (
          <div className="muted" style={{ padding: 12, textAlign: "center" }}>
            Filter không match dòng nào — clear filter để xem lại.
          </div>
        )}
      </div>
      <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
        💡 Click số dòng / tên cột để <b>chọn + copy</b> cả row/column (click lại bỏ chọn) ·
        Click ô để copy giá trị · Kéo chuột để chọn vùng tự do rồi <b>Ctrl+C</b> ·
        Click ▾ để sort / filter
      </div>

      {openMenu && (
        <ColumnMenu
          col={openMenu.col}
          values={allValuesByCol[openMenu.col]}
          currentFilter={filters[openMenu.col] ?? {}}
          currentSort={sort?.col === openMenu.col ? sort.dir : null}
          anchorRect={openMenu.rect}
          onSort={(dir) => applySort(openMenu.col, dir)}
          onApplyFilter={(next) => applyFilter(openMenu.col, next)}
          onClear={() => clearCol(openMenu.col)}
          onClose={() => setOpenMenu(null)}
        />
      )}
    </div>
  );
}

function HeaderCell({
  col,
  sortDir,
  hasFilter,
  isSelected,
  onOpenMenu,
  onSelectCol,
  onMouseDown,
}: {
  col: string;
  sortDir: SortDir | null;
  hasFilter: boolean;
  isSelected: boolean;
  onOpenMenu: (rect: DOMRect) => void;
  onSelectCol: (e: React.MouseEvent) => void;
  onMouseDown: (e: React.MouseEvent) => void;
}) {
  const btnRef = useRef<HTMLButtonElement | null>(null);
  return (
    <th
      style={{
        whiteSpace: "nowrap",
        background: isSelected ? "var(--accent)" : undefined,
        color: isSelected ? "#fff" : undefined,
        transition: "background 0.12s",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <span
          onMouseDown={onMouseDown}
          onClick={onSelectCol}
          style={{ cursor: "pointer", flex: 1, userSelect: "none" }}
          title="Click tên cột để chọn + copy cả cột. Click lại để bỏ chọn."
        >
          {col}
          {sortDir === "asc" && <span style={{ color: isSelected ? "#fff" : "var(--accent)" }}> ▲</span>}
          {sortDir === "desc" && <span style={{ color: isSelected ? "#fff" : "var(--accent)" }}> ▼</span>}
          {hasFilter && <span style={{ color: isSelected ? "#fff" : "var(--accent)", fontSize: 10 }}> ⚑</span>}
        </span>
        <button
          ref={btnRef}
          onClick={(e) => {
            e.stopPropagation();
            const rect = btnRef.current?.getBoundingClientRect() ?? null;
            onOpenMenu(rect!);
          }}
          title="Mở menu sort / filter"
          style={{
            background: "transparent",
            border: "none",
            color: isSelected ? "#fff" : "var(--text-dim)",
            padding: "0 4px",
            cursor: "pointer",
            fontSize: 12,
          }}
        >
          ▾
        </button>
      </div>
    </th>
  );
}

function stringify(v: unknown): string {
  if (v === null || v === undefined) return "NULL";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "NULL";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function cellForDelimited(v: unknown, delim: string): string {
  if (v === null || v === undefined) return "";
  const s = typeof v === "object" ? JSON.stringify(v) : String(v);
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
