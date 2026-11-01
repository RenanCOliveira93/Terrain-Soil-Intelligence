import type { AnalysisInfo, Compare, ImportResult, PropertyFull, PropertySummary, Results, Sources } from "./types";
import type { Geometry } from "geojson";

export class ApiError extends Error {
  constructor(public status: number, public detail: any) {
    super(typeof detail === "string" ? detail : detail?.message ?? `HTTP ${status}`);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/api${path}`, init);
  if (!r.ok) {
    let d: any = r.statusText;
    try { d = (await r.json()).detail ?? d; } catch { /* corpo vazio */ }
    throw new ApiError(r.status, d);
  }
  return (r.status === 204 ? undefined : await r.json()) as T;
}
const json = (method: string, body: unknown): RequestInit => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export type PropertyBody = { name: string; description?: string; geometry: Geometry; plots: { name: string; geometry: Geometry }[] };

export const api = {
  health: () => req<{ status: string; mode: string; version: string }>("/health"),
  sources: () => req<Sources>("/sources"),
  properties: (q: Record<string, string | number | boolean | undefined> = {}) => {
    const s = new URLSearchParams(Object.entries(q).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));
    return req<PropertySummary[]>(`/properties?${s}`);
  },
  property: (id: string) => req<PropertyFull>(`/properties/${id}`),
  createProperty: (b: PropertyBody) => req<PropertyFull>("/properties", json("POST", b)),
  updateProperty: (id: string, b: PropertyBody) => req<PropertyFull>(`/properties/${id}`, json("PUT", b)),
  deleteProperty: (id: string) => req<void>(`/properties/${id}`, { method: "DELETE" }),
  importFile: (f: File) => { const fd = new FormData(); fd.append("file", f); return req<ImportResult>("/import", { method: "POST", body: fd }); },
  startAnalysis: (id: string, body: { contour_interval_m?: number | null; soil: boolean }) =>
    req<{ analysis_id: string }>(`/properties/${id}/analyses`, json("POST", body)),
  job: (id: string) => req<AnalysisInfo>(`/jobs/${id}`),
  results: (id: string) => req<Results>(`/analyses/${id}`),
  compare: (id: string, a: string, b: string) => req<Compare>(`/analyses/${id}/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  contours: (id: string) => req<GeoJSON.FeatureCollection>(`/analyses/${id}/contours`),
  layerUrl: (id: string, layer: string) => `${location.origin}/api/analyses/${id}/layers/${encodeURIComponent(layer)}`,
  exportUrl: (id: string, kind: string) => `/api/analyses/${id}/export/${kind}`,
};
