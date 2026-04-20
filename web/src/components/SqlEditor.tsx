import { useEffect, useRef } from "react";
import Editor from "@monaco-editor/react";
import type { editor, languages } from "monaco-editor";
import { useSchema } from "../lib/useSchema";

export function SqlEditor({
  value,
  onChange,
  onRun,
  onReady,
}: {
  value: string;
  onChange: (v: string) => void;
  onRun: () => void;
  onReady?: (ed: editor.IStandaloneCodeEditor) => void;
}) {
  const onRunRef = useRef(onRun);
  useEffect(() => {
    onRunRef.current = onRun;
  }, [onRun]);

  const { tables } = useSchema();
  const tablesRef = useRef(tables);
  useEffect(() => {
    tablesRef.current = tables;
  }, [tables]);

  return (
    <div style={{ height: "100%", position: "relative" }}>
      <Editor
        height="100%"
        language="sql"
        theme="vs-dark"
        value={value}
        onChange={(v) => onChange(v ?? "")}
        options={{
          fontSize: 14,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          automaticLayout: true,
          wordWrap: "on",
          tabSize: 2,
          quickSuggestions: { other: true, comments: false, strings: false },
          suggestOnTriggerCharacters: true,
        }}
        onMount={(ed, monaco) => {
          ed.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => onRunRef.current());

          // Completion: tables + columns từ schema shopee
          const provider = monaco.languages.registerCompletionItemProvider("sql", {
            triggerCharacters: [" ", ".", ",", "\n", "("],
            provideCompletionItems: (model, position) => {
              const word = model.getWordUntilPosition(position);
              const range = {
                startLineNumber: position.lineNumber,
                endLineNumber: position.lineNumber,
                startColumn: word.startColumn,
                endColumn: word.endColumn,
              };
              const suggestions: languages.CompletionItem[] = [];
              const tables = tablesRef.current ?? [];
              const seenCols = new Set<string>();

              for (const t of tables) {
                suggestions.push({
                  label: `shopee.${t.table_name}`,
                  kind: monaco.languages.CompletionItemKind.Struct,
                  insertText: `shopee.${t.table_name}`,
                  detail: `${t.group} table · ${t.row_count.toLocaleString()} rows`,
                  range,
                });
                suggestions.push({
                  label: t.table_name,
                  kind: monaco.languages.CompletionItemKind.Struct,
                  insertText: t.table_name,
                  detail: `${t.group} table · ${t.row_count.toLocaleString()} rows`,
                  range,
                });
                for (const c of t.columns) {
                  const key = `${c.name}::${t.table_name}`;
                  if (seenCols.has(key)) continue;
                  seenCols.add(key);
                  suggestions.push({
                    label: c.name,
                    kind: monaco.languages.CompletionItemKind.Field,
                    insertText: c.name,
                    detail: `${c.type} · ${t.table_name}${c.nullable ? "" : " · NOT NULL"}`,
                    range,
                  });
                }
              }
              // SQL keyword snippets hay dùng (Monaco default đã có keywords cơ bản)
              const snippets: { label: string; insertText: string; detail: string }[] = [
                { label: "SELECT …",    insertText: "SELECT $0\nFROM ", detail: "SELECT FROM skeleton" },
                { label: "JOIN …",      insertText: "JOIN ${1:table} ${2:t} ON ${2:t}.${3:col} = ${0}", detail: "INNER JOIN" },
                { label: "LEFT JOIN …", insertText: "LEFT JOIN ${1:table} ${2:t} ON ${2:t}.${3:col} = ${0}", detail: "LEFT JOIN" },
                { label: "GROUP BY …",  insertText: "GROUP BY ${0}", detail: "GROUP BY" },
                { label: "ORDER BY …",  insertText: "ORDER BY ${1:col} ${2|ASC,DESC|}", detail: "ORDER BY" },
                { label: "WITH CTE …",  insertText: "WITH ${1:cte_name} AS (\n  SELECT ${2}\n  FROM ${3}\n)\nSELECT $0\nFROM ${1:cte_name}", detail: "CTE skeleton" },
                { label: "DATE_TRUNC", insertText: "DATE_TRUNC('${1|day,week,month,quarter,year|}', ${0})", detail: "Truncate date" },
              ];
              for (const s of snippets) {
                suggestions.push({
                  label: s.label,
                  kind: monaco.languages.CompletionItemKind.Snippet,
                  insertText: s.insertText,
                  insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
                  detail: s.detail,
                  range,
                });
              }
              return { suggestions };
            },
          });

          // Dispose provider khi editor unmount
          ed.onDidDispose(() => provider.dispose());

          onReady?.(ed);
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 8,
          right: 12,
          fontSize: 11,
          color: "var(--text-dim)",
          background: "rgba(0,0,0,0.5)",
          padding: "2px 6px",
          borderRadius: 4,
        }}
      >
        Ctrl/Cmd + Enter để chạy · Ctrl+Space để gợi ý
      </div>
    </div>
  );
}
