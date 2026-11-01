import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { ComparePanel as Compare } from "./components/Compare";
import { ImportDialog, Issues, NameDialog } from "./components/Dialogs";
import { MapHandle, MapMode, MapView } from "./components/MapView";
import { Indicators, JobBar, LayerPanel, SoilPanel, Warnings, ZoneTable } from "./components/Panels";
import { SourcesPage } from "./components/SourcesPage";
import { fmt } from "./format";
import type { AnalysisInfo, Issue, PropertyFull, PropertySummary, Results, Sources } from "./types";
import type { Geometry } from "geojson";

type View = "map" | "properties" | "compare" | "soil" | "sources";
const NAV: { id: View; label: string; icon: string }[] = [
  { id: "map", label: "Mapa e análise", icon: "◭" }, { id: "properties", label: "Propriedades", icon: "▦" },
  { id: "compare", label: "Comparar talhões", icon: "⇄" }, { id: "soil", label: "Solo", icon: "◍" }, { id: "sources", label: "Fontes e limites", icon: "ⓘ" },
];
type Toast = { kind: "ok" | "err"; text: string; issues?: Issue[] };

export default function App() {
  const [view, setView] = useState<View>("map");
  const [mode, setMode] = useState("demo");
  const [sources, setSources] = useState<Sources | null>(null);
  const [list, setList] = useState<PropertySummary[]>([]);
  const [filters, setFilters] = useState({ q: "", min: "", max: "", analyzed: false });
  const [prop, setProp] = useState<PropertyFull | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [results, setResults] = useState<Results | null>(null);
  const [contours, setContours] = useState<GeoJSON.FeatureCollection | null>(null);
  const [job, setJob] = useState<AnalysisInfo | null>(null);
  const [layerId, setLayerId] = useState<string | null>("slope");
  const [opacity, setOpacity] = useState(0.8);
  const [showContours, setShowContours] = useState(true);
  const [showZones, setShowZones] = useState(true);
  const [basemap, setBasemap] = useState(false);
  const [zone, setZone] = useState("property");
  const [depth, setDepth] = useState("0-5cm");
  const [mapMode, setMapMode] = useState<MapMode>("view");
  const [pendingGeom, setPendingGeom] = useState<Geometry | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [interval, setIntervalM] = useState("");
  const [withSoil, setWithSoil] = useState(true);
  const mapRef = useRef<MapHandle>(null);

  const say = useCallback((t: Toast) => { setToast(t); window.setTimeout(() => setToast((c) => (c === t ? null : c)), t.issues ? 9000 : 5000); }, []);
  const fail = useCallback((e: unknown) => {
    const d = e instanceof ApiError ? e.detail : null;
    say({ kind: "err", text: e instanceof Error ? e.message : String(e), issues: d && typeof d === "object" ? d.issues : undefined });
  }, [say]);

  const refreshList = useCallback(async () => {
    const l = await api.properties({ q: filters.q, min_area_ha: filters.min || undefined, max_area_ha: filters.max || undefined, has_analysis: filters.analyzed || undefined });
    setList(l);
    return l;
  }, [filters]);

  const loadAnalysis = useCallback(async (aid: string | null) => {
    setAnalysisId(aid); setResults(null); setContours(null);
    if (!aid) return;
    const [r, c] = await Promise.all([api.results(aid), api.contours(aid)]);
    setResults(r); setContours(c); setZone("property");
    if (r.soil && "depths" in r.soil) setDepth(r.soil.depths[0]);
  }, []);

  const selectProperty = useCallback(async (id: string) => {
    const p = await api.property(id);
    setProp(p); setMapMode("view");
    await loadAnalysis(p.analyses.find((a) => a.status === "done")?.id ?? null);
    return p;
  }, [loadAnalysis]);

  useEffect(() => { api.health().then((h) => setMode(h.mode)).catch(fail); api.sources().then(setSources).catch(fail); }, [fail]);
  useEffect(() => { refreshList().then((l) => { if (!prop && l[0]) selectProperty(l[0].id).catch(fail); }).catch(fail); }, [filters]); // eslint-disable-line react-hooks/exhaustive-deps

  const runAnalysis = async () => {
    if (!prop) return;
    try {
      const iv = interval ? Number(interval) : null;
      const { analysis_id } = await api.startAnalysis(prop.id, { contour_interval_m: iv, soil: withSoil });
      let j = await api.job(analysis_id);
      setJob(j);
      while (j.status === "queued" || j.status === "running") {
        await new Promise((r) => setTimeout(r, 300));
        j = await api.job(analysis_id); setJob(j);
      }
      if (j.status === "done") { await selectProperty(prop.id); setJob(null); say({ kind: "ok", text: "Análise concluída." }); refreshList(); }
    } catch (e) { fail(e); }
  };

  const propertyBody = (p: PropertyFull, extra?: { name: string; geometry: Geometry }) => ({
    name: p.name, description: p.description, geometry: p.geometry,
    plots: [...p.plots.map((x) => ({ name: x.name, geometry: x.geometry })), ...(extra ? [extra] : [])],
  });

  const onDrawn = (g: Geometry) => { setPendingGeom(g); };
  const confirmName = async (name: string) => {
    const g = pendingGeom!; setPendingGeom(null);
    try {
      if (mapMode === "draw-property") {
        const p = await api.createProperty({ name, geometry: g, plots: [] });
        if (p.issues?.length) say({ kind: "ok", text: "Propriedade criada com avisos.", issues: p.issues.filter((i) => i.severity !== "info") });
        await refreshList(); await selectProperty(p.id);
      } else if (prop) {
        await api.updateProperty(prop.id, propertyBody(prop, { name, geometry: g }));
        await selectProperty(prop.id); await refreshList();
      }
    } catch (e) { fail(e); }
    setMapMode("view");
  };

  const saveEdit = async () => {
    if (!prop) return;
    const fc = mapRef.current!.getDrawn();
    const byId = new Map(fc.features.map((f) => [String(f.id), f.geometry]));
    try {
      await api.updateProperty(prop.id, {
        name: prop.name, description: prop.description, geometry: (byId.get("__property") ?? prop.geometry) as Geometry,
        plots: prop.plots.map((x) => ({ name: x.name, geometry: (byId.get(`plot:${x.name}`) ?? x.geometry) as Geometry })),
      });
      await selectProperty(prop.id); await refreshList();
      say({ kind: "ok", text: "Geometria salva. Execute a análise novamente: os resultados anteriores se referem à geometria antiga." });
    } catch (e) { fail(e); }
    setMapMode("view");
  };

  const duplicateDemo = async () => {
    if (!prop) return;
    try { const p = await api.createProperty({ ...propertyBody(prop), name: `${prop.name} (cópia editável)` }); await refreshList(); await selectProperty(p.id); } catch (e) { fail(e); }
  };
  const remove = async () => {
    if (!prop || !confirm(`Excluir "${prop.name}" e suas análises?`)) return;
    try { await api.deleteProperty(prop.id); setProp(null); const l = await refreshList(); if (l[0]) await selectProperty(l[0].id); else await loadAnalysis(null); } catch (e) { fail(e); }
  };

  const layer = results?.layers.find((l) => l.id === layerId);
  const overlay = useMemo(() => (analysisId && layer ? { url: api.layerUrl(analysisId, layer.id), bounds: layer.bounds } : null), [analysisId, layer]);
  const demo = prop?.is_demo ?? false;
  const stale = results && prop && prop.analyses.find((a) => a.id === analysisId) && prop.analyses.find((a) => a.status === "done")?.id !== analysisId;

  const mapBlock = (
    <div className="mapbox">
      <MapView ref={mapRef} property={prop} mode={mapMode} onDrawn={onDrawn} overlay={overlay} opacity={opacity} contours={contours}
        showContours={showContours} showZones={showZones} basemap={basemap} selectedZone={zone === "property" ? null : zone} onZoneClick={setZone} />
      <div className="map-tools" role="toolbar" aria-label="Ferramentas de desenho">
        {mapMode === "view" && (<>
          <button onClick={() => setMapMode("draw-property")} data-testid="draw-property">✎ Desenhar propriedade</button>
          <button onClick={() => setMapMode("draw-plot")} disabled={!prop || demo} title={demo ? "A demonstração é somente leitura: duplique-a para editar" : ""}>＋ Talhão</button>
          <button onClick={() => setMapMode("edit")} disabled={!prop || demo} title={demo ? "A demonstração é somente leitura" : ""}>✥ Editar vértices</button>
          <button onClick={() => setImportOpen(true)} data-testid="open-import">⇪ Importar</button>
        </>)}
        {(mapMode === "draw-property" || mapMode === "draw-plot") && (<><span className="hint">Clique para marcar vértices; duplo clique conclui.</span><button className="ghost" onClick={() => setMapMode("view")}>Cancelar</button></>)}
        {mapMode === "edit" && (<><span className="hint">Selecione um polígono e arraste os vértices.</span><button className="primary" onClick={saveEdit}>Salvar</button><button className="ghost" onClick={() => setMapMode("view")}>Cancelar</button></>)}
      </div>
      <div className="dsm-badge" title="Copernicus DEM GLO-30 é um modelo digital de superfície (DSM), ~30 m. Não é levantamento topográfico.">DSM ~30 m · não é levantamento topográfico</div>
      {pendingGeom && <NameDialog title={mapMode === "draw-property" ? "Nome da propriedade" : "Nome do talhão"} onOk={confirmName} onCancel={() => { setPendingGeom(null); setMapMode("view"); }} />}
    </div>
  );

  return (
    <div className="app">
      <nav className="side" aria-label="Navegação">
        <div className="brand"><span className="logo">◭</span><div><strong>Terrain &amp; Soil</strong><small>Intelligence</small></div></div>
        {NAV.map((n) => (<button key={n.id} className={`nav ${view === n.id ? "on" : ""}`} onClick={() => setView(n.id)} aria-current={view === n.id ? "page" : undefined}><span aria-hidden>{n.icon}</span><span className="lbl">{n.label}</span></button>))}
        <div className="side-foot"><span className={`mode ${mode}`} data-testid="mode">{mode === "demo" ? "Modo demonstração · offline" : "Modo live"}</span></div>
      </nav>

      <main className="main">
        <header className="top">
          <label className="sel">Propriedade
            <select value={prop?.id ?? ""} onChange={(e) => selectProperty(e.target.value).catch(fail)} data-testid="prop-select">
              {list.map((p) => (<option key={p.id} value={p.id}>{p.name} · {fmt(p.area_ha, 0)} ha</option>))}
            </select>
          </label>
          <label className="sel small">Curvas (m)<input type="number" min={5} step={5} placeholder="auto" value={interval} onChange={(e) => setIntervalM(e.target.value)} aria-label="Intervalo das curvas de nível em metros" /></label>
          <label className="check"><input type="checkbox" checked={withSoil} onChange={(e) => setWithSoil(e.target.checked)} /> Solo</label>
          <button className="primary" onClick={runAnalysis} disabled={!prop || (job !== null && job.status !== "failed")} data-testid="run">▶ Executar análise</button>
          {results && analysisId && (
            <span className="exports" aria-label="Exportar">
              <a href={api.exportUrl(analysisId, "report")} download data-testid="export-pdf">PDF</a>
              <a href={api.exportUrl(analysisId, "dem")} download>DEM.tif</a>
              <a href={api.exportUrl(analysisId, "slope")} download>Declividade.tif</a>
              <a href={api.exportUrl(analysisId, "contours")} download>Curvas.geojson</a>
              <a href={api.exportUrl(analysisId, "geojson")} download>Zonas.geojson</a>
            </span>
          )}
        </header>
        <JobBar job={job} />
        {stale && <p className="flag banner">Há uma análise mais recente desta propriedade; esta é antiga.</p>}
        {toast && (<div className={`toast ${toast.kind}`} role="alert">{toast.text}{toast.issues && <Issues issues={toast.issues} />}</div>)}

        {view === "map" && (
          <div className="workspace">
            <aside className="left">
              {results ? <LayerPanel layers={results.layers} layerId={layerId} setLayerId={setLayerId} opacity={opacity} setOpacity={setOpacity}
                showContours={showContours} setShowContours={setShowContours} showZones={showZones} setShowZones={setShowZones} basemap={basemap} setBasemap={setBasemap} interval={results.params.contour_interval_m} />
                : <section className="card"><h3>Camadas</h3><label className="check"><input type="checkbox" checked={basemap} onChange={(e) => setBasemap(e.target.checked)} /> Mapa base OSM <em className="tag">online</em></label><p className="muted">Execute a análise para gerar as camadas de elevação, declividade, aspecto e solo.</p></section>}
              {demo && <section className="card note-card"><b>Demonstração.</b> Polígonos <b>ilustrativos</b> sobre dados reais (Copernicus DEM e SoilGrids). <button className="link" onClick={duplicateDemo}>Duplicar para editar</button></section>}
              {prop && !demo && <button className="danger" onClick={remove}>Excluir propriedade</button>}
            </aside>
            <section className="center">{mapBlock}</section>
            <aside className="right">
              {results ? (<><Warnings r={results} /><Indicators r={results} zone={zone} setZone={setZone} /></>) : <section className="card"><h3>Indicadores</h3><p className="muted">Nenhuma análise concluída para esta propriedade.</p></section>}
            </aside>
          </div>
        )}

        {view === "properties" && (
          <div className="page">
            <h2>Propriedades</h2>
            <div className="filters">
              <input placeholder="Buscar por nome" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} aria-label="Buscar por nome" />
              <input type="number" placeholder="Área mín (ha)" value={filters.min} onChange={(e) => setFilters({ ...filters, min: e.target.value })} aria-label="Área mínima" />
              <input type="number" placeholder="Área máx (ha)" value={filters.max} onChange={(e) => setFilters({ ...filters, max: e.target.value })} aria-label="Área máxima" />
              <label className="check"><input type="checkbox" checked={filters.analyzed} onChange={(e) => setFilters({ ...filters, analyzed: e.target.checked })} /> Só com análise</label>
              <button onClick={() => setImportOpen(true)}>⇪ Importar</button>
            </div>
            <div className="table-wrap"><table data-testid="prop-table"><thead><tr><th>Nome</th><th>Área (ha)</th><th>Talhões</th><th>Última análise</th><th>Elev. média (m)</th><th>Decliv. média (%)</th></tr></thead><tbody>
              {list.map((p) => (<tr key={p.id} className="click" onClick={() => { selectProperty(p.id).then(() => setView("map")).catch(fail); }}>
                <td>{p.name}{p.is_demo && <span className="badge">demo</span>}</td><td>{fmt(p.area_ha, 1)}</td><td>{p.n_plots}</td>
                <td>{p.last_analysis ? new Date(p.last_analysis.created_at).toLocaleString("pt-BR") : "–"}</td>
                <td>{fmt(p.last_analysis?.summary.elevation_mean_m, 0)}</td><td>{fmt(p.last_analysis?.summary.slope_mean_pct, 1)}</td></tr>))}
              {list.length === 0 && <tr><td colSpan={6} className="muted">Nenhuma propriedade com esses filtros.</td></tr>}
            </tbody></table></div>
          </div>
        )}

        {view === "compare" && (
          <div className="page"><h2>Comparar regiões da propriedade</h2>
            {results && analysisId ? (<><Compare analysisId={analysisId} r={results} /><h3>Todas as zonas</h3><ZoneTable r={results} onPick={(z) => { setZone(z); setView("map"); }} /></>) : <p className="muted">Execute uma análise primeiro.</p>}
          </div>
        )}

        {view === "soil" && (
          <div className="page"><h2>Solo estimado (SoilGrids)</h2>
            {results ? (<>
              <div className="zone-pick" role="tablist" aria-label="Zona">{Object.keys(results.zones).map((k) => (<button key={k} role="tab" aria-selected={k === zone} className={k === zone ? "on" : ""} onClick={() => setZone(k)}>{k === "property" ? "Propriedade" : k}</button>))}</div>
              <SoilPanel r={results} zone={zone} depth={depth} setDepth={setDepth} /></>) : <p className="muted">Execute uma análise primeiro.</p>}
          </div>
        )}

        {view === "sources" && <SourcesPage s={sources} />}
      </main>

      {importOpen && <ImportDialog onClose={() => setImportOpen(false)} onCreate={async (name, geometry, plots) => {
        try {
          const p = await api.createProperty({ name, geometry, plots });
          const warn = (p.issues ?? []).filter((i) => i.severity !== "info");
          say({ kind: "ok", text: `"${p.name}" criada.`, issues: warn.length ? warn : undefined });
          setImportOpen(false); await refreshList(); await selectProperty(p.id);
        } catch (e) { fail(e); }
      }} />}
    </div>
  );
}
