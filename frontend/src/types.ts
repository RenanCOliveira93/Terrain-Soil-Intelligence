import type { Geometry } from "geojson";

export type Issue = { code: string; severity: "error" | "warning" | "info"; message: string; feature?: string | null };

export type Metrics = {
  crs_projected: string; crs_projected_name: string; area_ha: number; perimeter_m: number; area_ha_geodesic: number;
  perimeter_m_geodesic: number; area_diff_pct: number; centroid: { lon: number; lat: number }; bbox: number[]; n_parts: number;
};

export type PropertySummary = {
  id: string; name: string; description: string; area_ha: number; is_demo: boolean; n_plots: number; bbox?: number[];
  last_analysis?: AnalysisInfo | null;
};
export type PlotOut = { id: string; name: string; area_ha: number; geometry: Geometry };
export type PropertyFull = PropertySummary & { geometry: Geometry; plots: PlotOut[]; analyses: AnalysisInfo[]; issues?: Issue[] };

export type AnalysisInfo = {
  id: string; property_id: string; status: "queued" | "running" | "done" | "failed"; progress: number; stage: string;
  error?: string | null; summary: Record<string, number>; created_at: string; mode: string;
};

export type Legend =
  | { type: "continuous"; unit: string; min: number; max: number; stops: string[] }
  | { type: "categorical"; unit: string; classes: { label: string; color: string }[] }
  | { type: "none" };
export type LayerDef = { id: string; label: string; group: string; unit: string; legend: Legend; bounds: number[]; soil?: { prop: string; depth: string; kind: "mean" | "pi"; prop_label: string } };

export type TerrainZone = {
  n_pixels: number;
  elevation_m: { min: number | null; max: number | null; mean: number | null; median: number | null; std: number | null; range: number | null; percentile_5: number | null; percentile_95: number | null };
  slope_pct: { mean: number | null; median: number | null; p95: number | null; max: number | null };
  slope_classes: { class: string; min_pct: number; max_pct: number | null; share: number }[];
  aspect: { flat_share: number; octants: Record<string, number>; mean_dir_deg: number | null; resultant_length: number | null; dominant: string | null };
  hypsometry: { elevation: number[]; area_above: number[] };
  quality_flags: string[];
};

export type SoilCell = { available?: boolean; mean?: number; q05_mean?: number; q95_mean?: number; q50_mean?: number; n_pixels: number; sampling: string; pi90_width_mean?: number; spatial_sd_of_pixel_means?: number | null };
export type SoilZone = {
  properties: Record<string, { label: string; unit: string; depths: Record<string, SoilCell> }>;
  texture_class_of_means: Record<string, string | null>; quality_flags: string[]; soil_pixel_ha: number;
};

export type Results = {
  name: string; mode: "demo" | "live"; created_at: string; params: { contour_interval_m: number; soil: boolean };
  geometry_issues: Issue[]; metrics: { property: Metrics; plots: Record<string, Metrics> };
  dem: Record<string, any>; zones: Record<string, TerrainZone>;
  soil: { meta: Record<string, string>; depths: string[]; zones: Record<string, SoilZone> } | { error: string } | null;
  layers: LayerDef[]; warnings: string[]; limitations: string[]; contours_meta: { interval_m: number; warning: string };
};

export type Compare = {
  a: string; b: string; notes: string[];
  terrain: Record<string, { a: number | string | null; b: number | string | null; delta: number | null }>;
  soil: { property: string; depth: string; a: number; b: number; delta: number; intervals_overlap: boolean; identical_pixels: boolean; reading: string }[];
  flags: Record<string, string[]>;
};

export type Sources = { dem: Record<string, string>; soil: Record<string, string>; limitations: string[]; mode: string; soil_properties: Record<string, { label: string; unit: string; mapped_unit: string }> };

export type ImportedFeature = { name: string; ok: boolean; repaired: boolean; issues: Issue[]; geometry: Geometry | null; metrics: Metrics | null };
export type ImportResult = { filename: string; source_crs: string; notes: string[]; features: ImportedFeature[] };
