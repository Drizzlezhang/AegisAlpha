import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PortfolioSummary from "@/components/dashboard/portfolio-summary";

describe("PortfolioSummary", () => {
  const mockData = {
    total_nav: 287500.0,
    daily_pnl: 3250.5,
    daily_pnl_pct: 1.14,
    delta_dollars: 184200.0,
    cash_ratio: 22.5,
  };

  it("renders all four metrics", () => {
    render(<PortfolioSummary data={mockData} />);
    expect(screen.getByText("Total NAV")).toBeInTheDocument();
    expect(screen.getByText("Daily P&L")).toBeInTheDocument();
    expect(screen.getByText("Delta $")).toBeInTheDocument();
    expect(screen.getByText("Cash Ratio")).toBeInTheDocument();
  });

  it("formats NAV as currency", () => {
    render(<PortfolioSummary data={mockData} />);
    expect(screen.getByText("287,500")).toBeInTheDocument();
  });

  it("shows positive P&L in bull color", () => {
    render(<PortfolioSummary data={mockData} />);
    const pnlEl = screen.getByText(/3,251/);
    expect(pnlEl).toBeInTheDocument();
  });

  it("shows negative P&L in bear color", () => {
    const lossData = { ...mockData, daily_pnl: -1500, daily_pnl_pct: -0.52 };
    render(<PortfolioSummary data={lossData} />);
    const pnlEl = screen.getByText(/-1,500/);
    expect(pnlEl).toBeInTheDocument();
  });

  it("renders loading skeleton when data is null", () => {
    const { container } = render(<PortfolioSummary data={null} />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("formats Delta Dollars correctly", () => {
    render(<PortfolioSummary data={mockData} />);
    expect(screen.getByText("+$184.2K")).toBeInTheDocument();
  });
});
