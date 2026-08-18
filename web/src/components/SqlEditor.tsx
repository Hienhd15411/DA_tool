import { useEffect, useRef } from "react";
import Editor from "@monaco-editor/react";
import type { editor } from "monaco-editor";

/**
 * UNCONTROLLED Monaco — không truyền `value` prop (tránh round-trip
 * React re-render → setValue → nhảy chữ khi gõ nhanh / gõ Telex VN).
 *
 * - Monaco tự own text buffer.
 * - `tabId` đổi (user switch tab) → mới setValue lại nội dung tab đó.
 * - `onChange` vẫn fire để App lưu state (persistence) — nhưng KHÔNG
 *   feed ngược lại làm value prop.
 * - App đọc nội dung live qua editor ref (onReady) khi Run / Format.
 */
export function SqlEditor({
  tabId,
  initialValue,
  onChange,
  onRun,
  onReady,
}: {
  tabId: string;
  initialValue: string;
  onChange: (v: string) => void;
  onRun: () => void;
  onReady?: (ed: editor.IStandaloneCodeEditor) => void;
}) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const onRunRef = useRef(onRun);
  useEffect(() => {
    onRunRef.current = onRun;
  }, [onRun]);

  // Chỉ sync nội dung vào editor khi ĐỔI TAB (tabId thay đổi),
  // KHÔNG sync theo initialValue (tránh disrupt khi đang gõ).
  useEffect(() => {
    const ed = editorRef.current;
    if (ed && ed.getValue() !== initialValue) {
      ed.setValue(initialValue);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tabId]);

  return (
    <div style={{ height: "100%", position: "relative" }}>
      <Editor
        height="100%"
        language="sql"
        theme="vs-dark"
        defaultValue={initialValue}
        onChange={(v) => onChange(v ?? "")}
        options={{
          fontSize: 14,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          automaticLayout: true,
          wordWrap: "on",
          tabSize: 2,
          renderWhitespace: "none",
          // Tắt autocomplete / suggest
          quickSuggestions: false,
          suggestOnTriggerCharacters: false,
          wordBasedSuggestions: "off",
          acceptSuggestionOnEnter: "off",
          acceptSuggestionOnCommitCharacter: false,
          tabCompletion: "off",
          parameterHints: { enabled: false },
          inlineSuggest: { enabled: false },
          snippetSuggestions: "none",
          suggest: { showWords: false, showSnippets: false, preview: false },
          // Tắt auto-insert / auto-format khi gõ
          formatOnType: false,
          formatOnPaste: false,
          autoClosingBrackets: "never",
          autoClosingQuotes: "never",
          autoSurround: "never",
          autoIndent: "keep",
          // Tắt visual distractions
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
          editorRef.current = ed;
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
