"use client";

import { useEffect, useState, useCallback } from "react";
import { WeightTrendChart } from "@/components/memory/weight-trend-chart";
import { ReportList } from "@/components/memory/report-list";
import { VectorSearch } from "@/components/memory/vector-search";
import { fetchWeightHistory, type WeightHistoryItem } from "@/lib/api/memory";
import { fetchReports, fetchReport, type ReportMeta, type ReportContent } from "@/lib/api/reports";

type Tab = "weights" | "reports" | "search";

export default function MemoryPage() {
  const [activeTab, setActiveTab] = useState<Tab>("weights");
  const [weightHistory, setWeightHistory] = useState<WeightHistoryItem[]>([]);
  const [reports, setReports] = useState<ReportMeta[]>([]);
  const [selectedReport, setSelectedReport] = useState<ReportContent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadWeights = useCallback(async () => {
    try {
      const data = await fetchWeightHistory();
      setWeightHistory(data);
    } catch {
      // ignore — handled by empty state in chart
    }
  }, []);

  const loadReports = useCallback(async () => {
    try {
      const data = await fetchReports();
      setReports(data);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setSelectedReport(null);
    if (activeTab === "weights") loadWeights();
    if (activeTab === "reports") loadReports();
    setLoading(false);
  }, [activeTab, loadWeights, loadReports]);

  const handleReportSelect = async (report: ReportMeta) => {
    try {
      const content = await fetchReport(report.type, report.date);
      setSelectedReport(content);
    } catch {
      // ignore
    }
  };

  const tabStyle = (tab: Tab): React.CSSProperties => ({
    padding: "8px 16px",
    borderRadius: "6px",
    border: "none",
    background:
      activeTab === tab
        ? "var(--aegis-brand-muted)"
        : "transparent",
    color:
      activeTab === tab
        ? "var(--aegis-brand)"
        : "var(--aegis-text-secondary)",
    fontSize: "14px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "background-color 150ms, color 150ms",
  });

  return (
    <div style={{ padding: "24px" }}>
      <h1
        style={{
          fontSize: "24px",
          fontWeight: 600,
          color: "var(--aegis-text-primary)",
          margin: "0 0 20px",
        }}
      >
        Memory &amp; Review
      </h1>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "20px" }}>
        <button style={tabStyle("weights")} onClick={() => setActiveTab("weights")}>
          Weight Trends
        </button>
        <button style={tabStyle("reports")} onClick={() => setActiveTab("reports")}>
          Reports
        </button>
        <button style={tabStyle("search")} onClick={() => setActiveTab("search")}>
          Vector Search
        </button>
      </div>

      {error && (
        <div
          style={{
            padding: "12px",
            borderRadius: "8px",
            background: "var(--aegis-signal-bear-bg)",
            color: "var(--aegis-signal-bear)",
            fontSize: "13px",
            marginBottom: "16px",
          }}
        >
          {error}
        </div>
      )}

      {/* Tab Content */}
      {activeTab === "weights" && (
        <div
          style={{
            padding: "16px",
            borderRadius: "8px",
            border: "1px solid var(--aegis-border-default)",
            background: "var(--aegis-bg-surface)",
          }}
        >
          <WeightTrendChart history={weightHistory} />
        </div>
      )}

      {activeTab === "reports" && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "20px",
          }}
        >
          <div
            style={{
              borderRadius: "8px",
              border: "1px solid var(--aegis-border-default)",
              background: "var(--aegis-bg-surface)",
              overflow: "hidden",
            }}
          >
            <ReportList reports={reports} onSelect={handleReportSelect} />
          </div>
          <div
            style={{
              borderRadius: "8px",
              border: "1px solid var(--aegis-border-default)",
              background: "var(--aegis-bg-surface)",
              padding: "16px",
              minHeight: "200px",
              overflowY: "auto",
            }}
          >
            {selectedReport ? (
              <div>
                <h3
                  style={{
                    fontSize: "16px",
                    fontWeight: 600,
                    color: "var(--aegis-text-primary)",
                    margin: "0 0 8px",
                  }}
                >
                  {selectedReport.type === "weekly" ? "Weekly" : "Monthly"} Report
                </h3>
                <p
                  style={{
                    fontSize: "12px",
                    color: "var(--aegis-text-tertiary)",
                    margin: "0 0 16px",
                  }}
                >
                  {selectedReport.period.start} &rarr; {selectedReport.period.end}
                </p>
                <div
                  style={{
                    fontSize: "14px",
                    color: "var(--aegis-text-secondary)",
                    lineHeight: 1.6,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {selectedReport.markdown}
                </div>
              </div>
            ) : (
              <div
                style={{
                  padding: "32px",
                  textAlign: "center",
                  color: "var(--aegis-text-tertiary)",
                  fontSize: "14px",
                }}
              >
                Select a report to view details
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "search" && (
        <div
          style={{
            borderRadius: "8px",
            border: "1px solid var(--aegis-border-default)",
            background: "var(--aegis-bg-surface)",
            padding: "16px",
          }}
        >
          <VectorSearch />
        </div>
      )}
    </div>
  );
}