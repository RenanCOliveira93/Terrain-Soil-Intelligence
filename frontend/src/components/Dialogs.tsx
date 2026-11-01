import { useState } from "react";
import { api, ApiError } from "../api";
import { fmt } from "../format";
import type { Issue, ImportResult } from "../types";

export function Issues({ issues }: { issues: Issue[] }) {
  return <ul className="issues">{issues.map((i, k) => (<li key={k} className={i.severity}>{i.severity === "error" ? "✖" : i.severity === "warning" ? "⚠" : "ℹ"} {i.message}</li>))}</ul>;
}

export function NameDialog(p: { title: string; initial?: string; onOk: (name: string) => void; onCancel: () => void }) {
  const [name, setName] = useState(p.initial ?? "");
  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label={p.title}>
      <form className="dialog" onSubmit={(e) => { e.preventDefault(); if (name.trim()) p.onOk(name.trim()); }}>
        <h3>{p.title}</h3>
        <label>Nome<input autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={200} data-testid="name-input" /></label>
        <div className="actions"><button type="button" className="ghost" onClick={p.onCancel}>Cancelar</button><button type="submit" className="primary" disabled={!name.trim()}>Salvar</button></div>
      </form>
    </div>
  );
}

export function ImportDialog(p: { onCreate: (name: string, geometry: any, plots: { name: string; geometry: any }[]) => Promise<void>; onClose: () => void }) {
  const [res, setRes] = useState<ImportResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [propIdx, setPropIdx] = useState(0);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);

  const load = async (f: File) => {
    setErr(null); setRes(null);
    try {
      const r = await api.importFile(f);
      setRes(r);
      const ok = r.features.map((x, i) => (x.ok ? i : -1)).filter((i) => i >= 0);
      const big = ok.sort((a, b) => (r.features[b].metrics?.area_ha ?? 0) - (r.features[a].metrics?.area_ha ?? 0))[0] ?? 0;
      setPropIdx(big);
      setSel(new Set(r.features.map((x, i) => (x.ok && i !== big ? i : -1)).filter((i) => i >= 0)));
    } catch (e) { setErr(e instanceof ApiError ? String(e.message) : "Falha ao importar"); }
  };
  const confirm = async () => {
    if (!res) return;
    setBusy(true);
    try {
      const pf = res.features[propIdx];
      await p.onCreate(pf.name, pf.geometry, [...sel].filter((i) => i !== propIdx).map((i) => ({ name: res.features[i].name, geometry: res.features[i].geometry })));
    } finally { setBusy(false); }
  };
  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label="Importar perímetro">
      <div className="dialog wide">
        <h3>Importar propriedade e talhões</h3>
        <p className="muted">Formatos: GeoJSON (WGS 84), KML e Shapefile em ZIP (com .prj; é reprojetado para WGS 84).</p>
        <input type="file" accept=".geojson,.json,.kml,.zip" data-testid="file-input" onChange={(e) => e.target.files?.[0] && load(e.target.files[0])} />
        {err && <p className="flag">✖ {err}</p>}
        {res && (
          <>
            <p className="note">Origem: {res.source_crs}. {res.notes.join(" ")}</p>
            <div className="table-wrap"><table><thead><tr><th>Propriedade</th><th>Talhão</th><th>Nome</th><th>Área (ha)</th><th>Validação</th></tr></thead><tbody>
              {res.features.map((f, i) => (
                <tr key={i}>
                  <td><input type="radio" name="prop" disabled={!f.ok} checked={propIdx === i} onChange={() => setPropIdx(i)} aria-label={`${f.name} é a propriedade`} /></td>
                  <td><input type="checkbox" disabled={!f.ok || i === propIdx} checked={sel.has(i) && i !== propIdx} onChange={(e) => { const s = new Set(sel); e.target.checked ? s.add(i) : s.delete(i); setSel(s); }} aria-label={`${f.name} é talhão`} /></td>
                  <td>{f.name}</td><td>{fmt(f.metrics?.area_ha, 2)}</td>
                  <td>{f.ok ? (f.repaired ? <span className="badge warn">reparada</span> : <span className="badge ok">ok</span>) : <span className="badge err">recusada</span>}{f.issues.length > 0 && <Issues issues={f.issues} />}</td>
                </tr>
              ))}</tbody></table></div>
          </>
        )}
        <div className="actions"><button className="ghost" onClick={p.onClose}>Fechar</button><button className="primary" disabled={!res || !res.features[propIdx]?.ok || busy} onClick={confirm} data-testid="import-confirm">Criar propriedade</button></div>
      </div>
    </div>
  );
}
