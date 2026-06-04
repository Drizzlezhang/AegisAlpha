import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import SignalBadge from "@/components/charts/signal-badge";

describe("SignalBadge", () => {
  it("renders bull signal with correct label", () => {
    render(<SignalBadge signal="bull" />);
    expect(screen.getByText("Bullish")).toBeInTheDocument();
  });

  it("renders bear signal with correct label", () => {
    render(<SignalBadge signal="bear" />);
    expect(screen.getByText("Bearish")).toBeInTheDocument();
  });

  it("renders neutral signal with correct label", () => {
    render(<SignalBadge signal="neutral" />);
    expect(screen.getByText("Neutral")).toBeInTheDocument();
  });

  it("renders blocked signal with correct label", () => {
    render(<SignalBadge signal="blocked" />);
    expect(screen.getByText("Blocked")).toBeInTheDocument();
  });

  it("renders custom label when provided", () => {
    render(<SignalBadge signal="bull" label="BUY" />);
    expect(screen.getByText("BUY")).toBeInTheDocument();
  });

  it("applies correct color for bull signal", () => {
    render(<SignalBadge signal="bull" />);
    const badge = screen.getByText("Bullish");
    expect(badge.style.color).toBe("var(--aegis-signal-bull)");
  });

  it("applies correct color for bear signal", () => {
    render(<SignalBadge signal="bear" />);
    const badge = screen.getByText("Bearish");
    expect(badge.style.color).toBe("var(--aegis-signal-bear)");
  });
});
