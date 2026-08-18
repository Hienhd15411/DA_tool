import { useEffect, useState } from "react";
import { supabase } from "../supabase";

export type SchemaColumn = { name: string; type: string; nullable: boolean; position: number };
export type SchemaTable = {
  table_name: string;
  group: "dim" | "fact" | "other";
  row_count: number;
  columns: SchemaColumn[];
};

// Module-level cache: fetch 1 lần cho cả session, share giữa SchemaBrowser + SqlEditor.
let cached: SchemaTable[] | null = null;
let inflight: Promise<SchemaTable[]> | null = null;
const listeners = new Set<(t: SchemaTable[]) => void>();

async function load(): Promise<SchemaTable[]> {
  if (cached) return cached;
  if (!inflight) {
    inflight = (async () => {
      const { data, error } = await supabase.rpc("get_schema_info");
      if (error) throw new Error(error.message);
      const next = (data ?? []) as SchemaTable[];
      cached = next;
      listeners.forEach((fn) => fn(next));
      return next;
    })();
  }
  return inflight;
}

export function useSchema(): { tables: SchemaTable[] | null; error: string | null } {
  const [tables, setTables] = useState<SchemaTable[] | null>(cached);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (cached) {
      setTables(cached);
      return;
    }
    const onUpdate = (t: SchemaTable[]) => setTables(t);
    listeners.add(onUpdate);
    load().catch((e) => setError(e.message ?? String(e)));
    return () => {
      listeners.delete(onUpdate);
    };
  }, []);

  return { tables, error };
}
