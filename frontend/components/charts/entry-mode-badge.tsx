import { entryModeLabel, type EntryMode } from "@/lib/design-tokens";

interface EntryModeBadgeProps {
  mode: EntryMode;
}

export default function EntryModeBadge({ mode }: EntryModeBadgeProps) {
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded"
      style={{
        color: "var(--aegis-brand)",
        background: "var(--aegis-brand-muted)",
      }}
    >
      {entryModeLabel(mode)}
    </span>
  );
}
