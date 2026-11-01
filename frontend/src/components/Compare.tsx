import { useEffect, useState } from "react";
import { api } from "../api";
import { fmt, zoneLabel } from "../format";
import type { Compare as C, Results } from "../types";

export function ComparePanel({ analysisId, r }: { analysisId: string; r: Results }) {
  const names = Object.keys(r.zones);
  const plots = names.filter((n) => n !== "property");
  const [a, setA] = useState(plots[0] ?? "property");
  const [b, setB] = useState(plots[1] ?? "property");
  const [c, setC] = useState<C | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setErr(null);
    api.compare(analysisId, a, b).then(setC).catch((e) => { setC(null); setErr(String(e.message)); });
  }, [analysisId, a, b]);
  const unit: Record<string, string> = { elevation_mean_m: "m", slope_mean_pct: "%", slope_p95_pct: "%" };
  const lab: Record<string, string> = { elevation_mean_m: "Elevação média", slope_mean_pct: "Declividade média", slope_p95_pct: "Declividade P95", aspect_dominant: "Aspecto dominante" };
  return (
    <div data-testid="compare">
      <div className="row">
        <label>Zona A <select value={a} onChange={(e) => setA(e.target.value)}>{names.map((n) => <option key={n} value={n}>{zoneLabel(n)}</option>)}</select></label>
        <label>Zona B <select value={b} onChange={(e) => setB(e.target.value)}>{names.map((n) => <option key={n} value={n}>{zoneLabel(n)}</option>)}</select></label>
      </div>
      {err && <p className="flag">⚠ {err}</p>}
      {c && (
        <>
          <h4>Terreno (DSM GLO-30)</h4>
          <div className="table-wrap"><table><thead><tr><th>Indicador</th><th>{zoneLabel(c.a)}</th><th>{zoneLabel(c.b)}</th><th>Δ (B − A)</th></tr></thead><tbody>
            {Object.entries(c.terrain).map(([k, v]) => (
              <tr key={k}><td>{lab[k]}</td><td>{typeof v.a === "number" ? fmt(v.a, 1) : v.a ?? "–"}</td><td>{typeof v.b === "number" ? fmt(v.b, 1) : v.b ?? "–"}</td><td>{v.delta === null ? "–" : `${v.delta >= 0 ? "+" : ""}${fmt(v.delta, 1)} ${unit[k]}`}</td></tr>
            ))}</tbody></table></div>
          <p className="note">Diferenças de terreno são calculadas sobre pixels de ~30 m de um modelo de superfície: não distinguem microrrelevo, e valores próximos podem estar dentro do erro vertical especificado (&lt; 4 m LE90).</p>
          <h4>Solo (SoilGrids)</h4>
          {c.soil.length === 0 ? <p className="muted">Sem dados de solo comparáveis.</p> : (
            <div className="table-wrap"><table><thead><tr><th>Atributo</th><th>Prof.</th><th>A</th><th>B</th><th>Δ</th><th>Leitura</th></tr></thead><tbody>
              {c.soil.filter((s) => s.depth === c.soil[0].depth).map((s) => (
                <tr key={s.property + s.depth}><td>{r.soil && "zones" in r.soil ? r.soil.zones.property.properties[s.property].label : s.property}</td><td>{s.depth}</td><td>{fmt(s.a, 1)}</td><td>{fmt(s.b, 1)}</td><td>{fmt(s.delta, 2)}</td><td className="muted">{s.reading}</td></tr>
              ))}</tbody></table></div>
          )}
          {c.notes.map((n) => <p className="flag" key={n}>ℹ {n}</p>)}
          {Object.entries(c.flags).flatMap(([z, fl]) => fl.map((f) => <p className="flag" key={z + f}>⚠ {zoneLabel(z)}: {f}</p>))}
        </>
      )}
    </div>
  );
}
