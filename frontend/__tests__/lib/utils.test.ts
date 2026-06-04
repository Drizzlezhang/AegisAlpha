import { describe, it, expect } from "vitest";
import {
  formatPrice,
  formatPercent,
  formatDeltaDollars,
  formatLargeNumber,
  formatDate,
  formatDateTime,
  dteFromExpiry,
  cn,
} from "@/lib/utils";

describe("formatPrice", () => {
  it("formats positive number", () => {
    expect(formatPrice(1234.5678)).toBe("1,234.57");
  });

  it("formats negative number", () => {
    expect(formatPrice(-567.89)).toBe("-567.89");
  });

  it("returns -- for NaN", () => {
    expect(formatPrice(NaN)).toBe("--");
  });

  it("returns -- for Infinity", () => {
    expect(formatPrice(Infinity)).toBe("--");
  });

  it("respects decimals parameter", () => {
    expect(formatPrice(100, 0)).toBe("100");
  });
});

describe("formatPercent", () => {
  it("formats positive percent with + sign", () => {
    expect(formatPercent(5.123)).toBe("+5.12%");
  });

  it("formats negative percent", () => {
    expect(formatPercent(-3.5)).toBe("-3.50%");
  });

  it("returns -- for NaN", () => {
    expect(formatPercent(NaN)).toBe("--");
  });
});

describe("formatDeltaDollars", () => {
  it("formats millions", () => {
    expect(formatDeltaDollars(2500000)).toBe("+$2.50M");
  });

  it("formats thousands", () => {
    expect(formatDeltaDollars(184200)).toBe("+$184.2K");
  });

  it("formats small values", () => {
    expect(formatDeltaDollars(500)).toBe("+$500");
  });

  it("formats negative values", () => {
    expect(formatDeltaDollars(-50000)).toBe("-$50.0K");
  });

  it("returns -- for NaN", () => {
    expect(formatDeltaDollars(NaN)).toBe("--");
  });
});

describe("formatLargeNumber", () => {
  it("formats millions", () => {
    expect(formatLargeNumber(2500000)).toBe("2.50M");
  });

  it("formats thousands", () => {
    expect(formatLargeNumber(1500)).toBe("1.5K");
  });

  it("formats small numbers", () => {
    expect(formatLargeNumber(42)).toBe("42");
  });
});

describe("formatDate", () => {
  it("formats ISO date string", () => {
    const result = formatDate("2026-06-04T08:00:00Z");
    expect(result).toContain("2026");
  });

  it("returns original string on invalid date", () => {
    expect(formatDate("not-a-date")).toBe("not-a-date");
  });
});

describe("formatDateTime", () => {
  it("formats ISO datetime string", () => {
    const result = formatDateTime("2026-06-04T08:00:00Z");
    expect(result).toContain("2026");
  });
});

describe("dteFromExpiry", () => {
  it("calculates days to expiry", () => {
    const future = new Date();
    future.setDate(future.getDate() + 30);
    const dte = dteFromExpiry(future.toISOString());
    expect(dte).toBeGreaterThanOrEqual(29);
    expect(dte).toBeLessThanOrEqual(31);
  });
});

describe("cn", () => {
  it("joins class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("filters falsy values", () => {
    expect(cn("foo", false, undefined, null, "bar")).toBe("foo bar");
  });
});
