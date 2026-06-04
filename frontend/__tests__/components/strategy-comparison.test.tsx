import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import EntryModeBadge from "@/components/charts/entry-mode-badge";

describe("EntryModeBadge", () => {
  it("renders active_left label", () => {
    render(<EntryModeBadge mode="active_left" />);
    expect(screen.getByText("Left Entry")).toBeInTheDocument();
  });

  it("renders active_right label", () => {
    render(<EntryModeBadge mode="active_right" />);
    expect(screen.getByText("Right Follow")).toBeInTheDocument();
  });

  it("renders passive label", () => {
    render(<EntryModeBadge mode="passive" />);
    expect(screen.getByText("Passive")).toBeInTheDocument();
  });

  it("renders cc label", () => {
    render(<EntryModeBadge mode="cc" />);
    expect(screen.getByText("Covered Call")).toBeInTheDocument();
  });

  it("renders sell_put label", () => {
    render(<EntryModeBadge mode="sell_put" />);
    expect(screen.getByText("Sell Put")).toBeInTheDocument();
  });
});
