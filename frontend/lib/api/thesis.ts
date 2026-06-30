const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface ThesisCard {
  id: number;
  ticker: string;
  direction: string;
  entry_mode: string;
  thesis_valid_status: string;
  entry_date: string | null;
  entry_price: number;
  target_price: number | null;
  stop_price: number | null;
  actual_pnl_pct: number | null;
  judgment_score: number | null;
  execution_score: number | null;
}

export interface ThesisDetail extends ThesisCard {
  key_assumptions: string[];
  factor_snapshot: Record<string, number>;
  close_date: string | null;
  close_price: number | null;
  close_reason: string | null;
  re_entry_flagged: boolean;
}

export async function fetchTheses(
  filters: Record<string, string>
): Promise<ThesisCard[]> {
  const params = new URLSearchParams();
  if (filters.status && filters.status !== "all") params.set("status", filters.status);
  if (filters.direction && filters.direction !== "all") params.set("direction", filters.direction);
  if (filters.ticker) params.set("ticker", filters.ticker);

  const res = await fetch(`${API_BASE}/thesis?${params}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  const data = await res.json();
  return data.items;
}

export async function fetchThesisDetail(id: number): Promise<ThesisDetail> {
  const res = await fetch(`${API_BASE}/thesis/${id}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function closeThesis(
  id: number,
  data: {
    close_price: number;
    judgment_score: number;
    execution_score: number;
    close_reason: string;
  }
): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/thesis/${id}/close`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `API ${res.status}`);
  }
  return res.json();
}