/** Estilos do mapbox-gl-draw compatíveis com MapLibre (o padrão usa `line-dasharray` num formato que o MapLibre rejeita). */
const BRAND = "#b45309";
export const drawStyles: any[] = [
  { id: "gl-draw-polygon-fill", type: "fill", filter: ["all", ["==", "$type", "Polygon"], ["!=", "mode", "static"]], paint: { "fill-color": BRAND, "fill-opacity": 0.14 } },
  { id: "gl-draw-line", type: "line", filter: ["all", ["any", ["==", "$type", "Polygon"], ["==", "$type", "LineString"]], ["!=", "mode", "static"]],
    layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": BRAND, "line-width": 2.4, "line-dasharray": ["literal", [2, 1.5]] } },
  { id: "gl-draw-vertex-halo", type: "circle", filter: ["all", ["==", "meta", "vertex"], ["==", "$type", "Point"], ["!=", "mode", "static"]], paint: { "circle-radius": 7, "circle-color": "#fff" } },
  { id: "gl-draw-vertex", type: "circle", filter: ["all", ["==", "meta", "vertex"], ["==", "$type", "Point"], ["!=", "mode", "static"]], paint: { "circle-radius": 4.5, "circle-color": BRAND } },
  { id: "gl-draw-midpoint", type: "circle", filter: ["all", ["==", "meta", "midpoint"], ["==", "$type", "Point"]], paint: { "circle-radius": 3, "circle-color": BRAND, "circle-opacity": 0.6 } },
];
