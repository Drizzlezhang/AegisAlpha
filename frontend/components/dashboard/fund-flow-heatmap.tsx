"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { SectorFlow } from "@/lib/types";
import LoadingSkeleton from "@/components/ui/loading-skeleton";

function flowColor(intensity: number): string {
  if (intensity >= 0.6) return "hsl(145, 60%, 40%)";
  if (intensity >= 0.2) return "hsl(145, 40%, 30%)";
  if (intensity >= -0.2) return "var(--aegis-bg-elevated)";
  if (intensity >= -0.6) return "hsl(0, 40%, 30%)";
  return "hsl(0, 60%, 40%)";
}

export default function FundFlowHeatmap() {
  const { data, error } = useSWR<SectorFlow[]>(
    "/flows/sector",
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
        Fund Flow Heatmap
      </h3>

      {error && (
        <p style={{ color: "var(--aegis-signal-bear)" }}>Failed to load</p>
      )}
      {!data && !error && <LoadingSkeleton lines={4} />}
      {data && (
        <div className="grid grid-cols-2 gap-1.5">
          {data.map((sector) => (
            <div
              key={sector.sector}
              className="flex items-center justify-between p-2 rounded text-xs"
              style={{ background: flowColor(sector.intensity) }}
            >
              <span
                style={{
                  color:
                    Math.abs(sector.intensity) >= 0.4
                      ? "var(--aegis-text-primary)"
                      : "var(--aegis-text-secondary)",
                }}
              >
                {sector.sector}
              </span>
              <span
                className="tabular-nums"
                style={{
                  color:
                    sector.flow_7d >= 0
                      ? "var(--aegis-signal-bull)"
                      : "var(--aegis-signal-bear)",
                }}
              >
                {sector.flow_7d >= 0 ? "+" : ""}
                {(sector.flow_7d / 1_000_000).toFixed(0)}M
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
