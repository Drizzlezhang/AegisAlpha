"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { PortfolioSnapshot } from "@/lib/types";
import PortfolioSummary from "@/components/dashboard/portfolio-summary";
import RecommendationFeed from "@/components/dashboard/recommendation-feed";
import PositionSnapshot from "@/components/dashboard/position-snapshot";
import DeltaDollarsChart from "@/components/dashboard/delta-dollars-chart";
import GreeksSummary from "@/components/dashboard/greeks-summary";
import ExpiryCalendar from "@/components/dashboard/expiry-calendar";
import PnlTrendChart from "@/components/dashboard/pnl-trend-chart";
import FundFlowHeatmap from "@/components/dashboard/fund-flow-heatmap";
import SmartMoneyCard from "@/components/dashboard/smart-money-card";
import HealthPanel from "@/components/dashboard/health-panel";

export default function DashboardPage() {
  const { data: snapshot, error } = useSWR<PortfolioSnapshot>(
    "/portfolio/snapshot",
    fetcher,
    { refreshInterval: 30000 }
  );

  if (error) {
    return (
      <div
        className="flex items-center justify-center h-full"
        style={{ color: "var(--aegis-signal-bear)" }}
      >
        Failed to load portfolio data
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* Row 1: Portfolio Summary (full width) */}
      <PortfolioSummary data={snapshot} />

      {/* Row 2: Recommendation Feed + Position Snapshot */}
      <div className="grid grid-cols-2 gap-4">
        <RecommendationFeed />
        <PositionSnapshot />
      </div>

      {/* Row 3: Delta Dollars Chart + Greeks Summary */}
      <div className="grid grid-cols-2 gap-4">
        <DeltaDollarsChart />
        <GreeksSummary />
      </div>

      {/* Row 4: Expiry Calendar + P&L Trend */}
      <div className="grid grid-cols-2 gap-4">
        <ExpiryCalendar />
        <PnlTrendChart />
      </div>

      {/* Row 5: Fund Flow Heatmap + Smart Money Card + Health Panel */}
      <div className="grid grid-cols-3 gap-4">
        <FundFlowHeatmap />
        <SmartMoneyCard />
        <HealthPanel />
      </div>
    </div>
  );
}
