"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { HealthScore } from "@/lib/types";
import LoadingSkeleton from "@/components/ui/loading-skeleton";
import EmptyState from "@/components/ui/empty-state";

function healthColor(score: number): string {
  if (score >= 80) return "var(--aegis-signal-bull)";
  if (score >= 60) return "var(--aegis-signal-neutral)";
  return "var(--aegis-signal-bear)";
}

export default function HealthPanel() {
  const { data, error } = useSWR<HealthScore[]>(
    "/portfolio/health",
    fetcher
  );

  return (
    <div
      className="rounded-lg border p-4"
      style={{
        background: "var(--aegis-bg-surface)",
        borderColor: "var(--aegis-border-default)",
      }}
    >
      <h3
        className="text-sm font-medium mb-3"
        style={{ color: "var(--aegis-text-primary)" }}
      >
        Health Scores
      </h3>

      {error && (
        <p style={{ color: "var(--aegis-signal-bear)" }}>Failed to load</p>
      )}
      {!data && !error && <LoadingSkeleton lines={3} />}
      {data && data.length === 0 && <EmptyState title="No positions" />}
      {data && data.length > 0 && (
        <div className="space-y-2">
          {data
            .sort((a, b) => b.score - a.score)
            .map((item) => (
              <div
                key={item.ticker}
                className="flex items-center gap-3 p-2 rounded"
                style={{ background: "var(--aegis-bg-base)" }}
              >
                <span
                  className="text-sm font-semibold"
                  style={{ color: "var(--aegis-text-primary)" }}
                >
                  {item.ticker}
                </span>
                <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: "var(--aegis-bg-elevated)" }}>
                  <div
                    className="h-full rounded-full transition-all duration-150"
                    style={{
                      width: `${item.score}%`,
                      background: healthColor(item.score),
                    }}
                  />
                </div>
                <span
                  className="text-xs tabular-nums font-medium w-8 text-right"
                  style={{ color: healthColor(item.score) }}
                >
                  {item.score}
                </span>
                {item.alerts.length > 0 && (
                  <span
                    className="text-xs"
                    style={{ color: "var(--aegis-signal-bear)" }}
                    title={item.alerts.join(", ")}
                  >
                    ⚠
                  </span>
                )}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
