"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { SmartMoneyData } from "@/lib/types";
import SignalBadge from "@/components/charts/signal-badge";
import LoadingSkeleton from "@/components/ui/loading-skeleton";

export default function SmartMoneyCard() {
  const { data, error } = useSWR<SmartMoneyData>(
    "/flows/smart-money/QQQ",
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
        Smart Money
      </h3>

      {error && (
        <p style={{ color: "var(--aegis-signal-bear)" }}>Failed to load</p>
      )}
      {!data && !error && <LoadingSkeleton lines={3} />}
      {data && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span
              className="text-sm font-semibold"
              style={{ color: "var(--aegis-text-primary)" }}
            >
              {data.ticker}
            </span>
            <SignalBadge
              signal={
                data.direction_bias === "bullish"
                  ? "bull"
                  : data.direction_bias === "bearish"
                  ? "bear"
                  : "neutral"
              }
            />
            <span
              className="text-xs tabular-nums ml-auto"
              style={{ color: "var(--aegis-text-secondary)" }}
            >
              Score: {data.smart_money_score}
            </span>
          </div>
          <div className="space-y-1">
            {data.unusual_options.slice(0, 5).map((opt, i) => (
              <div
                key={i}
                className="flex items-center gap-2 text-xs py-1 px-2 rounded"
                style={{ background: "var(--aegis-bg-base)" }}
              >
                <span
                  style={{
                    color:
                      opt.option_type === "call"
                        ? "var(--aegis-signal-bull)"
                        : "var(--aegis-signal-bear)",
                  }}
                >
                  {opt.option_type.toUpperCase()}
                </span>
                <span style={{ color: "var(--aegis-text-secondary)" }}>
                  ${opt.strike}
                </span>
                <span style={{ color: "var(--aegis-text-tertiary)" }}>
                  {opt.expiry.slice(0, 7)}
                </span>
                <span
                  className="tabular-nums ml-auto"
                  style={{
                    color:
                      opt.oi_change >= 0
                        ? "var(--aegis-signal-bull)"
                        : "var(--aegis-signal-bear)",
                  }}
                >
                  OI {opt.oi_change >= 0 ? "+" : ""}
                  {opt.oi_change}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
