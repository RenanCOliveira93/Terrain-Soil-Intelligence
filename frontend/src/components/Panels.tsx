import { useState } from "react";
import { fmt, fmtInterval, zoneLabel } from "../format";
import type { AnalysisInfo, LayerDef, Results, SoilZone } from "../types";
import { AspectRose, Hypsometry, SlopeBars, SoilIntervals } from "./Charts";
import { Legend } from "./Legend";

export function JobBar({ job }: { job: AnalysisInfo | null }) {
  if (!job || job.status === "done") return null;
  return (
    <div className={`job ${job.status}`} role="status" aria-live="polite" data-testid="job">
      <div className="job-line"><strong>{job.status === "failed" ? "Falhou" : "Processando"}</strong><span>{job.status === "failed" ? job.error : job.stage}</span><span>{Math.round(job.progress * 100)}%</span></div>
      <div className="progress"><span style={{ width: `${job.progress * 100}%` }} /></div>
    </div>
  );
}

export function LayerPanel(p: {
  layers: LayerDef[]; layerId: string | null; setLayerId: (id: string | null) => void; opacity: number; setOpacity: (n: number) => void;
  showContours: boolean; setShowContours: (b: boolean) => void; showZones: boolean; setShowZones: (b: boolean) => void;
  basemap: boolean; setBasemap: (b: boolean) => void; interval?: number;
}) {
  const terrain = p.layers.filter((l) => !l.soil);
  const soil = p.layers.filter((l) => l.soil);
  const props = [...new Map(soil.map((l) => [l.soil!.prop, l.soil!.prop_label])).entries()];
  const depths = [...new Set(soil.map((l) => l.soil!.depth))];
  const cur = p.layers.find((l) => l.id === p.layerId)?.soil;
  const [sel, setSel] = useState({ prop: props[0]?.[0] ?? "clay", depth: depths[0] ?? "0-5cm", kind: "mean" as "mean" | "pi" });
  const idOf = (s: typeof sel) => `soil:${s.prop}:${s.depth}:${s.kind}`;
  const change = (patch: Partial<typeof sel>) => { const n = { ...sel, ...patch }; setSel(n); if (cur) p.setLayerId(idOf(n)); };
  return (
    <section className="card layers" aria-label="Camadas">
      <h3>Camadas</h3>
      <label className="check"><input type="checkbox" checked={p.showZones} onChange={(e) => p.setShowZones(e.target.checked)} /> Propriedade e talhões</label>
      <label className="check"><input type="checkbox" checked={p.showContours} onChange={(e) => p.setShowContours(e.target.checked)} /> Curvas de nível{p.interval ? ` (${p.interval} m)` : ""} <em className="tag">interpoladas</em></label>
      <label className="check"><input type="checkbox" checked={p.basemap} onChange={(e) => p.setBasemap(e.target.checked)} /> Mapa base OSM <em className="tag">online</em></label>
      <fieldset>
        <legend>Terreno</legend>
        <label className="radio"><input type="radio" name="layer" checked={p.layerId === null} onChange={() => p.setLayerId(null)} /> Nenhuma</label>
        {terrain.map((l) => (<label className="radio" key={l.id}><input type="radio" name="layer" checked={p.layerId === l.id} onChange={() => p.setLayerId(l.id)} /> {l.label}</label>))}
      </fieldset>
      {soil.length > 0 && (
        <fieldset>
          <legend>Solo (SoilGrids, 250 m)</legend>
          <label className="radio"><input type="radio" name="layer" checked={!!cur} onChange={() => p.setLayerId(idOf(sel))} aria-label="Camada de solo" /> Mostrar camada de solo</label>
          <div className="soil-sel">
            <select value={sel.prop} onChange={(e) => change({ prop: e.target.value })} aria-label="Atributo do solo">{props.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            <select value={sel.depth} onChange={(e) => change({ depth: e.target.value })} aria-label="Profundidade">{depths.map((d) => <option key={d} value={d}>{d}</option>)}</select>
          </div>
          <div className="seg" role="group" aria-label="Variável">
            <button className={sel.kind === "mean" ? "on" : ""} onClick={() => change({ kind: "mean" })}>Média predita</button>
            <button className={sel.kind === "pi" ? "on" : ""} onClick={() => change({ kind: "pi" })}>Largura do intervalo 90%</button>
          </div>
        </fieldset>
      )}
      <label className="slider">Opacidade <input type="range" min={0.1} max={1} step={0.05} value={p.opacity} onChange={(e) => p.setOpacity(+e.target.value)} /></label>
      <Legend layer={p.layers.find((l) => l.id === p.layerId)} />
    </section>
  );
}

const Kpi = ({ label, value, sub }: { label: string; value: string; sub?: string }) => (
  <div className="kpi"><span>{label}</span><strong>{value}</strong>{sub && <small>{sub}</small>}</div>
);

export function Indicators({ r, zone, setZone }: { r: Results; zone: string; setZone: (z: string) => void }) {
  const z = r.zones[zone] ?? r.zones.property;
  const m = zone === "property" ? r.metrics.property : r.metrics.plots[zone];
  return (
    <div className="indicators" data-testid="indicators">
      <div className="zone-pick" role="tablist" aria-label="Zona analisada">
        {Object.keys(r.zones).map((k) => (<button key={k} role="tab" aria-selected={k === zone} className={k === zone ? "on" : ""} onClick={() => setZone(k)}>{zoneLabel(k)}</button>))}
      </div>
      <div className="kpis">
        <Kpi label="Área" value={fmt(m.area_ha, 1, " ha")} sub={`UTM · geodésica ${fmt(m.area_ha_geodesic, 1)} ha`} />
        <Kpi label="Perímetro" value={fmt(m.perimeter_m / 1000, 2, " km")} />
        <Kpi label="Elevação média" value={fmt(z.elevation_m.mean, 0, " m")} sub={`${fmt(z.elevation_m.min, 0)}–${fmt(z.elevation_m.max, 0)} m (DSM)`} />
        <Kpi label="Declividade média" value={fmt(z.slope_pct.mean, 1, " %")} sub={`P95 ${fmt(z.slope_pct.p95, 1)} %`} />
        <Kpi label="Aspecto dominante" value={z.aspect.dominant ?? "–"} sub={`plano ${fmt(z.aspect.flat_share * 100, 1)}%`} />
        <Kpi label="Pixels (~30 m)" value={z.n_pixels.toLocaleString("pt-BR")} sub={`CRS ${m.crs_projected}`} />
      </div>
      {z.quality_flags.map((f) => (<p className="flag" key={f}>⚠ {f}</p>))}
      <h4>Declividade (classes EMBRAPA)</h4><SlopeBars z={z} />
      <div className="two"><div><h4>Hipsometria</h4><Hypsometry z={z} /></div><div><h4>Orientação</h4><AspectRose z={z} /></div></div>
    </div>
  );
}

export function ZoneTable({ r, onPick }: { r: Results; onPick: (z: string) => void }) {
  return (
    <div className="table-wrap">
      <table data-testid="zone-table">
        <thead><tr><th>Zona</th><th>Área (ha)</th><th>Elev. mín</th><th>Elev. méd</th><th>Elev. máx</th><th>Decliv. méd (%)</th><th>P95 (%)</th><th>Aspecto</th><th>Pixels</th><th>Avisos</th></tr></thead>
        <tbody>
          {Object.entries(r.zones).map(([k, z]) => {
            const m = k === "property" ? r.metrics.property : r.metrics.plots[k];
            return (
              <tr key={k} onClick={() => onPick(k)} className="click">
                <td>{zoneLabel(k)}</td><td>{fmt(m.area_ha, 1)}</td><td>{fmt(z.elevation_m.min, 0)}</td><td>{fmt(z.elevation_m.mean, 0)}</td><td>{fmt(z.elevation_m.max, 0)}</td>
                <td>{fmt(z.slope_pct.mean, 1)}</td><td>{fmt(z.slope_pct.p95, 1)}</td><td>{z.aspect.dominant ?? "–"}</td><td>{z.n_pixels}</td>
                <td>{z.quality_flags.length ? <span className="badge warn" title={z.quality_flags.join(" ")}>⚠ {z.quality_flags.length}</span> : "–"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function SoilPanel({ r, zone, depth, setDepth }: { r: Results; zone: string; depth: string; setDepth: (d: string) => void }) {
  const soil = r.soil;
  if (!soil) return <p className="muted">Solo desativado nesta análise.</p>;
  if ("error" in soil) return <p className="flag">⚠ SoilGrids indisponível: {soil.error}. A análise de relevo segue válida.</p>;
  const zs: SoilZone = soil.zones[zone] ?? soil.zones.property;
  return (
    <div data-testid="soil-panel">
      <div className="zone-pick" role="tablist" aria-label="Profundidade">
        {soil.depths.map((d) => (<button key={d} role="tab" aria-selected={d === depth} className={d === depth ? "on" : ""} onClick={() => setDepth(d)}>{d}</button>))}
      </div>
      <p className="note">Valor = média predita; entre colchetes, o <b>intervalo de predição de 90% por pixel</b> (Q0.05–Q0.95). Não é intervalo de confiança da média da zona, e a faixa é larga: o modelo (250 m) não permite concluir diferenças finas entre zonas.</p>
      <SoilIntervals zone={zs} depth={depth} />
      <div className="table-wrap">
        <table>
          <thead><tr><th>Atributo</th><th>Unidade</th><th>Média [Q0.05–Q0.95]</th><th>Largura 90%</th><th>Pixels</th><th>Amostragem</th></tr></thead>
          <tbody>
            {Object.entries(zs.properties).map(([k, p]) => {
              const d = p.depths[depth];
              return (<tr key={k}><td>{p.label}</td><td>{p.unit}</td><td>{d?.available ? fmtInterval(d.mean, d.q05_mean, d.q95_mean) : "–"}</td><td>{fmt(d?.pi90_width_mean, 1)}</td><td>{d?.n_pixels}</td><td>{d?.sampling}</td></tr>);
            })}
          </tbody>
        </table>
      </div>
      {zs.texture_class_of_means[depth] && <p className="note">Classe textural USDA da <i>média predita</i>: <b>{zs.texture_class_of_means[depth]}</b>. Com estes intervalos, a classe real pode ser outra.</p>}
      {zs.quality_flags.map((f) => (<p className="flag" key={f}>⚠ {f}</p>))}
      <p className="note">Profundidades em cm; unidades já convertidas das unidades mapeadas (pH×10, dg/kg, g/kg). Fonte: SoilGrids 2.0, ISRIC, CC BY 4.0.</p>
    </div>
  );
}

export function Warnings({ r }: { r: Results }) {
  const items = [...r.warnings, ...r.geometry_issues.filter((i) => i.severity !== "info").map((i) => i.message)];
  if (!items.length) return null;
  return <div className="card warn-card">{items.map((w, i) => (<p key={i} className="flag">⚠ {w}</p>))}</div>;
}
