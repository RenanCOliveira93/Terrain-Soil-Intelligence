import MapboxDraw from "@mapbox/mapbox-gl-draw";
import "@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { bboxToBounds, imageCoords } from "../format";
import { drawStyles } from "./drawStyles";
import type { PropertyFull } from "../types";

// mapbox-gl-draw usa classes CSS do Mapbox; apontamos para as do MapLibre.
const C = (MapboxDraw as any).constants.classes;
C.CANVAS = "maplibregl-canvas"; C.CONTROL_BASE = "maplibregl-ctrl"; C.CONTROL_PREFIX = "maplibregl-ctrl-"; C.CONTROL_GROUP = "maplibregl-ctrl-group";
C.ATTRIBUTION = "maplibregl-ctrl-attrib";

export type MapMode = "view" | "draw-property" | "draw-plot" | "edit";
export type MapHandle = { getDrawn: () => FeatureCollection; fitTo: (bbox: number[]) => void };

type Props = {
  property: PropertyFull | null;
  mode: MapMode;
  onDrawn: (g: Geometry) => void;
  overlay: { url: string; bounds: number[] } | null;
  opacity: number;
  contours: FeatureCollection | null;
  showContours: boolean;
  showZones: boolean;
  basemap: boolean;
  selectedZone: string | null;
  onZoneClick: (name: string) => void;
};

const PLOT_COLORS = ["#1565c0", "#ef6c00", "#6a1b9a", "#00838f", "#ad1457", "#558b2f"];

export const MapView = forwardRef<MapHandle, Props>(function MapView(p, ref) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const draw = useRef<MapboxDraw | null>(null);
  const [ready, setReady] = useState(false);
  const cb = useRef(p);
  cb.current = p;

  useImperativeHandle(ref, () => ({
    getDrawn: () => draw.current!.getAll() as FeatureCollection,
    fitTo: (b) => map.current?.fitBounds(bboxToBounds(b), { padding: 60, duration: 600 }),
  }));

  useEffect(() => {
    const m = new maplibregl.Map({
      container: el.current!,
      style: {
        version: 8,
        sources: { osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, maxzoom: 19, attribution: "© OpenStreetMap contributors" } },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": "#e6ece6" } },
          { id: "osm", type: "raster", source: "osm", layout: { visibility: "none" } },
        ],
      },
      center: [-46.78, -22.2], zoom: 12, attributionControl: { compact: true },
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    const d = new MapboxDraw({ displayControlsDefault: false, defaultMode: "simple_select", styles: drawStyles });
    m.addControl(d as unknown as maplibregl.IControl);
    draw.current = d;
    m.on("draw.create", (e: any) => {
      const f = e.features[0] as Feature;
      if (cb.current.mode === "draw-property" || cb.current.mode === "draw-plot") {
        d.delete(String(f.id));
        cb.current.onDrawn(f.geometry);
      }
    });
    m.on("load", () => {
      m.addSource("zones", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addSource("contours", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({ id: "zones-fill", type: "fill", source: "zones", paint: { "fill-color": ["get", "color"], "fill-opacity": ["case", ["==", ["get", "selected"], 1], 0.28, ["==", ["get", "kind"], "plot"], 0.08, 0] } });
      m.addLayer({ id: "contours", type: "line", source: "contours", paint: { "line-color": "#2b2b2b", "line-width": 0.7, "line-opacity": 0.75 } });
      m.addLayer({ id: "zones-line", type: "line", source: "zones", paint: { "line-color": ["get", "color"], "line-width": ["case", ["==", ["get", "kind"], "property"], 2.6, 1.8] } });
      m.on("click", "zones-fill", (e) => { const n = e.features?.[0]?.properties?.name; if (n && cb.current.mode === "view") cb.current.onZoneClick(String(n)); });
      m.on("mouseenter", "zones-fill", () => (m.getCanvas().style.cursor = "pointer"));
      m.on("mouseleave", "zones-fill", () => (m.getCanvas().style.cursor = ""));
      setReady(true);
    });
    map.current = m;
    (window as any).__tsiMap = m; // facilita depuração e testes E2E
    return () => { m.remove(); map.current = null; };
  }, []);

  // polígonos
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    const feats: Feature[] = [];
    if (p.property && p.showZones && p.mode !== "edit") {
      feats.push({ type: "Feature", geometry: p.property.geometry, properties: { name: "property", kind: "property", color: "#14532d", selected: p.selectedZone === "property" ? 1 : 0 } });
      p.property.plots.forEach((pl, i) => feats.push({ type: "Feature", geometry: pl.geometry, properties: { name: pl.name, kind: "plot", color: PLOT_COLORS[i % PLOT_COLORS.length], selected: p.selectedZone === pl.name ? 1 : 0 } }));
    }
    (m.getSource("zones") as maplibregl.GeoJSONSource).setData({ type: "FeatureCollection", features: feats });
  }, [ready, p.property, p.showZones, p.mode, p.selectedZone]);

  // ajuste de enquadramento
  const lastId = useRef<string | null>(null);
  useEffect(() => {
    if (!ready || !p.property || lastId.current === p.property.id) return;
    lastId.current = p.property.id;
    const g = p.property.geometry as any;
    const pts: number[][] = (g.type === "Polygon" ? [g.coordinates] : g.coordinates).flat(2);
    const xs = pts.map((c) => c[0]), ys = pts.map((c) => c[1]);
    map.current!.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]], { padding: 70, duration: 0 });
  }, [ready, p.property]);

  // curvas de nível
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    (m.getSource("contours") as maplibregl.GeoJSONSource).setData(p.showContours && p.contours ? p.contours : { type: "FeatureCollection", features: [] });
  }, [ready, p.contours, p.showContours]);

  // camada raster
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    if (m.getLayer("overlay")) m.removeLayer("overlay");
    if (m.getSource("overlay")) m.removeSource("overlay");
    if (!p.overlay) return;
    m.addSource("overlay", { type: "image", url: p.overlay.url, coordinates: imageCoords(p.overlay.bounds) });
    m.addLayer({ id: "overlay", type: "raster", source: "overlay", paint: { "raster-opacity": p.opacity, "raster-resampling": "nearest" } }, "contours");
  }, [ready, p.overlay]);
  useEffect(() => { if (ready && map.current?.getLayer("overlay")) map.current.setPaintProperty("overlay", "raster-opacity", p.opacity); }, [ready, p.opacity]);

  useEffect(() => { if (ready) map.current!.setLayoutProperty("osm", "visibility", p.basemap ? "visible" : "none"); }, [ready, p.basemap]);

  // modos de desenho/edição
  useEffect(() => {
    const d = draw.current;
    if (!ready || !d) return;
    if (p.mode === "draw-property" || p.mode === "draw-plot") { d.deleteAll(); d.changeMode("draw_polygon"); }
    else if (p.mode === "edit" && p.property) {
      d.deleteAll();
      d.add({ type: "FeatureCollection", features: [
        { type: "Feature", id: "__property", geometry: p.property.geometry, properties: {} },
        ...p.property.plots.map((pl) => ({ type: "Feature" as const, id: `plot:${pl.name}`, geometry: pl.geometry, properties: {} })),
      ] } as FeatureCollection);
      d.changeMode("simple_select");
    } else { d.deleteAll(); d.changeMode("simple_select"); }
  }, [ready, p.mode, p.property]);

  return <div ref={el} className="map" data-testid="map" />;
});
