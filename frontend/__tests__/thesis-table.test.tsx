import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ThesisTable } from "@/components/thesis/thesis-table";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock API
vi.mock("@/lib/api/thesis", () => ({
  fetchTheses: vi.fn().mockResolvedValue([
    {
      id: 1,
      ticker: "NVDA",
      direction: "long",
      entry_mode: "active_right",
      thesis_valid_status: "valid",
      entry_date: "2024-01-15T00:00:00Z",
      entry_price: 500,
      target_price: 600,
      stop_price: 450,
      actual_pnl_pct: null,
      judgment_score: null,
      execution_score: null,
    },
    {
      id: 2,
      ticker: "QQQ",
      direction: "short_put",
      entry_mode: "active_left",
      thesis_valid_status: "partial_broken",
      entry_date: "2024-02-01T00:00:00Z",
      entry_price: 420,
      target_price: null,
      stop_price: 400,
      actual_pnl_pct: 0.05,
      judgment_score: 4,
      execution_score: 3,
    },
  ]),
}));

describe("ThesisTable", () => {
  it("renders thesis cards", async () => {
    render(
      <ThesisTable filters={{ status: "all", direction: "all", ticker: "" }} />
    );

    expect(await screen.findByText("NVDA")).toBeInTheDocument();
  });

  it("displays all thesis rows", async () => {
    render(
      <ThesisTable filters={{ status: "all", direction: "all", ticker: "" }} />
    );

    expect(await screen.findByText("NVDA")).toBeInTheDocument();
    expect(screen.getByText("QQQ")).toBeInTheDocument();
  });

  it("shows column headers", async () => {
    render(
      <ThesisTable filters={{ status: "all", direction: "all", ticker: "" }} />
    );

    expect(await screen.findByText("Ticker")).toBeInTheDocument();
    expect(screen.getByText("Direction")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("P&L")).toBeInTheDocument();
  });
});