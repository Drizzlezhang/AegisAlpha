export default function RightPanel() {
  return (
    <aside
      className="w-[320px] xl:w-[320px] lg:w-[280px] shrink-0 border-l overflow-y-auto p-4 flex-col gap-4 hidden lg:flex"
      style={{
        background: "var(--aegis-bg-surface)",
        borderColor: "var(--aegis-border-default)",
      }}
    >
      {/* Signal Log */}
      <section>
        <h3
          className="text-xs uppercase tracking-wider mb-2"
          style={{ color: "var(--aegis-text-tertiary)" }}
        >
          Signal Log
        </h3>
        <div
          className="text-sm"
          style={{ color: "var(--aegis-text-secondary)" }}
        >
          No recent signals
        </div>
      </section>

      {/* Agent Runs */}
      <section>
        <h3
          className="text-xs uppercase tracking-wider mb-2"
          style={{ color: "var(--aegis-text-tertiary)" }}
        >
          Agent Runs
        </h3>
        <div
          className="text-sm"
          style={{ color: "var(--aegis-text-secondary)" }}
        >
          No recent runs
        </div>
      </section>

      {/* Triggers */}
      <section>
        <h3
          className="text-xs uppercase tracking-wider mb-2"
          style={{ color: "var(--aegis-text-tertiary)" }}
        >
          Triggers
        </h3>
        <div
          className="text-sm"
          style={{ color: "var(--aegis-text-secondary)" }}
        >
          No pending triggers
        </div>
      </section>
    </aside>
  );
}
