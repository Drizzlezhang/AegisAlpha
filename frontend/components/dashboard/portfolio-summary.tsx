import type { PortfolioSnapshot } from "@/lib/types";
import { formatPrice, formatPercent, formatDeltaDollars } from "@/lib/utils";
import LoadingSkeleton from "@/components/ui/loading-skeleton";

interface Props {
  data?: PortfolioSnapshot | null;
}

export default function PortfolioSummary({ data }: Props) {
  if (!data) return <LoadingSkeleton lines={1} />;

  return (
    <div
      className="rounded-lg border p-4"
      style={{
        background: "var(--aegis-bg-surface)",
        borderColor: "var(--aegis-border-default)",
      }}
    >
      <div className="grid grid-cols-4 gap-6">
        <div>
          <p
            className="text-xs uppercase tracking-wider mb-1"
            style={{ color: "var(--aegis-text-tertiary)" }}
          >
            Total NAV
          </p>
          <p
            className="text-2xl font-bold tabular-nums"
            style={{ color: "var(--aegis-text-primary)" }}
          >
            {formatPrice(data.total_nav, 0)}
          </p>
        </div>
        <div>
          <p
            className="text-xs uppercase tracking-wider mb-1"
            style={{ color: "var(--aegis-text-tertiary)" }}
          >
            Daily P&L
          </p>
          <p
            className="text-2xl font-bold tabular-nums"
            style={{
              color:
                data.daily_pnl >= 0
                  ? "var(--aegis-signal-bull)"
                  : "var(--aegis-signal-bear)",
            }}
          >
            {formatPrice(data.daily_pnl, 0)} ({formatPercent(data.daily_pnl_pct)})
          </p>
        </div>
        <div>
          <p
            className="text-xs uppercase tracking-wider mb-1"
            style={{ color: "var(--aegis-text-tertiary)" }}
          >
            Delta $
          </p>
          <p
            className="text-2xl font-bold tabular-nums"
            style={{ color: "var(--aegis-text-primary)" }}
          >
            {formatDeltaDollars(data.delta_dollars)}
          </p>
        </div>
        <div>
          <p
            className="text-xs uppercase tracking-wider mb-1"
            style={{ color: "var(--aegis-text-tertiary)" }}
          >
            Cash Ratio
          </p>
          <p
            className="text-2xl font-bold tabular-nums"
            style={{ color: "var(--aegis-text-primary)" }}
          >
            {data.cash_ratio.toFixed(1)}%
          </p>
        </div>
      </div>
    </div>
  );
}
