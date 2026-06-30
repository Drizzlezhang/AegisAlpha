"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AssumptionChecklist } from "@/components/thesis/assumption-checklist";
import { CloseModal } from "@/components/thesis/close-modal";
import { fetchThesisDetail, type ThesisDetail } from "@/lib/api/thesis";
import { formatDate } from "@/lib/utils";

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        padding: "16px",
        borderRadius: "8px",
        background: "var(--aegis-bg-surface)",
        border: "1px solid var(--aegis-border-default)",
      }}
    >
      <p
        style={{
          fontSize: "12px",
          color: "var(--aegis-text-tertiary)",
          margin: "0 0 4px",
        }}
      >
        {label}
      </p>
      <p
        style={{
          fontSize: "18px",
          fontWeight: 600,
          color: "var(--aegis-text-primary)",
          margin: 0,
        }}
      >
        {value}
      </p>
    </div>
  );
}

export default function ThesisDetailPage() {
  const params = useParams();
  const [thesis, setThesis] = useState<ThesisDetail | null>(null);
  const [showCloseModal, setShowCloseModal] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!params.id) return;
    setError(null);
    try {
      const data = await fetchThesisDetail(Number(params.id));
      setThesis(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load thesis");
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

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

  if (!thesis) {
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

  const isClosed = !!thesis.close_date;

  return (
    <div style={{ padding: "24px" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          marginBottom: "24px",
        }}
      >
        <div>
          <h1
            style={{
              fontSize: "24px",
              fontWeight: 600,
              color: "var(--aegis-text-primary)",
              margin: "0 0 4px",
            }}
          >
            {thesis.ticker} &mdash; {thesis.direction.toUpperCase()}
          </h1>
          <p
            style={{
              fontSize: "14px",
              color: "var(--aegis-text-tertiary)",
              margin: 0,
            }}
          >
            Entry: ${thesis.entry_price}{" "}
            {thesis.entry_date ? `on ${formatDate(thesis.entry_date)}` : ""}
          </p>
        </div>
        {!isClosed && (
          <button
            onClick={() => setShowCloseModal(true)}
            style={{
              padding: "8px 16px",
              borderRadius: "6px",
              border: "none",
              background: "var(--aegis-signal-bear)",
              color: "#fff",
              fontSize: "14px",
              fontWeight: 500,
              cursor: "pointer",
              transition: "background-color 150ms",
            }}
          >
            Close Position
          </button>
        )}
      </div>

      {/* Status + Scores */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "12px",
          marginBottom: "24px",
        }}
      >
        <MetricCard label="Status" value={thesis.thesis_valid_status.replace(/_/g, " ")} />
        <MetricCard label="Entry Mode" value={thesis.entry_mode.replace(/_/g, " ")} />
        <MetricCard
          label="Target"
          value={thesis.target_price ? `$${thesis.target_price}` : "\u2014"}
        />
        <MetricCard
          label="Stop"
          value={thesis.stop_price ? `$${thesis.stop_price}` : "\u2014"}
        />
      </div>

      {/* Key Assumptions */}
      <section style={{ marginBottom: "24px" }}>
        <h2
          style={{
            fontSize: "16px",
            fontWeight: 500,
            color: "var(--aegis-text-primary)",
            margin: "0 0 12px",
          }}
        >
          Key Assumptions
        </h2>
        <AssumptionChecklist assumptions={thesis.key_assumptions || []} />
      </section>

      {/* Factor Snapshot */}
      {thesis.factor_snapshot &&
        Object.keys(thesis.factor_snapshot).length > 0 && (
          <section style={{ marginBottom: "24px" }}>
            <h2
              style={{
                fontSize: "16px",
                fontWeight: 500,
                color: "var(--aegis-text-primary)",
                margin: "0 0 12px",
              }}
            >
              Factor Snapshot at Entry
            </h2>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: "10px",
              }}
            >
              {Object.entries(thesis.factor_snapshot).map(([factor, weight]) => (
                <div
                  key={factor}
                  style={{
                    padding: "12px",
                    borderRadius: "8px",
                    background: "var(--aegis-bg-elevated)",
                    border: "1px solid var(--aegis-border-default)",
                  }}
                >
                  <p
                    style={{
                      fontSize: "12px",
                      color: "var(--aegis-text-tertiary)",
                      margin: "0 0 4px",
                    }}
                  >
                    {factor}
                  </p>
                  <p
                    style={{
                      fontSize: "18px",
                      fontWeight: 600,
                      color: "var(--aegis-text-primary)",
                      margin: 0,
                    }}
                  >
                    {(weight as number).toFixed(2)}
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}

      {/* Close Result */}
      {isClosed && (
        <section style={{ marginBottom: "24px" }}>
          <h2
            style={{
              fontSize: "16px",
              fontWeight: 500,
              color: "var(--aegis-text-primary)",
              margin: "0 0 12px",
            }}
          >
            Result
          </h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: "12px",
            }}
          >
            <MetricCard
              label="Close Price"
              value={thesis.close_price ? `$${thesis.close_price}` : "\u2014"}
            />
            <MetricCard
              label="P&L"
              value={
                thesis.actual_pnl_pct != null
                  ? `${(thesis.actual_pnl_pct >= 0 ? "+" : "") + (thesis.actual_pnl_pct * 100).toFixed(1)}%`
                  : "\u2014"
              }
            />
            <MetricCard
              label="Judgment"
              value={
                thesis.judgment_score != null
                  ? `${thesis.judgment_score}/5`
                  : "\u2014"
              }
            />
            <MetricCard
              label="Execution"
              value={
                thesis.execution_score != null
                  ? `${thesis.execution_score}/5`
                  : "\u2014"
              }
            />
          </div>
        </section>
      )}

      {/* Close Modal */}
      {showCloseModal && (
        <CloseModal
          thesisId={thesis.id}
          ticker={thesis.ticker}
          onClose={() => setShowCloseModal(false)}
          onSuccess={() => {
            setShowCloseModal(false);
            load();
          }}
        />
      )}
    </div>
  );
}