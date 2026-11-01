import { fmt } from "../format";
import type { SoilZone, TerrainZone } from "../types";

const ASPECT = ["N", "NE", "L", "SE", "S", "SO", "O", "NO"];
export const ASPECT_COLORS: Record<string, string> = { N: "#1e88e5", NE: "#00acc1", L: "#43a047", SE: "#c0ca33", S: "#fdd835", SO: "#fb8c00", O: "#e53935", NO: "#8e24aa" };
export const SLOPE_COLORS = ["#2e7d32", "#9ccc65", "#ffee58", "#fb8c00", "#e53935", "#6a1b9a"];

export function Hypsometry({ z }: { z: TerrainZone }) {
  const { elevation: e, area_above: a } = z.hypsometry;
  if (!e.length) return null;
  const W = 300, H = 170, L = 40, B = 28, T = 8, R = 8;
  const lo = e[0], hi = e[e.length - 1], span = Math.max(hi - lo, 1e-6);
  const pts = e.map((v, i) => `${L + (1 - a[i]) * (W - L - R)},${T + (1 - (v - lo) / span) * (H - T - B)}`);
  const path = "M" + pts.reverse().join("L");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Curva hipsométrica" className="chart">
      <line x1={L} y1={H - B} x2={W - R} y2={H - B} className="axis" /><line x1={L} y1={T} x2={L} y2={H - B} className="axis" />
      <path d={path} fill="none" stroke="var(--brand)" strokeWidth="2" />
      {[0, 0.5, 1].map((t) => (<g key={t}><text x={L - 4} y={T + (1 - t) * (H - T - B) + 3} textAnchor="end" className="tick">{fmt(lo + t * span, 0)}</text></g>))}
      {[0, 50, 100].map((p) => (<text key={p} x={L + (p / 100) * (W - L - R)} y={H - B + 12} textAnchor="middle" className="tick">{p}%</text>))}
      <text x={(W + L) / 2} y={H - 3} textAnchor="middle" className="tick">% da área abaixo da elevação (m)</text>
    </svg>
  );
}

export function SlopeBars({ z }: { z: TerrainZone }) {
  const max = Math.max(...z.slope_classes.map((c) => c.share), 0.01);
  return (
    <div className="bars" role="img" aria-label="Distribuição de declividade por classe">
      {z.slope_classes.map((c, i) => (
        <div className="bar-row" key={c.class}>
          <span className="bar-label">{c.class}<small> {c.min_pct}–{c.max_pct ?? "∞"}%</small></span>
          <span className="bar-track"><span style={{ width: `${(c.share / max) * 100}%`, background: SLOPE_COLORS[i] }} /></span>
          <span className="bar-val">{fmt(c.share * 100, 1, "%")}</span>
        </div>
      ))}
    </div>
  );
}

export function AspectRose({ z }: { z: TerrainZone }) {
  const S = 190, c = S / 2, R = 68;
  const vals = ASPECT.map((k) => z.aspect.octants[k] ?? 0);
  const m = Math.max(...vals, 0.01);
  const wedge = (i: number, r: number) => {
    const a0 = ((i * 45 - 22.5 - 90) * Math.PI) / 180, a1 = ((i * 45 + 22.5 - 90) * Math.PI) / 180;
    return `M${c},${c}L${c + r * Math.cos(a0)},${c + r * Math.sin(a0)}A${r},${r} 0 0 1 ${c + r * Math.cos(a1)},${c + r * Math.sin(a1)}Z`;
  };
  return (
    <svg viewBox={`0 0 ${S} ${S}`} role="img" aria-label="Rosa de orientação das encostas" className="chart rose">
      <circle cx={c} cy={c} r={R} className="grid" /><circle cx={c} cy={c} r={R / 2} className="grid" />
      {vals.map((v, i) => (<path key={i} d={wedge(i, (v / m) * R)} fill={ASPECT_COLORS[ASPECT[i]]} opacity="0.85"><title>{ASPECT[i]}: {fmt(v * 100, 1, "%")}</title></path>))}
      {ASPECT.map((k, i) => { const a = ((i * 45 - 90) * Math.PI) / 180; return <text key={k} x={c + (R + 14) * Math.cos(a)} y={c + (R + 14) * Math.sin(a) + 3} textAnchor="middle" className="tick">{k}</text>; })}
      <text x={c} y={S - 2} textAnchor="middle" className="tick">plano (&lt;1°): {fmt(z.aspect.flat_share * 100, 1, "%")}</text>
    </svg>
  );
}

/** Intervalo de predição de 90% (Q0.05–Q0.95) com a média; a largura é a mensagem principal. */
export function SoilIntervals({ zone, depth }: { zone: SoilZone; depth: string }) {
  const rows = Object.entries(zone.properties).map(([k, p]) => ({ k, p, d: p.depths[depth] })).filter((r) => r.d?.available);
  const W = 300, L = 118, R = 10, rowH = 26;
  const scale: Record<string, [number, number]> = { phh2o: [3, 9], soc: [0, 120], clay: [0, 100], silt: [0, 100], sand: [0, 100] };
  return (
    <svg viewBox={`0 0 ${W} ${rows.length * rowH + 22}`} className="chart" role="img" aria-label={`Intervalos de predição de 90% do SoilGrids, ${depth}`}>
      {rows.map(({ k, p, d }, i) => {
        const [lo, hi] = scale[k] ?? [0, 100];
        const x = (v: number) => L + ((Math.min(Math.max(v, lo), hi) - lo) / (hi - lo)) * (W - L - R);
        const y = i * rowH + 14;
        return (
          <g key={k}>
            <text x={L - 6} y={y + 3} textAnchor="end" className="tick">{p.label.replace("Carbono orgânico do solo", "Carbono org.")} ({p.unit})</text>
            <line x1={x(lo)} x2={x(hi)} y1={y} y2={y} className="grid" />
            <line x1={x(d.q05_mean!)} x2={x(d.q95_mean!)} y1={y} y2={y} stroke="var(--brand-2)" strokeWidth="6" strokeLinecap="round" opacity="0.35" />
            <circle cx={x(d.mean!)} cy={y} r="4.2" fill="var(--brand)"><title>{p.label}: {fmt(d.mean, 1)} [{fmt(d.q05_mean, 1)}–{fmt(d.q95_mean, 1)}] {p.unit}</title></circle>
          </g>
        );
      })}
      <text x={W / 2} y={rows.length * rowH + 18} textAnchor="middle" className="tick">ponto = média · faixa = intervalo de 90%</text>
    </svg>
  );
}
