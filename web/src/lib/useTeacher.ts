import { useEffect, useState } from "react";
import { supabase } from "../supabase";

// Module cache — 1 RPC call per session
let cached: boolean | null = null;
let inflight: Promise<boolean> | null = null;

async function check(): Promise<boolean> {
  if (cached !== null) return cached;
  if (!inflight) {
    inflight = (async () => {
      const { data, error } = await supabase.rpc("is_teacher");
      const val = !error && data === true;
      cached = val;
      return val;
    })();
  }
  return inflight;
}

export function useTeacher(): boolean {
  const [ok, setOk] = useState<boolean>(cached ?? false);
  useEffect(() => {
    if (cached !== null) {
      setOk(cached);
      return;
    }
    let live = true;
    check().then((v) => {
      if (live) setOk(v);
    });
    return () => {
      live = false;
    };
  }, []);
  return ok;
}
