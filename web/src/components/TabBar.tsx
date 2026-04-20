export type QueryTab = {
  id: string;
  title: string;
  sql: string;
};

export function TabBar({
  tabs,
  activeId,
  onSelect,
  onClose,
  onAdd,
  onRename,
}: {
  tabs: QueryTab[];
  activeId: string;
  onSelect: (id: string) => void;
  onClose: (id: string) => void;
  onAdd: () => void;
  onRename: (id: string, title: string) => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "stretch",
        gap: 2,
        padding: "4px 6px 0 6px",
        background: "var(--bg)",
        borderBottom: "1px solid var(--border)",
        overflowX: "auto",
      }}
    >
      {tabs.map((t) => {
        const active = t.id === activeId;
        return (
          <div
            key={t.id}
            onClick={() => onSelect(t.id)}
            onDoubleClick={() => {
              const next = prompt("Đổi tên tab:", t.title);
              if (next && next.trim()) onRename(t.id, next.trim().slice(0, 40));
            }}
            title="Click để mở · double-click để đổi tên"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 10px",
              background: active ? "var(--panel)" : "transparent",
              borderTop: active ? "2px solid var(--accent)" : "2px solid transparent",
              borderLeft: "1px solid var(--border)",
              borderRight: "1px solid var(--border)",
              borderTopLeftRadius: 4,
              borderTopRightRadius: 4,
              fontSize: 12,
              fontWeight: active ? 600 : 400,
              color: active ? "var(--text)" : "var(--text-dim)",
              cursor: "pointer",
              userSelect: "none",
              whiteSpace: "nowrap",
              maxWidth: 200,
            }}
          >
            <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{t.title}</span>
            {tabs.length > 1 && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm(`Đóng tab "${t.title}"?`)) onClose(t.id);
                }}
                title="Đóng tab"
                style={{
                  background: "transparent",
                  color: "var(--text-dim)",
                  border: "none",
                  padding: "0 4px",
                  fontSize: 14,
                  lineHeight: 1,
                  cursor: "pointer",
                }}
              >
                ×
              </button>
            )}
          </div>
        );
      })}
      <button
        onClick={onAdd}
        title="Tab mới (không mất query hiện tại)"
        className="secondary"
        style={{
          padding: "4px 10px",
          fontSize: 14,
          fontWeight: 600,
          alignSelf: "flex-end",
          marginBottom: 1,
        }}
      >
        + Tab
      </button>
    </div>
  );
}
