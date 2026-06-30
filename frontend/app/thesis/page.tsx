"use client";

import { useState } from "react";
import { ThesisTable } from "@/components/thesis/thesis-table";

const INPUT_STYLE: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: "6px",
  border: "1px solid var(--aegis-border-default)",
  background: "var(--aegis-bg-base)",
  color: "var(--aegis-text-primary)",
  fontSize: "14px",
  width: "180px",
  outline: "none",
};

const SELECT_STYLE: React.CSSProperties = {
  ...INPUT_STYLE,
  width: "150px",
  appearance: "auto",
  cursor: "pointer",
};

export default function ThesisPage() {
  const [filters, setFilters] = useState({
    status: "all",
    direction: "all",
    ticker: "",
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
        Thesis Cards
      </h1>

      {/* Filters */}
      <div style={{ display: "flex", gap: "12px", marginBottom: "20px" }}>
        <input
          placeholder="Search ticker..."
          value={filters.ticker}
          onChange={(e) =>
            setFilters({ ...filters, ticker: e.target.value.toUpperCase() })
          }
          style={INPUT_STYLE}
        />
        <select
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value })}
          style={SELECT_STYLE}
        >
          <option value="all">All Status</option>
          <option value="valid">Valid</option>
          <option value="partial_broken">Partial Broken</option>
          <option value="fully_broken">Fully Broken</option>
          <option value="closed">Closed</option>
        </select>
        <select
          value={filters.direction}
          onChange={(e) =>
            setFilters({ ...filters, direction: e.target.value })
          }
          style={SELECT_STYLE}
        >
          <option value="all">All Directions</option>
          <option value="long">Long</option>
          <option value="short_put">Short Put</option>
          <option value="cc">Covered Call</option>
        </select>
      </div>

      {/* Table */}
      <ThesisTable filters={filters} />
    </div>
  );
}