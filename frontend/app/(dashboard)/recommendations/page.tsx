"use client";

import Link from "next/link";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { Recommendation } from "@/lib/types";
import SignalBadge from "@/components/charts/signal-badge";
import EntryModeBadge from "@/components/charts/entry-mode-badge";
import LoadingSkeleton from "@/components/ui/loading-skeleton";
import EmptyState from "@/components/ui/empty-state";

export default function RecommendationsPage() {
  const { data, error } = useSWR<Recommendation[]>("/recommendations", fetcher);

  return (
    <div className="p-4">
      <h2
        className="text-lg font-semibold mb-4"
        style={{ color: "var(--aegis-text-primary)" }}
      >
        Recommendations
      </h2>

      {error && (
        <p style={{ color: "var(--aegis-signal-bear)" }}>Failed to load recommendations</p>
      )}
      {!data && !error && <LoadingSkeleton lines={3} />}
      {data && data.length === 0 && <EmptyState title="No recommendations yet" />}

      {data && data.length > 0 && (
        <div className="space-y-3">
          {data.map((rec) => (
            <Link
              key={rec.id}
              href={`/recommendations/${rec.id}`}
              className="block rounded-lg border p-4 transition-colors duration-150"
              style={{
                background: "var(--aegis-bg-surface)",
                borderColor: "var(--aegis-border-default)",
                borderLeftWidth: 2,
                borderLeftColor:
                  rec.direction === "bullish"
                    ? "var(--aegis-signal-bull)"
                    : rec.direction === "bearish"
                    ? "var(--aegis-signal-bear)"
                    : "var(--aegis-signal-neutral)",
              }}
            >
              <div className="flex items-center gap-3 mb-2">
                <span
                  className="text-base font-semibold"
                  style={{ color: "var(--aegis-text-primary)" }}
                >
                  {rec.ticker}
                </span>
                <SignalBadge
                  signal={
                    rec.direction === "bullish"
                      ? "bull"
                      : rec.direction === "bearish"
                      ? "bear"
                      : "neutral"
                  }
                />
                <EntryModeBadge mode={rec.entry_mode} />
                <span
                  className="text-xs px-2 py-0.5 rounded"
                  style={{
                    color: "var(--aegis-text-primary)",
                    background: "var(--aegis-bg-elevated)",
                  }}
                >
                  {rec.strategy}
                </span>
                <div className="flex-1" />
                <span
                  className="text-xs"
                  style={{ color: "var(--aegis-text-tertiary)" }}
                >
                  Score:{" "}
                  <span
                    className="font-semibold tabular-nums"
                    style={{
                      color:
                        rec.score >= 7
                          ? "var(--aegis-signal-bull)"
                          : rec.score >= 4
                          ? "var(--aegis-signal-neutral)"
                          : "var(--aegis-signal-bear)",
                    }}
                  >
                    {rec.score.toFixed(1)}
                  </span>
                </span>
              </div>
              <p
                className="text-sm line-clamp-2"
                style={{ color: "var(--aegis-text-secondary)" }}
              >
                {rec.rationale}
              </p>
              <div className="flex items-center gap-2 mt-2">
                <span
                  className="text-xs"
                  style={{
                    color:
                      rec.urgency === "high"
                        ? "var(--aegis-signal-bear)"
                        : rec.urgency === "medium"
                        ? "var(--aegis-signal-neutral)"
                        : "var(--aegis-text-tertiary)",
                  }}
                >
                  {rec.urgency.toUpperCase()}
                </span>
                {rec.risk_gate_status === "blocked" && (
                  <span
                    className="text-xs px-2 py-0.5 rounded"
                    style={{
                      color: "var(--aegis-signal-blocked)",
                      background: "var(--aegis-signal-blocked-bg)",
                    }}
                  >
                    BLOCKED
                  </span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
