const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface WeightHistoryItem {
  factor_name: string;
  weight: number;
  previous_weight: number | null;
  changed_by: string;
  sample_count: number;
  updated_at: string | null;
}

export interface WeightSnapshot {
  factors: Record<string, {
    weight: number;
    previous_weight: number | null;
    changed_by: string;
    observation_period_active: boolean;
    sample_count: number;
    updated_at: string | null;
  }>;
  observation_period_active: boolean;
  observation_days_remaining: number | null;
}

export interface MemorySearchResult {
  id: string | number;
  document: string;
  metadata: Record<string, unknown>;
  score: number;
}

export async function fetchWeightHistory(
  factor?: string
): Promise<WeightHistoryItem[]> {
  const qs = factor ? `?factor=${encodeURIComponent(factor)}` : "";
  const res = await fetch(`${API_BASE}/memory/weights/history${qs}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function fetchCurrentWeights(): Promise<WeightSnapshot> {
  const res = await fetch(`${API_BASE}/memory/weights`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function searchMemory(query: string): Promise<MemorySearchResult[]> {
  const res = await fetch(
    `${API_BASE}/memory/search?q=${encodeURIComponent(query)}`
  );
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}