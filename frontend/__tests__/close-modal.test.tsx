import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { CloseModal } from "@/components/thesis/close-modal";

// Mock API
vi.mock("@/lib/api/thesis", () => ({
  closeThesis: vi.fn().mockResolvedValue({ thesis_id: 1, pnl_pct: 0.1 }),
}));

describe("CloseModal", () => {
  const defaultProps = {
    thesisId: 1,
    ticker: "NVDA",
    onClose: vi.fn(),
    onSuccess: vi.fn(),
  };

  it("renders close position modal", () => {
    render(<CloseModal {...defaultProps} />);

    expect(screen.getByText("Close NVDA Position")).toBeInTheDocument();
  });

  it("renders judgment and execution sliders", () => {
    render(<CloseModal {...defaultProps} />);

    expect(screen.getByText(/Judgment Score/)).toBeInTheDocument();
    expect(screen.getByText(/Execution Score/)).toBeInTheDocument();
  });

  it("renders close reason select", () => {
    render(<CloseModal {...defaultProps} />);

    expect(screen.getByText("Target Reached")).toBeInTheDocument();
  });

  it("renders cancel and confirm buttons", () => {
    render(<CloseModal {...defaultProps} />);

    expect(screen.getByText("Cancel")).toBeInTheDocument();
    expect(screen.getByText("Confirm Close")).toBeInTheDocument();
  });

  it("calls onClose when cancel is clicked", () => {
    const onClose = vi.fn();
    render(<CloseModal {...defaultProps} onClose={onClose} />);

    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalled();
  });
});