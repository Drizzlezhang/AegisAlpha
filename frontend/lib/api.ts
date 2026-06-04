const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";

export async function fetcher<T>(url: string): Promise<T> {
  if (USE_MOCK) {
    const mockPath = url
      .replace(/^\/|\?.*$/g, "")
      .replace(/\//g, "_")
      .replace(/-/g, "_");
    try {
      const mod = await import(`@/mocks/${mockPath}.json`);
      return mod.default as T;
    } catch {
      throw new Error(`Mock not found: ${mockPath}`);
    }
  }
  const res = await fetch(`${API_BASE}${url}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function apiPost<T>(
  url: string,
  body: unknown
): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export async function apiDelete(url: string): Promise<void> {
  const res = await fetch(`${API_BASE}${url}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
}

export const api = {
  pipeline: {
    latest: () => "/pipeline/latest",
    runs: (params?: Record<string, string>) =>
      `/pipeline/runs?${new URLSearchParams(params || {})}`,
    trigger: (mode: string) => apiPost("/pipeline/run", { mode }),
  },
  portfolio: {
    snapshot: () => "/portfolio/snapshot",
    greeks: () => "/portfolio/greeks",
    deltaDollars: () => "/portfolio/delta-dollars",
    health: () => "/portfolio/health",
  },
  recommendations: {
    list: () => "/recommendations",
    detail: (id: number) => `/recommendations/${id}`,
  },
  triggers: {
    list: () => "/triggers",
    cancel: (id: number) => apiDelete(`/triggers/${id}`),
  },
  flows: {
    etf: () => "/flows/etf",
    sector: () => "/flows/sector",
    smartMoney: (ticker: string) => `/flows/smart-money/${ticker}`,
  },
};
