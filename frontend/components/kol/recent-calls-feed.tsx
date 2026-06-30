"use client";

import { KOLCall } from "@/lib/api/kol";
import { formatDate } from "@/lib/utils";

interface Props {
  calls: KOLCall[];
}

export function RecentCallsFeed({ calls }: Props) {
  if (!calls.length) {
    return (
      <div
        style={{
          padding: "32px",
          textAlign: "center",
          color: "var(--aegis-text-tertiary)",
          fontSize: "14px",
        }}
      >
        No recent calls
      </div>
    );
  }

  return (
    <div style={{ maxHeight: "320px", overflowY: "auto" }}>
      {calls.map((call) => {
        const statusColor =
          call.attribution_status === "validated"
            ? "var(--aegis-signal-bull)"
            : call.attribution_status === "invalidated"
              ? "var(--aegis-signal-bear)"
              : "var(--aegis-signal-neutral)";

        return (
          <div
            key={call.id}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "10px",
              padding: "10px 12px",
              borderBottom: "1px solid var(--aegis-border-subtle)",
              transition: "background-color 150ms",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--aegis-bg-elevated)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            {/* Direction indicator */}
            <div
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: statusColor,
                flexShrink: 0,
                marginTop: "5px",
              }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  marginBottom: "2px",
                }}
              >
                <span
                  style={{
                    fontFamily: "var(--aegis-font-mono)",
                    fontWeight: 600,
                    fontSize: "14px",
                    color: "var(--aegis-text-primary)",
                  }}
                >
                  {call.ticker}
                </span>
                <span
                  style={{
                    fontSize: "12px",
                    color:
                      call.direction === "long"
                        ? "var(--aegis-signal-bull)"
                        : "var(--aegis-signal-bear)",
                  }}
                >
                  {call.direction.toUpperCase()}
                </span>
              </div>
              <div
                style={{
                  fontSize: "12px",
                  color: "var(--aegis-text-tertiary)",
                }}
              >
                {call.call_date ? formatDate(call.call_date) : "Unknown date"}
                {call.call_price ? ` @ $${call.call_price}` : ""}
              </div>
              {call.content_snippet && (
                <div
                  style={{
                    fontSize: "12px",
                    color: "var(--aegis-text-secondary)",
                    marginTop: "4px",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {call.content_snippet}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}