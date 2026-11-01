import { fmt, textOn } from "../format";
import type { LayerDef } from "../types";

export function Legend({ layer }: { layer: LayerDef | undefined }) {
  if (!layer) return null;
  const lg = layer.legend;
  return (
    <div className="legend" aria-label={`Legenda: ${layer.label}`}>
      <strong>{layer.label}</strong>
      {lg.type === "continuous" && (
        <>
          <div className="ramp" style={{ background: `linear-gradient(90deg, ${lg.stops.join(",")})` }} />
          <div className="ramp-labels"><span>{fmt(lg.min, lg.max - lg.min > 20 ? 0 : 1)}</span><span>{lg.unit}</span><span>{fmt(lg.max, lg.max - lg.min > 20 ? 0 : 1)}</span></div>
        </>
      )}
      {lg.type === "categorical" && (
        <ul>{lg.classes.map((c) => (<li key={c.label}><i style={{ background: c.color, color: textOn(c.color) }} />{c.label}</li>))}</ul>
      )}
      {lg.type === "none" && <small>Sombreamento (azimute 315°, altitude 45°)</small>}
    </div>
  );
}
