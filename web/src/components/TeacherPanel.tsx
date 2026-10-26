import { useEffect, useState } from "react";
import { supabase } from "../supabase";

type LogRow = {
  id: number;
  created_at: string;
  student_email: string | null;
  exercise_id: string | null;
  status: "ok" | "error";
  error_code: string | null;
  error_message: string | null;
  row_count: number | null;
  exec_ms: number | null;
  sql_text: string;
};

type Stats = {
  since_days: number;
  total_queries: number;
  ok_queries: number;
  error_queries: number;
  active_students: number;
  active_exercises: number;
  error_rate_pct: number;
  top_errors: { error_code: string; occurrences: number; affected_students: number; sample_message: string }[];
  top_students: { email: string; queries: number; ok_queries: number; err_queries: number; last_active: string }[];
};

export function TeacherPanel({ onClose }: { onClose: () => void }) {
  const [logs, setLogs] = useState<LogRow[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [email, setEmail] = useState("");
  const [exercise, setExercise] = useState("");
  const [status, setStatus] = useState<"" | "ok" | "error">("");
  const [sinceDays, setSinceDays] = useState(7);
  const [limit, setLimit] = useState(200);
  const [selected, setSelected] = useState<LogRow | null>(null);

  async function reload() {
    setLoading(true);
    setError(null);
    const [logsRes, statsRes] = await Promise.all([
      supabase.rpc("teacher_query_log", {
        filter_email:    email.trim() || null,
        filter_exercise: exercise.trim() || null,
        filter_status:   status || null,
        since_days:      sinceDays,
        max_rows:        limit,
      }),
      supabase.rpc("teacher_stats", { since_days: sinceDays }),
    ]);
    if (logsRes.error) {
      setError(logsRes.error.message);
    } else {
      setLogs((logsRes.data as LogRow[]) ?? []);
    }
    if (!statsRes.error) {
      setStats(statsRes.data as Stats);
    }
    setLoading(false);
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.65)",
        zIndex: 50,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(1400px, 96vw)",
          height: "min(920px, 92vh)",
          background: "var(--bg)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "10px 16px",
            background: "var(--panel)",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 700 }}>
            👨‍🏫 Teacher Dashboard · <span className="muted" style={{ fontSize: 12 }}>query_log + stats</span>
          </div>
          <button className="secondary" onClick={onClose} style={{ padding: "4px 12px" }}>
            ✕ Đóng
          </button>
        </div>

        {/* Stats cards */}
        {stats && (
          <div style={{ padding: "10px 16px", display: "flex", gap: 10, flexWrap: "wrap", borderBottom: "1px solid var(--border)" }}>
            <Card label="Tổng query" value={stats.total_queries} sub={`${stats.since_days} ngày`} />
            <Card label="OK" value={stats.ok_queries} sub={`${100 - stats.error_rate_pct}%`} color="var(--success)" />
            <Card label="Lỗi" value={stats.error_queries} sub={`${stats.error_rate_pct}%`} color="var(--error)" />
            <Card label="Học viên active" value={stats.active_students} />
            <Card label="Exercise touched" value={stats.active_exercises} />
          </div>
        )}

        {/* Filters */}
        <div style={{ padding: "10px 16px", display: "flex", gap: 8, alignItems: "center", borderBottom: "1px solid var(--border)", flexWrap: "wrap", fontSize: 12 }}>
          <FilterInput label="Email" value={email} onChange={setEmail} placeholder="student@" width={180} />
          <FilterInput label="Exercise" value={exercise} onChange={setExercise} placeholder="A1, B2..." width={120} />
          <FilterSelect label="Status" value={status} onChange={(v) => setStatus(v as "" | "ok" | "error")} options={[
            { value: "", label: "All" },
            { value: "ok", label: "OK" },
            { value: "error", label: "Error" },
          ]} />
          <FilterSelect label="Since" value={String(sinceDays)} onChange={(v) => setSinceDays(+v)} options={[
            { value: "1", label: "1 day" },
            { value: "7", label: "7 days" },
            { value: "30", label: "30 days" },
            { value: "90", label: "90 days" },
          ]} />
          <FilterSelect label="Limit" value={String(limit)} onChange={(v) => setLimit(+v)} options={[
            { value: "50", label: "50" },
            { value: "200", label: "200" },
            { value: "500", label: "500" },
            { value: "1000", label: "1000" },
          ]} />
          <button onClick={reload} disabled={loading} style={{ padding: "4px 14px" }}>
            {loading ? "Loading…" : "🔄 Refresh"}
          </button>
          <span className="muted" style={{ marginLeft: "auto" }}>
            {logs ? `${logs.length} rows` : "—"}
          </span>
        </div>

        {/* Body */}
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          {/* Left: query log */}
          <div style={{ flex: 2, overflow: "auto", minWidth: 0 }}>
            {error && <div className="error" style={{ padding: 12 }}>❌ {error}</div>}
            {!error && logs && logs.length === 0 && (
              <div className="muted" style={{ padding: 20 }}>Không có log match filter.</div>
            )}
            {logs && logs.length > 0 && (
              <table className="result-table" style={{ width: "100%", fontSize: 12 }}>
                <thead style={{ position: "sticky", top: 0, background: "var(--panel-light)", zIndex: 1 }}>
                  <tr>
                    <th>Time</th>
                    <th>Student</th>
                    <th>Exercise</th>
                    <th>Status</th>
                    <th>Rows</th>
                    <th>ms</th>
                    <th>SQL snippet</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((l) => (
                    <tr
                      key={l.id}
                      onClick={() => setSelected(l)}
                      style={{ cursor: "pointer", background: selected?.id === l.id ? "rgba(249, 115, 22, 0.15)" : undefined }}
                      title="Click để xem SQL đầy đủ + error"
                    >
                      <td style={{ whiteSpace: "nowrap" }}>{fmtTime(l.created_at)}</td>
                      <td style={{ whiteSpace: "nowrap" }}>{l.student_email ?? "—"}</td>
                      <td>{l.exercise_id ?? <span className="muted">—</span>}</td>
                      <td style={{ color: l.status === "ok" ? "var(--success)" : "var(--error)" }}>{l.status}</td>
                      <td style={{ textAlign: "right" }}>{l.row_count ?? ""}</td>
                      <td style={{ textAlign: "right" }}>{l.exec_ms ?? ""}</td>
                      <td style={{ fontFamily: "ui-monospace, monospace", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 400 }}>
                        {l.sql_text.slice(0, 100)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Right: details */}
          <div style={{ width: 440, borderLeft: "1px solid var(--border)", overflow: "auto", background: "var(--panel)" }}>
            {selected ? (
              <LogDetail log={selected} />
            ) : stats ? (
              <StatsDetail stats={stats} />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function Card({ label, value, sub, color }: { label: string; value: number | string; sub?: string; color?: string }) {
  return (
    <div
      style={{
        padding: "8px 14px",
        background: "var(--panel)",
        border: "1px solid var(--border)",
        borderRadius: 6,
        minWidth: 110,
      }}
    >
      <div className="muted" style={{ fontSize: 11 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color ?? "var(--text)" }}>{value}</div>
      {sub && <div className="muted" style={{ fontSize: 11 }}>{sub}</div>}
    </div>
  );
}

function FilterInput({ label, value, onChange, placeholder, width }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; width?: number }) {
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span className="muted">{label}:</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{ width: width ?? 120, fontSize: 12, padding: "3px 6px" }}
      />
    </label>
  );
}

function FilterSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span className="muted">{label}:</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} style={{ fontSize: 12, padding: "3px 6px", background: "var(--panel)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 4 }}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

function LogDetail({ log }: { log: LogRow }) {
  return (
    <div style={{ padding: 14 }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Query #{log.id}</div>
      <Meta label="Student"  value={log.student_email ?? "—"} />
      <Meta label="Time"     value={new Date(log.created_at).toLocaleString()} />
      <Meta label="Exercise" value={log.exercise_id ?? "—"} />
      <Meta label="Status"   value={log.status} color={log.status === "ok" ? "var(--success)" : "var(--error)"} />
      <Meta label="Rows"     value={log.row_count ?? "—"} />
      <Meta label="Exec ms"  value={log.exec_ms ?? "—"} />
      {log.error_code && (
        <>
          <Meta label="Error code" value={log.error_code} color="var(--error)" />
          <div style={{ marginTop: 4, fontSize: 12, color: "var(--error)", background: "rgba(239,68,68,0.1)", padding: 8, borderRadius: 4 }}>
            {log.error_message}
          </div>
        </>
      )}
      <div style={{ marginTop: 12, fontSize: 12, fontWeight: 600 }}>SQL</div>
      <pre
        style={{
          marginTop: 4,
          background: "var(--bg)",
          padding: 10,
          fontSize: 12,
          maxHeight: 400,
          overflow: "auto",
          whiteSpace: "pre-wrap",
          border: "1px solid var(--border)",
          borderRadius: 4,
        }}
      >
        {log.sql_text}
      </pre>
      <button
        className="secondary"
        onClick={() => navigator.clipboard.writeText(log.sql_text)}
        style={{ marginTop: 8, fontSize: 12, padding: "3px 10px" }}
      >
        📋 Copy SQL
      </button>
    </div>
  );
}

function StatsDetail({ stats }: { stats: Stats }) {
  return (
    <div style={{ padding: 14 }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Top errors ({stats.since_days}d)</div>
      {stats.top_errors.length === 0 && <div className="muted" style={{ fontSize: 12 }}>Không có error.</div>}
      {stats.top_errors.slice(0, 8).map((e) => (
        <div key={e.error_code} style={{ marginBottom: 8, fontSize: 12 }}>
          <div><code>{e.error_code ?? "null"}</code> · {e.occurrences} lần · {e.affected_students} người</div>
          <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{e.sample_message?.slice(0, 140)}</div>
        </div>
      ))}
      <div style={{ fontSize: 13, fontWeight: 600, margin: "16px 0 8px" }}>Top students ({stats.since_days}d)</div>
      {stats.top_students.slice(0, 10).map((s) => (
        <div key={s.email} style={{ marginBottom: 6, fontSize: 12, display: "flex", justifyContent: "space-between" }}>
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginRight: 8 }}>{s.email}</span>
          <span className="muted">
            {s.queries} ({s.ok_queries}ok/{s.err_queries}err)
          </span>
        </div>
      ))}
      <div className="muted" style={{ fontSize: 11, marginTop: 12 }}>
        💡 Click 1 row ở bảng trái để xem query đầy đủ.
      </div>
    </div>
  );
}

function Meta({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{ fontSize: 12, marginBottom: 3 }}>
      <span className="muted">{label}:</span>{" "}
      <span style={{ color: color ?? "var(--text)" }}>{value}</span>
    </div>
  );
}

function fmtTime(s: string): string {
  const d = new Date(s);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  return sameDay
    ? d.toLocaleTimeString("en-GB").slice(0, 8)
    : d.toLocaleString("en-GB", { year: "2-digit", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}
