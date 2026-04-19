import { supabase } from "../supabase";

export type RunSqlResult =
  | {
      status: "ok";
      rows: Record<string, unknown>[];
      row_count: number;
      exec_ms: number;
      truncated: boolean;
    }
  | {
      status: "error";
      error_code: string;
      error_message: string;
      exec_ms: number;
    };

export async function runSql(
  sql: string,
  exerciseId: string | null = null,
): Promise<RunSqlResult> {
  const { data, error } = await supabase.rpc("run_sql", {
    query_text: sql,
    exercise_id_in: exerciseId,
  });

  if (error) {
    return {
      status: "error",
      error_code: "CLIENT_ERROR",
      error_message: error.message,
      exec_ms: 0,
    };
  }
  return data as RunSqlResult;
}
