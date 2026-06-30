const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface KOLSource {
  id: number;
  name: string;
  platform: string;
  handle: string;
  reliability_score: number;
  total_calls: number;
  successful_calls: number;
  enabled: boolean;
}

export interface KOLCall {
  id: number;
  kol_source_id: number;
  ticker: string;
  direction: string;
  call_date: string | null;
  call_price: number;
  attribution_status: string;
  pnl_30d: number | null;
  pnl_60d: number | null;
  source_url: string | null;
  content_snippet: string | null;
}

export async function fetchKOLSources(enabledOnly = true): Promise<KOLSource[]> {
  const res = await fetch(`${API_BASE}/kol/sources?enabled_only=${enabledOnly}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  const data = await res.json();
  return data.items;
}

export async function fetchKOLCalls(params: {
  limit?: number;
  ticker?: string;
}): Promise<KOLCall[]> {
  const qs = new URLSearchParams();
  if (params.limit) qs.set("limit", String(params.limit));
  if (params.ticker) qs.set("ticker", params.ticker);
  const res = await fetch(`${API_BASE}/kol/calls?${qs}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  const data = await res.json();
  return data.items;
}

export async function fetchAttributionReport(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/kol/attribution/report`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}