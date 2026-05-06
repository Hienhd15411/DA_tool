import { useEffect, useRef } from "react";
import Editor from "@monaco-editor/react";
import type { editor } from "monaco-editor";

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
          renderWhitespace: "none",
          // ===== TẮT TẤT CẢ AUTOCOMPLETE / SUGGEST =====
          quickSuggestions: false,
          suggestOnTriggerCharacters: false,
          wordBasedSuggestions: "off",
          acceptSuggestionOnEnter: "off",
          acceptSuggestionOnCommitCharacter: false,
          tabCompletion: "off",
          parameterHints: { enabled: false },
          inlineSuggest: { enabled: false },
          snippetSuggestions: "none",
          suggest: {
            showWords: false,
            showSnippets: false,
            preview: false,
          },
          // ===== TẮT AUTO-FORMAT / AUTO-INSERT KHI GÕ =====
          // (autoClosingBrackets/Quotes thêm ký tự phụ → có thể gây nhảy với Telex VN)
          formatOnType: false,
          formatOnPaste: false,
          autoClosingBrackets: "never",
          autoClosingQuotes: "never",
          autoSurround: "never",
          autoIndent: "keep",
          // ===== TẮT VISUAL DISTRACTIONS =====
          hover: { enabled: false },
          links: false,
          occurrencesHighlight: "off",
          selectionHighlight: false,
          codeLens: false,
          contextmenu: false,
          cursorSmoothCaretAnimation: "off",
          smoothScrolling: false,
        }}
        onMount={(ed, monaco) => {
          ed.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => onRunRef.current());
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
        Ctrl/Cmd + Enter để chạy
      </div>
    </div>
  );
}
