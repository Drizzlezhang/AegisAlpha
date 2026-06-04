export const SIGNAL_COLORS = {
  bull: "var(--aegis-signal-bull)",
  bear: "var(--aegis-signal-bear)",
  neutral: "var(--aegis-signal-neutral)",
  blocked: "var(--aegis-signal-blocked)",
} as const;

export const SIGNAL_BG_COLORS = {
  bull: "var(--aegis-signal-bull-bg)",
  bear: "var(--aegis-signal-bear-bg)",
  neutral: "var(--aegis-signal-neutral-bg)",
  blocked: "var(--aegis-signal-blocked-bg)",
} as const;

export const CHART_COLORS = {
  price: "hsl(210, 100%, 56%)",
  volume: "hsl(200, 60%, 50%)",
  iv: "hsl(35, 80%, 55%)",
  positive: "hsl(145, 65%, 50%)",
  negative: "hsl(0, 75%, 60%)",
  threshold: "hsl(0, 0%, 42%)",
} as const;

export const AGENT_STATUS_COLORS = {
  running: "var(--aegis-brand)",
  done: "var(--aegis-signal-bull)",
  error: "var(--aegis-signal-bear)",
  skipped: "var(--aegis-text-tertiary)",
} as const;

export type SignalType = "bull" | "bear" | "neutral" | "blocked";
export type EntryMode =
  | "active_left"
  | "active_right"
  | "passive"
  | "cc"
  | "sell_put";

export function signalToColor(signal: SignalType): string {
  return SIGNAL_COLORS[signal];
}

export function signalToBgColor(signal: SignalType): string {
  return SIGNAL_BG_COLORS[signal];
}

export function entryModeLabel(mode: EntryMode): string {
  const labels: Record<EntryMode, string> = {
    active_left: "Left Entry",
    active_right: "Right Follow",
    passive: "Passive",
    cc: "Covered Call",
    sell_put: "Sell Put",
  };
  return labels[mode];
}
