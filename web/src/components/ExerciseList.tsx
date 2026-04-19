import { useEffect, useState } from "react";
import { supabase } from "../supabase";

export type Exercise = {
  exercise_id: string;
  theme: string;
  title: string;
  level: number;
  description_md: string;
};

export function ExerciseList({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (ex: Exercise | null) => void;
}) {
  const [exercises, setExercises] = useState<Exercise[]>([]);

  useEffect(() => {
    supabase
      .from("exercise")
      .select("*")
      .order("exercise_id", { ascending: true })
      .then(({ data }) => setExercises((data as Exercise[]) ?? []));
  }, []);

  const byTheme = exercises.reduce<Record<string, Exercise[]>>((acc, e) => {
    (acc[e.theme] ??= []).push(e);
    return acc;
  }, {});

  return (
    <div
      style={{
        width: 260,
        borderRight: "1px solid var(--border)",
        overflowY: "auto",
        padding: "0.8rem",
      }}
    >
      <div style={{ marginBottom: 8 }}>
        <button
          className="secondary"
          style={{ width: "100%", fontSize: 12 }}
          onClick={() => onSelect(null)}
        >
          ✨ Free mode (không bài)
        </button>
      </div>
      {Object.entries(byTheme).map(([theme, items]) => (
        <details key={theme} open={theme <= "C"}>
          <summary style={{ cursor: "pointer", fontWeight: 600, padding: "0.3rem 0" }}>
            {theme}. {themeName(theme)} ({items.length})
          </summary>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {items.map((e) => (
              <li key={e.exercise_id}>
                <button
                  onClick={() => onSelect(e)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    background:
                      selected === e.exercise_id ? "var(--accent-dim)" : "transparent",
                    color: "var(--text)",
                    padding: "0.4rem 0.5rem",
                    fontWeight: 400,
                    fontSize: 13,
                  }}
                >
                  <span style={{ fontWeight: 600 }}>{e.exercise_id}</span>{" "}
                  <span className="muted">L{e.level}</span>{" "}
                  {e.title}
                </button>
              </li>
            ))}
          </ul>
        </details>
      ))}
      {exercises.length === 0 && (
        <p className="muted">
          Chưa có bài tập. Import từ <code>learning.exercise</code> bảng hoặc xem{" "}
          <code>docs/exercises/</code> trên GitHub.
        </p>
      )}
    </div>
  );
}

function themeName(t: string): string {
  return (
    {
      A: "Revenue/GMV",
      B: "Customer lifecycle",
      C: "Campaign / Sale day",
      D: "Voucher",
      E: "Seller",
      F: "Product/Category",
      G: "Marketing/Ads",
      H: "Ops/Shipping",
      I: "Cancel/Return",
      J: "Customer Service",
      K: "Geographic",
      L: "Capstone",
    }[t] ?? t
  );
}
