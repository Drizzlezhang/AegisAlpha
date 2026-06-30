"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { closeThesis } from "@/lib/api/thesis";

interface Props {
  thesisId: number;
  ticker: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function CloseModal({ thesisId, ticker, onClose, onSuccess }: Props) {
  const [closePrice, setClosePrice] = useState("");
  const [judgmentScore, setJudgmentScore] = useState(3);
  const [executionScore, setExecutionScore] = useState(3);
  const [closeReason, setCloseReason] = useState("manual");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!closePrice) return;
    setLoading(true);
    setError(null);
    try {
      await closeThesis(thesisId, {
        close_price: parseFloat(closePrice),
        judgment_score: judgmentScore,
        execution_score: executionScore,
        close_reason: closeReason,
      });
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to close thesis");
    } finally {
      setLoading(false);
    }
  };

  const overlayStyle: React.CSSProperties = {
    position: "fixed",
    inset: 0,
    background: "var(--aegis-bg-overlay)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 50,
  };

  const dialogStyle: React.CSSProperties = {
    background: "var(--aegis-bg-surface)",
    border: "1px solid var(--aegis-border-default)",
    borderRadius: "12px",
    padding: "24px",
    width: "100%",
    maxWidth: "420px",
    maxHeight: "90vh",
    overflowY: "auto",
  };

  const labelStyle: React.CSSProperties = {
    display: "block",
    fontSize: "13px",
    fontWeight: 500,
    color: "var(--aegis-text-secondary)",
    marginBottom: "6px",
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "8px 12px",
    borderRadius: "6px",
    border: "1px solid var(--aegis-border-default)",
    background: "var(--aegis-bg-base)",
    color: "var(--aegis-text-primary)",
    fontSize: "14px",
    outline: "none",
    boxSizing: "border-box",
  };

  const selectStyle: React.CSSProperties = {
    ...inputStyle,
    appearance: "auto",
    cursor: "pointer",
  };

  const sliderTrackStyle: React.CSSProperties = {
    width: "100%",
    height: "6px",
    borderRadius: "3px",
    background: "var(--aegis-bg-elevated)",
    position: "relative",
    marginTop: "8px",
    marginBottom: "4px",
  };

  const sliderFillStyle = (value: number): React.CSSProperties => ({
    height: "100%",
    borderRadius: "3px",
    background: "var(--aegis-brand)",
    width: `${((value - 1) / 4) * 100}%`,
    transition: "width 150ms",
  });

  const btnPrimaryStyle: React.CSSProperties = {
    padding: "8px 16px",
    borderRadius: "6px",
    border: "none",
    background: "var(--aegis-brand)",
    color: "var(--aegis-text-on-brand)",
    fontSize: "14px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "background-color 150ms",
  };

  const btnOutlineStyle: React.CSSProperties = {
    padding: "8px 16px",
    borderRadius: "6px",
    border: "1px solid var(--aegis-border-default)",
    background: "transparent",
    color: "var(--aegis-text-secondary)",
    fontSize: "14px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "background-color 150ms",
  };

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={dialogStyle} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "20px",
          }}
        >
          <h2
            style={{
              fontSize: "18px",
              fontWeight: 600,
              color: "var(--aegis-text-primary)",
              margin: 0,
            }}
          >
            Close {ticker} Position
          </h2>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: "var(--aegis-text-tertiary)",
              padding: "4px",
              borderRadius: "4px",
              transition: "color 150ms",
            }}
          >
            <X size={20} />
          </button>
        </div>

        {error && (
          <div
            style={{
              padding: "8px 12px",
              borderRadius: "6px",
              background: "var(--aegis-signal-bear-bg)",
              color: "var(--aegis-signal-bear)",
              fontSize: "13px",
              marginBottom: "16px",
            }}
          >
            {error}
          </div>
        )}

        {/* Close Price */}
        <div style={{ marginBottom: "16px" }}>
          <label style={labelStyle}>Close Price</label>
          <input
            type="number"
            step="0.01"
            placeholder="Enter close price"
            value={closePrice}
            onChange={(e) => setClosePrice(e.target.value)}
            style={inputStyle}
          />
        </div>

        {/* Close Reason */}
        <div style={{ marginBottom: "16px" }}>
          <label style={labelStyle}>Close Reason</label>
          <select
            value={closeReason}
            onChange={(e) => setCloseReason(e.target.value)}
            style={selectStyle}
          >
            <option value="target_reached">Target Reached</option>
            <option value="stop_hit">Stop Hit</option>
            <option value="thesis_broken">Thesis Broken</option>
            <option value="manual">Manual</option>
          </select>
        </div>

        {/* Judgment Score */}
        <div style={{ marginBottom: "16px" }}>
          <label style={labelStyle}>
            Judgment Score:{" "}
            <span style={{ fontWeight: 600, color: "var(--aegis-text-primary)" }}>
              {judgmentScore}/5
            </span>
          </label>
          <p
            style={{
              fontSize: "12px",
              color: "var(--aegis-text-tertiary)",
              margin: "0 0 4px",
            }}
          >
            Was the system&apos;s analysis accurate? (direction, timing)
          </p>
          <div style={sliderTrackStyle}>
            <div style={sliderFillStyle(judgmentScore)} />
          </div>
          <input
            type="range"
            min={1}
            max={5}
            step={1}
            value={judgmentScore}
            onChange={(e) => setJudgmentScore(Number(e.target.value))}
            style={{ width: "100%", margin: 0, cursor: "pointer" }}
          />
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: "12px",
              color: "var(--aegis-text-tertiary)",
              marginTop: "2px",
            }}
          >
            <span>Wrong</span>
            <span>Accurate</span>
          </div>
        </div>

        {/* Execution Score */}
        <div style={{ marginBottom: "24px" }}>
          <label style={labelStyle}>
            Execution Score:{" "}
            <span style={{ fontWeight: 600, color: "var(--aegis-text-primary)" }}>
              {executionScore}/5
            </span>
          </label>
          <p
            style={{
              fontSize: "12px",
              color: "var(--aegis-text-tertiary)",
              margin: "0 0 4px",
            }}
          >
            Did you execute well? (discipline, stop-loss adherence)
          </p>
          <div style={sliderTrackStyle}>
            <div style={sliderFillStyle(executionScore)} />
          </div>
          <input
            type="range"
            min={1}
            max={5}
            step={1}
            value={executionScore}
            onChange={(e) => setExecutionScore(Number(e.target.value))}
            style={{ width: "100%", margin: 0, cursor: "pointer" }}
          />
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: "12px",
              color: "var(--aegis-text-tertiary)",
              marginTop: "2px",
            }}
          >
            <span>Poor</span>
            <span>Perfect</span>
          </div>
        </div>

        {/* Footer */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
          <button style={btnOutlineStyle} onClick={onClose}>
            Cancel
          </button>
          <button
            style={{
              ...btnPrimaryStyle,
              opacity: !closePrice || loading ? 0.5 : 1,
              cursor: !closePrice || loading ? "not-allowed" : "pointer",
            }}
            onClick={handleSubmit}
            disabled={!closePrice || loading}
          >
            {loading ? "Closing..." : "Confirm Close"}
          </button>
        </div>
      </div>
    </div>
  );
}