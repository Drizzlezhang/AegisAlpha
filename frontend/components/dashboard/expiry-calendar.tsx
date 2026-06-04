"use client";

import LoadingSkeleton from "@/components/ui/loading-skeleton";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];
const EXPIRIES = [
  { month: "Jun", day: 20, count: 2, intensity: 0.8 },
  { month: "Sep", day: 19, count: 3, intensity: 0.9 },
  { month: "Dec", day: 19, count: 1, intensity: 0.4 },
  { month: "Jan", day: 16, count: 2, intensity: 0.7 },
  { month: "Mar", day: 19, count: 1, intensity: 0.5 },
];

function intensityColor(intensity: number): string {
  if (intensity >= 0.8) return "hsl(145, 65%, 45%)";
  if (intensity >= 0.5) return "hsl(145, 50%, 35%)";
  if (intensity >= 0.3) return "hsl(145, 30%, 25%)";
  return "var(--aegis-bg-elevated)";
}

export default function ExpiryCalendar() {
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
        Expiry Calendar
      </h3>

      <div className="grid grid-cols-6 gap-1">
        {MONTHS.map((month) => (
          <div
            key={month}
            className="text-xs text-center py-1"
            style={{ color: "var(--aegis-text-tertiary)" }}
          >
            {month}
          </div>
        ))}
        {EXPIRIES.map((exp) => (
          <div
            key={`${exp.month}-${exp.day}`}
            className="aspect-square rounded flex items-center justify-center text-xs font-medium transition-colors duration-150"
            style={{
              background: intensityColor(exp.intensity),
              color:
                exp.intensity >= 0.5
                  ? "var(--aegis-text-primary)"
                  : "var(--aegis-text-tertiary)",
            }}
            title={`${exp.month} ${exp.day}: ${exp.count} position(s)`}
          >
            {exp.day}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 mt-3">
        <span
          className="text-xs"
          style={{ color: "var(--aegis-text-tertiary)" }}
        >
          Low
        </span>
        <div className="flex gap-0.5">
          {[0.2, 0.4, 0.6, 0.8].map((i) => (
            <div
              key={i}
              className="w-4 h-3 rounded-sm"
              style={{ background: intensityColor(i) }}
            />
          ))}
        </div>
        <span
          className="text-xs"
          style={{ color: "var(--aegis-text-tertiary)" }}
        >
          High
        </span>
      </div>
    </div>
  );
}
