import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { ThemeToggle } from "@/components/ui/theme-toggle";

// jsdom localStorage mock
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
  };
})();
Object.defineProperty(window, "localStorage", { value: localStorageMock });

describe("ThemeToggle", () => {
  beforeEach(() => {
    localStorageMock.clear();
    document.documentElement.setAttribute("data-theme", "dark");
  });

  it("renders toggle button", () => {
    render(<ThemeToggle />);

    expect(
      screen.getByRole("button", { name: /toggle theme/i })
    ).toBeInTheDocument();
  });

  it("toggles from dark to light", () => {
    render(<ThemeToggle />);

    const button = screen.getByRole("button", { name: /toggle theme/i });
    fireEvent.click(button);

    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("toggles back from light to dark", () => {
    render(<ThemeToggle />);

    const button = screen.getByRole("button", { name: /toggle theme/i });
    fireEvent.click(button); // dark → light
    fireEvent.click(button); // light → dark

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("persists to localStorage", () => {
    render(<ThemeToggle />);

    fireEvent.click(screen.getByRole("button", { name: /toggle theme/i }));

    expect(localStorage.getItem("aegis-theme")).toBe("light");
  });

  it("reads initial theme from localStorage", () => {
    localStorage.setItem("aegis-theme", "light");
    render(<ThemeToggle />);

    // Component reads from localStorage on mount
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});