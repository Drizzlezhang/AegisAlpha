"use client";

import { useEffect, useState } from "react";
import { KOLSourceTable } from "@/components/kol/kol-source-table";
import { AttributionChart } from "@/components/kol/attribution-chart";
import { RecentCallsFeed } from "@/components/kol/recent-calls-feed";
import { fetchKOLSources, fetchKOLCalls, fetchAttributionReport } from "@/lib/api/kol";
import type { KOLSource, KOLCall } from "@/lib/api/kol";

export default function KOLPage() {
  const [sources, setSources] = useState<KOLSource[]>([]);
  const [calls, setCalls] = useState<KOLCall[]>([]);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [s, c, r] = await Promise.all([
          fetchKOLSources(),
          fetchKOLCalls({ limit: 20 }),
          fetchAttributionReport(),
        ]);
        setSources(s);
        setCalls(c);
        setReport(r);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load KOL data");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <div
        style={{
          padding: "48px",
          textAlign: "center",
          color: "var(--aegis-text-tertiary)",
        }}
      >
        Loading...
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          padding: "48px",
          textAlign: "center",
          color: "var(--aegis-signal-bear)",
          fontSize: "14px",
        }}
      >
        {error}
      </div>
    );
  }

  return (
    <div style={{ padding: "24px" }}>
      <h1
        style={{
          fontSize: "24px",
          fontWeight: 600,
          color: "var(--aegis-text-primary)",
          margin: "0 0 24px",
        }}
      >
        KOL Tracker
      </h1>

      {/* Source Table */}
      <section style={{ marginBottom: "24px" }}>
        <h2
          style={{
            fontSize: "16px",
            fontWeight: 500,
            color: "var(--aegis-text-primary)",
            margin: "0 0 12px",
          }}
        >
          KOL Sources
        </h2>
        <KOLSourceTable sources={sources} />
      </section>

      {/* Attribution + Recent Calls */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "20px",
        }}
      >
        <div>
          <h2
            style={{
              fontSize: "16px",
              fontWeight: 500,
              color: "var(--aegis-text-primary)",
              margin: "0 0 12px",
            }}
          >
            Attribution
          </h2>
          <div
            style={{
              padding: "16px",
              borderRadius: "8px",
              border: "1px solid var(--aegis-border-default)",
              background: "var(--aegis-bg-surface)",
            }}
          >
            <AttributionChart report={report} />
          </div>
        </div>
        <div>
          <h2
            style={{
              fontSize: "16px",
              fontWeight: 500,
              color: "var(--aegis-text-primary)",
              margin: "0 0 12px",
            }}
          >
            Recent Calls
          </h2>
          <div
            style={{
              borderRadius: "8px",
              border: "1px solid var(--aegis-border-default)",
              background: "var(--aegis-bg-surface)",
              overflow: "hidden",
            }}
          >
            <RecentCallsFeed calls={calls} />
          </div>
        </div>
      </div>
    </div>
  );
}