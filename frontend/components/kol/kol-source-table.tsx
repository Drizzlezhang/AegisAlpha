"use client";

import { KOLSource } from "@/lib/api/kol";

interface Props {
  sources: KOLSource[];
}

function ReliabilityBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.7
      ? "var(--aegis-signal-bull)"
      : score >= 0.4
        ? "var(--aegis-signal-neutral)"
        : "var(--aegis-signal-bear)";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div
        style={{
          flex: 1,
          height: "6px",
          borderRadius: "3px",
          background: "var(--aegis-bg-elevated)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            borderRadius: "3px",
            background: color,
            width: `${pct}%`,
            transition: "width 150ms",
          }}
        />
      </div>
      <span style={{ fontSize: "13px", fontWeight: 500, color, minWidth: "36px" }}>
        {pct}%
      </span>
    </div>
  );
}

export function KOLSourceTable({ sources }: Props) {
  if (!sources.length) {
    return (
      <div
        style={{
          padding: "48px 32px",
          textAlign: "center",
          color: "var(--aegis-text-tertiary)",
          fontSize: "14px",
        }}
      >
        No KOL sources tracked yet
      </div>
    );
  }

  const thStyle: React.CSSProperties = {
    padding: "10px 16px",
    textAlign: "left",
    fontSize: "12px",
    fontWeight: 500,
    color: "var(--aegis-text-tertiary)",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  };

  const tdStyle: React.CSSProperties = {
    padding: "10px 16px",
    fontSize: "14px",
    color: "var(--aegis-text-primary)",
  };

  const platformLabel = (p: string) => {
    const labels: Record<string, string> = {
      x: "X",
      stocktwits: "StockTwits",
      reddit: "Reddit",
    };
    return labels[p] || p;
  };

  return (
    <div
      style={{
        borderRadius: "8px",
        border: "1px solid var(--aegis-border-default)",
        overflow: "hidden",
      }}
    >
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead style={{ background: "var(--aegis-bg-elevated)" }}>
          <tr>
            <th style={thStyle}>Name</th>
            <th style={thStyle}>Platform</th>
            <th style={thStyle}>Handle</th>
            <th style={thStyle}>Reliability</th>
            <th style={thStyle}>Calls</th>
            <th style={thStyle}>Success</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((s) => (
            <tr
              key={s.id}
              style={{
                borderTop: "1px solid var(--aegis-border-default)",
                transition: "background-color 150ms",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--aegis-bg-elevated)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              <td style={{ ...tdStyle, fontWeight: 500 }}>{s.name}</td>
              <td style={tdStyle}>
                <span
                  style={{
                    display: "inline-block",
                    padding: "2px 8px",
                    borderRadius: "4px",
                    fontSize: "12px",
                    color: "var(--aegis-text-secondary)",
                    background: "var(--aegis-bg-elevated)",
                    border: "1px solid var(--aegis-border-default)",
                  }}
                >
                  {platformLabel(s.platform)}
                </span>
              </td>
              <td style={{ ...tdStyle, fontFamily: "var(--aegis-font-mono)" }}>
                @{s.handle}
              </td>
              <td style={{ ...tdStyle, minWidth: "140px" }}>
                <ReliabilityBar score={s.reliability_score} />
              </td>
              <td style={tdStyle}>{s.total_calls}</td>
              <td style={tdStyle}>
                {s.total_calls > 0
                  ? `${Math.round((s.successful_calls / s.total_calls) * 100)}%`
                  : "\u2014"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}