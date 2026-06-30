"use client";

import { useState } from "react";
import { Search } from "lucide-react";
import { searchMemory, MemorySearchResult } from "@/lib/api/memory";

export function VectorSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MemorySearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setSearched(true);
    try {
      const items = await searchMemory(query.trim());
      setResults(items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {/* Search Input */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "8px 12px",
            borderRadius: "8px",
            border: "1px solid var(--aegis-border-default)",
            background: "var(--aegis-bg-base)",
          }}
        >
          <Search size={16} style={{ color: "var(--aegis-text-tertiary)" }} />
          <input
            type="text"
            placeholder="Search memory (e.g., AAPL bull thesis)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearch();
            }}
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              background: "transparent",
              color: "var(--aegis-text-primary)",
              fontSize: "14px",
            }}
          />
        </div>
        <button
          onClick={handleSearch}
          disabled={loading || !query.trim()}
          style={{
            padding: "8px 16px",
            borderRadius: "8px",
            border: "none",
            background: "var(--aegis-brand)",
            color: "var(--aegis-text-on-brand)",
            fontSize: "14px",
            fontWeight: 500,
            cursor: loading ? "not-allowed" : "pointer",
            opacity: loading ? 0.6 : 1,
            transition: "background-color 150ms",
          }}
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </div>

      {/* Results */}
      {error && (
        <div
          style={{
            padding: "12px",
            borderRadius: "8px",
            background: "var(--aegis-signal-bear-bg)",
            color: "var(--aegis-signal-bear)",
            fontSize: "13px",
            marginBottom: "12px",
          }}
        >
          {error}
        </div>
      )}

      {searched && !loading && !error && !results.length && (
        <div
          style={{
            padding: "32px",
            textAlign: "center",
            color: "var(--aegis-text-tertiary)",
            fontSize: "14px",
          }}
        >
          No results found
        </div>
      )}

      {results.length > 0 && (
        <div style={{ maxHeight: "400px", overflowY: "auto" }}>
          {results.map((result, i) => (
            <div
              key={result.id || i}
              style={{
                padding: "12px 16px",
                borderBottom: "1px solid var(--aegis-border-subtle)",
                transition: "background-color 150ms",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--aegis-bg-elevated)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: "4px",
                }}
              >
                <span
                  style={{
                    fontSize: "12px",
                    color: "var(--aegis-text-tertiary)",
                  }}
                >
                  Score: {(result.score * 100).toFixed(0)}%
                </span>
                {result.metadata && Object.keys(result.metadata).length > 0 && (
                  <span
                    style={{
                      fontSize: "12px",
                      color: "var(--aegis-text-tertiary)",
                    }}
                  >
                    {Object.entries(result.metadata)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(" | ")}
                  </span>
                )}
              </div>
              <p
                style={{
                  fontSize: "14px",
                  color: "var(--aegis-text-secondary)",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                {result.document}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}