export default function LeftPanel() {
  return (
    <aside
      className="w-[280px] xl:w-[280px] lg:w-[240px] shrink-0 border-r overflow-y-auto p-4 flex-col gap-4 hidden md:flex"
      style={{
        background: "var(--aegis-bg-surface)",
        borderColor: "var(--aegis-border-default)",
      }}
    >
      {/* Holdings */}
      <section>
        <h3
          className="text-xs uppercase tracking-wider mb-2"
          style={{ color: "var(--aegis-text-tertiary)" }}
        >
          Holdings
        </h3>
        <div
          className="text-sm"
          style={{ color: "var(--aegis-text-secondary)" }}
        >
          No holdings loaded
        </div>
      </section>

      {/* Watchlist */}
      <section>
        <h3
          className="text-xs uppercase tracking-wider mb-2"
          style={{ color: "var(--aegis-text-tertiary)" }}
        >
          Watch
        </h3>
        <div
          className="text-sm"
          style={{ color: "var(--aegis-text-secondary)" }}
        >
          No watchlist items
        </div>
      </section>

      {/* Thesis */}
      <section>
        <h3
          className="text-xs uppercase tracking-wider mb-2"
          style={{ color: "var(--aegis-text-tertiary)" }}
        >
          Thesis
        </h3>
        <div
          className="text-sm"
          style={{ color: "var(--aegis-text-secondary)" }}
        >
          No active thesis cards
        </div>
      </section>
    </aside>
  );
}
