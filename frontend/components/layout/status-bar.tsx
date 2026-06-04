export default function StatusBar() {
  return (
    <footer
      className="flex items-center h-7 px-4 border-t shrink-0 gap-4"
      style={{
        background: "var(--aegis-bg-surface)",
        borderColor: "var(--aegis-border-default)",
      }}
    >
      <span
        className="text-xs"
        style={{ color: "var(--aegis-text-tertiary)" }}
      >
        Last Run: --
      </span>
      <span
        className="text-xs"
        style={{ color: "var(--aegis-text-tertiary)" }}
      >
        Errors: 0
      </span>
      <div className="flex-1" />
      <span
        className="text-xs"
        style={{ color: "var(--aegis-text-tertiary)" }}
      >
        v0.1.0
      </span>
    </footer>
  );
}
