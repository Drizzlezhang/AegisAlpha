import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { KOLSourceTable } from "@/components/kol/kol-source-table";

const mockSources = [
  {
    id: 1,
    name: "Trader Joe",
    platform: "x",
    handle: "traderjoe",
    reliability_score: 0.75,
    total_calls: 120,
    successful_calls: 90,
    enabled: true,
  },
  {
    id: 2,
    name: "Stock Guru",
    platform: "stocktwits",
    handle: "stockguru",
    reliability_score: 0.35,
    total_calls: 50,
    successful_calls: 15,
    enabled: true,
  },
];

describe("KOLSourceTable", () => {
  it("renders KOL source names", () => {
    render(<KOLSourceTable sources={mockSources} />);

    expect(screen.getByText("Trader Joe")).toBeInTheDocument();
    expect(screen.getByText("Stock Guru")).toBeInTheDocument();
  });

  it("renders platform labels", () => {
    render(<KOLSourceTable sources={mockSources} />);

    expect(screen.getByText("X")).toBeInTheDocument();
    expect(screen.getByText("StockTwits")).toBeInTheDocument();
  });

  it("shows empty state when no sources", () => {
    render(<KOLSourceTable sources={[]} />);

    expect(screen.getByText("No KOL sources tracked yet")).toBeInTheDocument();
  });

  it("renders reliability percentages", () => {
    render(<KOLSourceTable sources={mockSources} />);

    expect(screen.getAllByText("75%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("35%").length).toBeGreaterThanOrEqual(1);
  });
});