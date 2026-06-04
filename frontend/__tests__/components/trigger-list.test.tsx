import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

// Mock the fetcher
vi.mock("@/lib/api", () => ({
  fetcher: vi.fn(),
  api: {
    triggers: {
      cancel: vi.fn().mockResolvedValue(undefined),
    },
  },
}));

import TriggersPage from "@/app/(dashboard)/triggers/page";

const mockTriggers = [
  {
    id: 1,
    ticker: "QQQ",
    type: "price_alert",
    params: { condition: "below", level: 470 },
    suggested_action: "Review QQQ LEAPS position",
    valid_until: "2026-06-11T20:00:00Z",
    status: "pending" as const,
  },
  {
    id: 2,
    ticker: "SPY",
    type: "iv_spike",
    params: { condition: "above", level: 35 },
    suggested_action: "Evaluate Covered Call",
    valid_until: "2026-06-18T20:00:00Z",
    status: "triggered" as const,
  },
  {
    id: 3,
    ticker: "GLD",
    type: "price_alert",
    params: { condition: "above", level: 2450 },
    suggested_action: "Take profit",
    valid_until: "2026-06-25T20:00:00Z",
    status: "cancelled" as const,
  },
];

// Partially mock swr: keep SWRConfig, mock default (useSWR)
vi.mock("swr", async (importOriginal) => {
  const actual = await importOriginal<typeof import("swr")>();
  return {
    ...actual,
    default: vi.fn((_key: string, _fetcher: unknown, _config?: unknown) => ({
      data: mockTriggers,
      error: undefined,
      mutate: vi.fn(),
      isLoading: false,
      isValidating: false,
    })),
  };
});

describe("TriggersPage", () => {
  it("renders trigger list with correct tickers", () => {
    render(<TriggersPage />);
    expect(screen.getByText("QQQ")).toBeInTheDocument();
    expect(screen.getByText("SPY")).toBeInTheDocument();
    expect(screen.getByText("GLD")).toBeInTheDocument();
  });

  it("shows cancel button for pending triggers", () => {
    render(<TriggersPage />);
    const cancelButtons = screen.getAllByText("Cancel");
    expect(cancelButtons.length).toBeGreaterThan(0);
  });

  it("renders correct status labels", () => {
    render(<TriggersPage />);
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByText("triggered")).toBeInTheDocument();
    expect(screen.getByText("cancelled")).toBeInTheDocument();
  });
});
