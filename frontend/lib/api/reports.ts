const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface ReportMeta {
  type: string;
  date: string;
  period: { start: string; end: string };
}

export interface ReportContent {
  type: string;
  date: string;
  period: { start: string; end: string };
  sections: Record<string, unknown>;
  markdown: string;
}

export async function fetchReports(
  reportType?: string
): Promise<ReportMeta[]> {
  const qs = reportType ? `?report_type=${encodeURIComponent(reportType)}` : "";
  const res = await fetch(`${API_BASE}/reports${qs}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function fetchReport(
  reportType: string,
  reportDate: string
): Promise<ReportContent> {
  const res = await fetch(
    `${API_BASE}/reports/${encodeURIComponent(reportType)}/${encodeURIComponent(reportDate)}`
  );
  if (!res.ok) throw new Error(`API ${res.status}`);
  const data = await res.json();
  if (data.error) throw new Error(data.error);
  return data;
}

export async function generateReport(
  reportType: "weekly" | "monthly"
): Promise<ReportContent> {
  const res = await fetch(
    `${API_BASE}/reports/generate?report_type=${reportType}`,
    { method: "POST" }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `API ${res.status}`);
  }
  return res.json();
}