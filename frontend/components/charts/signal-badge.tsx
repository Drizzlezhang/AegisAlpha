import { signalToColor, signalToBgColor, type SignalType } from "@/lib/design-tokens";

interface SignalBadgeProps {
  signal: SignalType;
  label?: string;
}

const DEFAULT_LABELS: Record<SignalType, string> = {
  bull: "Bullish",
  bear: "Bearish",
  neutral: "Neutral",
  blocked: "Blocked",
};

export default function SignalBadge({ signal, label }: SignalBadgeProps) {
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded"
      style={{
        color: signalToColor(signal),
        background: signalToBgColor(signal),
      }}
    >
      {label || DEFAULT_LABELS[signal]}
    </span>
  );
}
