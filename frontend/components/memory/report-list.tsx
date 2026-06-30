"use client";

import { ReportMeta } from "@/lib/api/reports";
import { formatDate } from "@/lib/utils";

interface Props {
  reports: ReportMeta[];
  onSelect: (report: ReportMeta) => void;
}

export function ReportList({ reports, onSelect }: Props) {
  if (!reports.length) {
    return (
      <div
        style={{
          padding: "48px 32px",
          textAlign: "center",
          color: "var(--aegis-text-tertiary)",
          fontSize: "14px",
        }}
      >
        No reports generated yet
      </div>
    );
  }

  return (
    <div style={{ maxHeight: "400px", overflowY: "auto" }}>
      {reports.map((report, i) => {
        const isWeekly = report.type === "weekly";
        const accentColor = isWeekly
          ? "var(--aegis-brand)"
          : "var(--aegis-signal-neutral)";

        return (
          <div
            key={`${report.type}-${report.date}`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              padding: "12px 16px",
              borderBottom: "1px solid var(--aegis-border-subtle)",
              cursor: "pointer",
              transition: "background-color 150ms",
            }}
            onClick={() => onSelect(report)}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--aegis-bg-elevated)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            {/* Type badge */}
            <span
              style={{
                display: "inline-block",
                padding: "3px 10px",
                borderRadius: "4px",
                fontSize: "11px",
                fontWeight: 600,
                textTransform: "uppercase",
                color: accentColor,
                background: isWeekly
                  ? "var(--aegis-brand-muted)"
                  : "var(--aegis-signal-neutral-bg)",
                flexShrink: 0,
              }}
            >
              {report.type}
            </span>
            <div style={{ flex: 1 }}>
              <div
                style={{
                  fontSize: "14px",
                  fontWeight: 500,
                  color: "var(--aegis-text-primary)",
                }}
              >
                {report.type === "weekly" ? "Weekly" : "Monthly"} Report
              </div>
              <div
                style={{
                  fontSize: "12px",
                  color: "var(--aegis-text-tertiary)",
                  marginTop: "2px",
                }}
              >
                {report.period.start} \u2192 {report.period.end}
              </div>
            </div>
            <span
              style={{
                fontSize: "12px",
                color: "var(--aegis-text-tertiary)",
              }}
            >
              {report.date}
            </span>
          </div>
        );
      })}
    </div>
  );
}