"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { Recommendation } from "@/lib/types";
import SignalBadge from "@/components/charts/signal-badge";
import EntryModeBadge from "@/components/charts/entry-mode-badge";
import LoadingSkeleton from "@/components/ui/loading-skeleton";
import EmptyState from "@/components/ui/empty-state";

export default function RecommendationFeed() {
  const [tab, setTab] = useState<"pre" | "post">("pre");
  const { data, error } = useSWR<Recommendation[]>(
    "/recommendations",
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
      <div className="flex items-center justify-between mb-3">
        <h3
          className="text-sm font-medium"
          style={{ color: "var(--aegis-text-primary)" }}
        >
          Recommendations
        </h3>
        <div className="flex gap-1">
          {(["pre", "post"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="px-2 py-0.5 text-xs rounded transition-colors duration-150"
              style={{
                color:
                  tab === t
                    ? "var(--aegis-text-primary)"
                    : "var(--aegis-text-secondary)",
                background:
                  tab === t
                    ? "var(--aegis-bg-elevated)"
                    : "transparent",
              }}
            >
              {t === "pre" ? "Pre-Market" : "Post-Market"}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p style={{ color: "var(--aegis-signal-bear)" }}>Failed to load</p>
      )}
      {!data && !error && <LoadingSkeleton lines={3} />}
      {data && data.length === 0 && <EmptyState title="No recommendations yet" />}
      {data && data.length > 0 && (
        <div className="space-y-2">
          {data.slice(0, 3).map((rec) => (
            <div
              key={rec.id}
              className="flex items-center gap-3 p-2 rounded-md transition-colors duration-150"
              style={{ background: "var(--aegis-bg-base)" }}
            >
              <span
                className="text-sm font-semibold tabular-nums"
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
                className="text-xs tabular-nums ml-auto"
                style={{ color: "var(--aegis-text-secondary)" }}
              >
                Score: {rec.score.toFixed(1)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
