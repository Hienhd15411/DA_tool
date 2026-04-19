import Editor from "@monaco-editor/react";

export function SqlEditor({
  value,
  onChange,
  onRun,
}: {
  value: string;
  onChange: (v: string) => void;
  onRun: () => void;
}) {
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
        }}
        onMount={(editor, monaco) => {
          editor.addCommand(
            monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
            onRun,
          );
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
