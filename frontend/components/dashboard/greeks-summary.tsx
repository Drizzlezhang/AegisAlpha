"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { GreeksSummary as GreeksSummaryType } from "@/lib/types";
import LoadingSkeleton from "@/components/ui/loading-skeleton";

export default function GreeksSummary() {
  const { data, error } = useSWR<GreeksSummaryType>(
    "/portfolio/greeks",
    fetcher
  );

  const rows: { label: string; value: number; format: string }[] = data
    ? [
        { label: "Delta", value: data.total_delta, format: "num" },
        { label: "Gamma", value: data.total_gamma, format: "num" },
        { label: "Theta", value: data.total_theta, format: "num" },
        { label: "Vega", value: data.total_vega, format: "num" },
        { label: "Delta $", value: data.total_delta_dollars, format: "dd" },
      ]
    : [];

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
        Greeks Summary
      </h3>

      {error && (
        <p style={{ color: "var(--aegis-signal-bear)" }}>Failed to load</p>
      )}
      {!data && !error && <LoadingSkeleton lines={5} />}
      {data && (
        <table className="w-full text-sm">
          <thead>
            <tr
              className="text-xs uppercase tracking-wider"
              style={{ color: "var(--aegis-text-tertiary)" }}
            >
              <th className="text-left py-1 font-medium">Greek</th>
              <th className="text-right py-1 font-medium">Value</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.label}
                className="border-t"
                style={{ borderColor: "var(--aegis-border-subtle)" }}
              >
                <td
                  className="py-1.5"
                  style={{ color: "var(--aegis-text-secondary)" }}
                >
                  {row.label}
                </td>
                <td
                  className="py-1.5 text-right tabular-nums"
                  style={{
                    color:
                      row.value >= 0
                        ? "var(--aegis-signal-bull)"
                        : "var(--aegis-signal-bear)",
                  }}
                >
                  {row.format === "dd"
                    ? `$${row.value.toLocaleString()}`
                    : row.value.toFixed(3)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
