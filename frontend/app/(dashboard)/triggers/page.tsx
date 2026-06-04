"use client";

import useSWR from "swr";
import { fetcher, api } from "@/lib/api";
import type { Trigger } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";
import SignalBadge from "@/components/charts/signal-badge";
import LoadingSkeleton from "@/components/ui/loading-skeleton";
import EmptyState from "@/components/ui/empty-state";

const STATUS_SIGNAL: Record<string, "bull" | "bear" | "neutral" | "blocked"> = {
  pending: "neutral",
  triggered: "bull",
  expired: "neutral",
  cancelled: "bear",
};

export default function TriggersPage() {
  const { data, error, mutate } = useSWR<Trigger[]>("/triggers", fetcher);

  const handleCancel = async (id: number) => {
    try {
      await api.triggers.cancel(id);
      mutate();
    } catch {
      // silently fail
    }
  };

  return (
    <div className="p-4">
      <h2
        className="text-lg font-semibold mb-4"
        style={{ color: "var(--aegis-text-primary)" }}
      >
        Pending Triggers
      </h2>

      {error && (
        <p style={{ color: "var(--aegis-signal-bear)" }}>Failed to load triggers</p>
      )}
      {!data && !error && <LoadingSkeleton lines={3} />}
      {data && data.length === 0 && <EmptyState title="No pending triggers" />}

      {data && data.length > 0 && (
        <div
          className="rounded-lg border overflow-hidden"
          style={{
            background: "var(--aegis-bg-surface)",
            borderColor: "var(--aegis-border-default)",
          }}
        >
          <table className="w-full text-sm">
            <thead>
              <tr
                className="text-xs uppercase tracking-wider"
                style={{ background: "var(--aegis-bg-elevated)" }}
              >
                <th className="text-left py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Ticker</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Type</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Params</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Action</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Valid Until</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Status</th>
                <th className="text-right py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}></th>
              </tr>
            </thead>
            <tbody>
              {data.map((trigger) => (
                <tr
                  key={trigger.id}
                  className="border-t"
                  style={{ borderColor: "var(--aegis-border-subtle)" }}
                >
                  <td className="py-2 px-3 font-semibold" style={{ color: "var(--aegis-text-primary)" }}>
                    {trigger.ticker}
                  </td>
                  <td className="py-2 px-3" style={{ color: "var(--aegis-text-secondary)" }}>
                    {trigger.type}
                  </td>
                  <td className="py-2 px-3" style={{ color: "var(--aegis-text-secondary)" }}>
                    {JSON.stringify(trigger.params)}
                  </td>
                  <td className="py-2 px-3" style={{ color: "var(--aegis-text-secondary)" }}>
                    {trigger.suggested_action}
                  </td>
                  <td className="py-2 px-3 tabular-nums" style={{ color: "var(--aegis-text-tertiary)" }}>
                    {formatDateTime(trigger.valid_until)}
                  </td>
                  <td className="py-2 px-3">
                    <SignalBadge
                      signal={STATUS_SIGNAL[trigger.status] || "neutral"}
                      label={trigger.status}
                    />
                  </td>
                  <td className="py-2 px-3 text-right">
                    {trigger.status === "pending" && (
                      <button
                        onClick={() => handleCancel(trigger.id)}
                        className="text-xs px-2 py-1 rounded transition-colors duration-150"
                        style={{
                          color: "var(--aegis-signal-bear)",
                          background: "var(--aegis-signal-bear-bg)",
                        }}
                      >
                        Cancel
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
