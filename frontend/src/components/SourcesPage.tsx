import type { Sources } from "../types";

export function SourcesPage({ s }: { s: Sources | null }) {
  if (!s) return <p className="muted">Carregando…</p>;
  const rows = (o: Record<string, string>) => Object.entries(o).map(([k, v]) => (<tr key={k}><th scope="row">{k.replace(/_/g, " ")}</th><td>{v}</td></tr>));
  return (
    <div className="page" data-testid="sources">
      <h2>Fontes, incertezas e limites</h2>
      <p className="callout"><b>O Copernicus DEM GLO-30 é um DSM</b> (modelo de superfície), não um levantamento topográfico. Com célula de ~30 m ele não mapeia microdesníveis nem serve para planejar trajetórias seguras de pulverizadores.</p>
      <div className="grid2">
        <section className="card"><h3>Relevo · Copernicus DEM GLO-30</h3><table><tbody>{rows(s.dem)}</tbody></table></section>
        <section className="card"><h3>Solo · SoilGrids 2.0</h3><table><tbody>{rows(s.soil)}</tbody></table>
          <h4>Atributos expostos</h4>
          <ul>{Object.entries(s.soil_properties).map(([k, v]) => (<li key={k}><b>{v.label}</b> ({k}): unidade mapeada {v.mapped_unit} → {v.unit}</li>))}</ul></section>
      </div>
      <section className="card"><h3>O que esta ferramenta não faz</h3><ul>{s.limitations.map((l) => (<li key={l}>{l}</li>))}</ul></section>
      <p className="muted">Modo atual: <b>{s.mode === "demo" ? "demonstração (amostras reais offline, região de Espírito Santo do Pinhal, SP)" : "live (fontes remotas)"}</b>.</p>
    </div>
  );
}
