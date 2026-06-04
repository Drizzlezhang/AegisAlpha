interface LoadingSkeletonProps {
  lines?: number;
}

export default function LoadingSkeleton({ lines = 3 }: LoadingSkeletonProps) {
  return (
    <div className="flex flex-col gap-3 p-4 animate-pulse">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-4 rounded"
          style={{
            background: "var(--aegis-bg-elevated)",
            width: `${100 - i * 15}%`,
          }}
        />
      ))}
    </div>
  );
}
