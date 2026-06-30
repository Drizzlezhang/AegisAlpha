import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

// jsdom has no dimensions, so ResponsiveContainer won't render children
vi.mock("recharts", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => children,
  };
});

import { WeightTrendChart } from "@/components/memory/weight-trend-chart";

const mockHistory = [
  {
    factor_name: "trend_phase",
    weight: 1.0,
    previous_weight: null,
    changed_by: "system",
    sample_count: 0,
    updated_at: "2026-06-01T00:00:00Z",
  },
  {
    factor_name: "trend_phase",
    weight: 1.2,
    previous_weight: 1.0,
    changed_by: "system",
    sample_count: 5,
    updated_at: "2026-06-08T00:00:00Z",
  },
  {
    factor_name: "smart_money",
    weight: 0.8,
    previous_weight: null,
    changed_by: "system",
    sample_count: 0,
    updated_at: "2026-06-01T00:00:00Z",
  },
];

describe("WeightTrendChart", () => {
  it("shows empty state when no data", () => {
    render(<WeightTrendChart history={[]} />);

    expect(screen.getByText("No weight data yet")).toBeInTheDocument();
  });

  it("renders chart with data", () => {
    const { container } = render(<WeightTrendChart history={mockHistory} />);

    // Recharts ResponsiveContainer renders a div with recharts-wrapper class
    const wrapper = container.querySelector(".recharts-wrapper");
    expect(wrapper).toBeInTheDocument();
  });
});