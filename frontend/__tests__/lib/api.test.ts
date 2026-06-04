import { describe, it, expect } from "vitest";
import { api } from "@/lib/api";

describe("API Client", () => {
  it("builds pipeline latest URL", () => {
    expect(api.pipeline.latest()).toBe("/pipeline/latest");
  });

  it("builds pipeline runs URL with params", () => {
    const url = api.pipeline.runs({ limit: "10", mode: "full" });
    expect(url).toContain("/pipeline/runs?");
    expect(url).toContain("limit=10");
    expect(url).toContain("mode=full");
  });

  it("builds portfolio snapshot URL", () => {
    expect(api.portfolio.snapshot()).toBe("/portfolio/snapshot");
  });

  it("builds portfolio greeks URL", () => {
    expect(api.portfolio.greeks()).toBe("/portfolio/greeks");
  });

  it("builds portfolio delta-dollars URL", () => {
    expect(api.portfolio.deltaDollars()).toBe("/portfolio/delta-dollars");
  });

  it("builds portfolio health URL", () => {
    expect(api.portfolio.health()).toBe("/portfolio/health");
  });

  it("builds recommendations list URL", () => {
    expect(api.recommendations.list()).toBe("/recommendations");
  });

  it("builds recommendation detail URL", () => {
    expect(api.recommendations.detail(42)).toBe("/recommendations/42");
  });

  it("builds triggers list URL", () => {
    expect(api.triggers.list()).toBe("/triggers");
  });

  it("builds flows ETF URL", () => {
    expect(api.flows.etf()).toBe("/flows/etf");
  });

  it("builds flows sector URL", () => {
    expect(api.flows.sector()).toBe("/flows/sector");
  });

  it("builds flows smart money URL", () => {
    expect(api.flows.smartMoney("QQQ")).toBe("/flows/smart-money/QQQ");
  });
});
