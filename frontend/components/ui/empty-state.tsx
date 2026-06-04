interface EmptyStateProps {
  title: string;
  description?: string;
}

export default function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 gap-2">
      <p
        className="text-sm font-medium"
        style={{ color: "var(--aegis-text-secondary)" }}
      >
        {title}
      </p>
      {description && (
        <p
          className="text-xs"
          style={{ color: "var(--aegis-text-tertiary)" }}
        >
          {description}
        </p>
      )}
    </div>
  );
}
