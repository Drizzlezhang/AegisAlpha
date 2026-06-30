"use client";

import { CheckCircle2, XCircle } from "lucide-react";

interface Props {
  assumptions: string[];
}

export function AssumptionChecklist({ assumptions }: Props) {
  if (!assumptions.length) {
    return (
      <p style={{ color: "var(--aegis-text-tertiary)", fontSize: "14px" }}>
        No assumptions recorded
      </p>
    );
  }

  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {assumptions.map((assumption, i) => {
        const isBroken = assumption.startsWith("[BROKEN]");
        const displayText = isBroken
          ? assumption.replace("[BROKEN] ", "")
          : assumption;
        const iconColor = isBroken
          ? "var(--aegis-signal-bear)"
          : "var(--aegis-signal-bull)";

        return (
          <li
            key={i}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "8px",
              padding: "8px",
              borderRadius: "6px",
              background: "var(--aegis-bg-elevated)",
              marginBottom: "6px",
            }}
          >
            {isBroken ? (
              <XCircle
                size={18}
                style={{ color: iconColor, flexShrink: 0, marginTop: 2 }}
              />
            ) : (
              <CheckCircle2
                size={18}
                style={{ color: iconColor, flexShrink: 0, marginTop: 2 }}
              />
            )}
            <span
              style={{
                color: isBroken
                  ? "var(--aegis-text-tertiary)"
                  : "var(--aegis-text-secondary)",
                fontSize: "14px",
                textDecoration: isBroken ? "line-through" : "none",
              }}
            >
              {displayText}
            </span>
          </li>
        );
      })}
    </ul>
  );
}