"""API REST do Terrain & Soil Intelligence (FastAPI). Documentação interativa em /docs, OpenAPI em /openapi.json."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import rasterio
import shapely
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from shapely.geometry import MultiPolygon, mapping

from . import jobs, store
from .config import ROOT, settings
from .core import analysis as an
from .core import dem as demmod
from .core import geometry as geom
from .core import io as gio
from .core import soil as soilmod

log = logging.getLogger("tsi")
VERSION = "0.1.0"


class PlotIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    geometry: dict[str, Any]


class PropertyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    geometry: dict[str, Any]
    plots: list[PlotIn] = []


class AnalysisIn(BaseModel):
    contour_interval_m: float | None = Field(None, description="Intervalo das curvas (m). Mínimo 5; padrão automático (≥10).")
    soil: bool = True


class ValidateIn(BaseModel):
    geometry: dict[str, Any]
    name: str | None = None
    repair: bool = True


def seed_demo():
    gj = json.loads((settings.sample_dir / "propriedade_demo.geojson").read_text(encoding="utf-8"))
    with store.session() as s:
        if s.query(store.Property).filter_by(is_demo="1").first():
            return
        pf = [f for f in gj["features"] if f["properties"]["kind"] == "property"][0]
        P = geom.validate_geometry(pf["geometry"]).geometry
        p = store.Property(name=pf["properties"]["name"], is_demo="1", geom=P, area_ha=geom.metrics(P)["area_ha"],
                           description="Polígonos ILUSTRATIVOS sobre dados reais do Copernicus DEM e do SoilGrids (não é uma propriedade real).")
        for f in gj["features"]:
            if f["properties"]["kind"] == "plot":
                g = geom.validate_geometry(f["geometry"]).geometry
                p.plots.append(store.Plot(name=f["properties"]["name"], geom=g, area_ha=geom.metrics(g)["area_ha"]))
        s.add(p)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    if settings.mode == "demo":
        seed_demo()
    yield


app = FastAPI(title="Terrain & Soil Intelligence API", version=VERSION, lifespan=lifespan,
              description="Análise territorial de propriedades agrícolas: relevo (Copernicus DEM GLO-30, um DSM) e solo (SoilGrids), "
                          "com incertezas e limitações explícitas.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["X-Bounds", "Content-Disposition"])


def _to_mp(geojson, name=None, repair=True):
    v = geom.validate_geometry(geojson, name, repair=repair, max_area_ha=settings.max_area_ha)
    if not v.ok:
        raise HTTPException(422, {"message": "Geometria inválida", "issues": [i.asdict() for i in v.issues]})
    return v


def _prop_out(p: store.Property, full=True) -> dict:
    d = {"id": p.id, "name": p.name, "description": p.description, "area_ha": p.area_ha, "is_demo": p.is_demo == "1",
         "created_at": p.created_at, "updated_at": p.updated_at, "n_plots": len(p.plots)}
    if full:
        d["geometry"] = mapping(p.geom)
        d["plots"] = [{"id": x.id, "name": x.name, "area_ha": x.area_ha, "geometry": mapping(x.geom)} for x in p.plots]
        d["analyses"] = [_an_out(a) for a in p.analyses]
    return d


def _an_out(a: store.Analysis) -> dict:
    return {"id": a.id, "property_id": a.property_id, "status": a.status, "progress": a.progress, "stage": a.stage,
            "params": a.params, "summary": a.summary, "error": a.error, "mode": a.mode, "created_at": a.created_at,
            "finished_at": a.finished_at}


@app.get("/api/health", tags=["sistema"])
def health():
    return {"status": "ok", "version": VERSION, "mode": settings.mode, "database": store._engine.dialect.name if store._engine else None,
            "versions": {"rasterio": rasterio.__version__, "shapely": shapely.__version__}}


@app.get("/api/sources", tags=["sistema"])
def sources():
    return {"dem": demmod.DEM_META, "soil": soilmod.SOIL_META,
            "soil_properties": {k: {kk: vv for kk, vv in v.items() if kk != "factor"} for k, v in soilmod.PROPERTIES.items()},
            "soil_depths": soilmod.DEPTHS, "limitations": an.LIMITATIONS, "mode": settings.mode,
            "contour_policy": {"min_interval_m": 5, "warn_below_m": 10}}


@app.post("/api/geometry/validate", tags=["geometria"])
def validate(body: ValidateIn):
    v = geom.validate_geometry(body.geometry, body.name, repair=body.repair, max_area_ha=settings.max_area_ha)
    return {"ok": v.ok, "repaired": v.repaired, "issues": [i.asdict() for i in v.issues],
            "metrics": geom.metrics(v.geometry) if v.geometry is not None and v.ok else None,
            "geometry": mapping(v.geometry) if v.geometry is not None else None}


@app.post("/api/import", tags=["geometria"])
async def import_file(file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Arquivo maior que {settings.max_upload_mb} MB.")
    try:
        imp = gio.read_any(file.filename or "", raw)
    except gio.ImportError_ as exc:
        raise HTTPException(422, str(exc)) from exc
    feats = []
    for f in imp.features:
        v = geom.validate_geometry(f["geometry"], f["name"], repair=True, max_area_ha=settings.max_area_ha)
        feats.append({"name": f["name"], "properties": f["properties"], "ok": v.ok, "repaired": v.repaired,
                      "issues": [i.asdict() for i in v.issues], "geometry": mapping(v.geometry) if v.geometry is not None else None,
                      "metrics": geom.metrics(v.geometry) if v.ok else None})
    return {"filename": file.filename, "source_crs": imp.source_crs, "notes": imp.notes, "features": feats}


@app.get("/api/properties", tags=["propriedades"])
def list_properties(q: str | None = None, min_area_ha: float | None = None, max_area_ha: float | None = None,
                    has_analysis: bool | None = None):
    with store.session() as s:
        out = []
        for p in s.query(store.Property).order_by(store.Property.created_at.desc()).all():
            if q and q.lower() not in p.name.lower():
                continue
            if min_area_ha is not None and (p.area_ha or 0) < min_area_ha:
                continue
            if max_area_ha is not None and (p.area_ha or 0) > max_area_ha:
                continue
            if has_analysis is not None and bool(any(a.status == "done" for a in p.analyses)) != has_analysis:
                continue
            d = _prop_out(p, full=False)
            d["bbox"] = list(p.geom.bounds)
            d["last_analysis"] = next((_an_out(a) for a in p.analyses if a.status == "done"), None)
            out.append(d)
        return out


@app.post("/api/properties", status_code=201, tags=["propriedades"])
def create_property(body: PropertyIn):
    v = _to_mp(body.geometry, body.name)
    plots = {}
    for pl in body.plots:
        if pl.name in plots:
            raise HTTPException(422, f"Nome de talhão repetido: {pl.name}")
        plots[pl.name] = _to_mp(pl.geometry, pl.name).geometry
    plot_issues = [i.asdict() for i in geom.check_plots(v.geometry, plots)] if plots else []
    with store.session() as s:
        p = store.Property(name=body.name, description=body.description, geom=v.geometry, area_ha=geom.metrics(v.geometry)["area_ha"])
        for k, g in plots.items():
            p.plots.append(store.Plot(name=k, geom=g, area_ha=geom.metrics(g)["area_ha"]))
        s.add(p)
        s.flush()
        out = _prop_out(p)
    out["issues"] = [i.asdict() for i in v.issues] + plot_issues
    return out


def _get_prop(s, pid) -> store.Property:
    p = s.get(store.Property, pid)
    if not p:
        raise HTTPException(404, "Propriedade não encontrada")
    return p


@app.get("/api/properties/{pid}", tags=["propriedades"])
def get_property(pid: str):
    with store.session() as s:
        return _prop_out(_get_prop(s, pid))


@app.put("/api/properties/{pid}", tags=["propriedades"])
def update_property(pid: str, body: PropertyIn):
    v = _to_mp(body.geometry, body.name)
    plots = {pl.name: _to_mp(pl.geometry, pl.name).geometry for pl in body.plots}
    with store.session() as s:
        p = _get_prop(s, pid)
        if p.is_demo == "1":
            raise HTTPException(403, "A propriedade de demonstração é somente leitura; duplique-a ou importe a sua.")
        p.name, p.description, p.geom, p.area_ha = body.name, body.description, v.geometry, geom.metrics(v.geometry)["area_ha"]
        p.plots.clear()
        s.flush()
        for k, g in plots.items():
            p.plots.append(store.Plot(name=k, geom=g, area_ha=geom.metrics(g)["area_ha"]))
        s.flush()
        out = _prop_out(p)
    return out


@app.delete("/api/properties/{pid}", status_code=204, tags=["propriedades"])
def delete_property(pid: str):
    with store.session() as s:
        p = _get_prop(s, pid)
        if p.is_demo == "1":
            raise HTTPException(403, "A propriedade de demonstração não pode ser excluída.")
        ids = [a.id for a in p.analyses]
        s.delete(p)
    import shutil
    for i in ids:
        shutil.rmtree(settings.analyses_dir / i, ignore_errors=True)
    return Response(status_code=204)


@app.post("/api/properties/{pid}/analyses", status_code=202, tags=["análises"])
def start_analysis(pid: str, body: AnalysisIn | None = None):
    body = body or AnalysisIn()
    if body.contour_interval_m is not None and body.contour_interval_m < 5:
        raise HTTPException(422, "Intervalo de curvas < 5 m é incoerente com o DEM GLO-30 (exatidão vertical < 4 m LE90).")
    with store.session() as s:
        p = _get_prop(s, pid)
        a = store.Analysis(property_id=p.id, params=body.model_dump(), mode=settings.mode)
        s.add(a)
        s.flush()
        aid = a.id
    jobs.submit(aid)
    return {"analysis_id": aid, "job_id": aid, "status_url": f"/api/jobs/{aid}"}


@app.get("/api/jobs/{job_id}", tags=["análises"])
def job_status(job_id: str):
    with store.session() as s:
        a = s.get(store.Analysis, job_id)
        if not a:
            raise HTTPException(404, "Job não encontrado")
        return _an_out(a)


def _done(aid) -> Path:
    with store.session() as s:
        a = s.get(store.Analysis, aid)
        if not a:
            raise HTTPException(404, "Análise não encontrada")
        if a.status != "done":
            raise HTTPException(409, f"Análise em estado '{a.status}'")
    return settings.analyses_dir / aid


@app.get("/api/analyses/{aid}", tags=["análises"])
def get_analysis(aid: str):
    return json.loads((_done(aid) / "results.json").read_text(encoding="utf-8"))


@app.get("/api/analyses/{aid}/layers/{layer_id}", tags=["análises"], response_class=Response)
def get_layer(aid: str, layer_id: str):
    d = _done(aid)
    try:
        png, bounds = an.render_layer_png(d, layer_id)
    except KeyError:
        raise HTTPException(404, "Camada inexistente")
    return Response(png, media_type="image/png", headers={"X-Bounds": json.dumps(bounds), "Cache-Control": "max-age=3600"})


@app.get("/api/analyses/{aid}/contours", tags=["análises"])
def get_contours(aid: str):
    return JSONResponse(json.loads((_done(aid) / "contours.geojson").read_text(encoding="utf-8")))


EXPORTS = {
    "dem": ("dem_clip.tif", "image/tiff", "dem_glo30_recortado.tif"),
    "slope": ("slope_deg.tif", "image/tiff", "declividade_graus.tif"),
    "aspect": ("aspect_deg.tif", "image/tiff", "aspecto_graus.tif"),
    "contours": ("contours.geojson", "application/geo+json", "curvas_de_nivel.geojson"),
    "report": ("relatorio.pdf", "application/pdf", "relatorio.pdf"),
    "results": ("results.json", "application/json", "resultados.json"),
}


@app.get("/api/analyses/{aid}/export/{kind}", tags=["exportação"])
def export(aid: str, kind: str):
    d = _done(aid)
    if kind == "geojson":
        gj = json.loads((d / "property.geojson").read_text(encoding="utf-8"))
        res = json.loads((d / "results.json").read_text(encoding="utf-8"))
        for f in gj["features"]:
            key = "property" if f["properties"]["kind"] == "property" else f["properties"]["name"]
            z = res["zones"][key]
            f["properties"].update({"elev_mean_m": z["elevation_m"]["mean"], "elev_min_m": z["elevation_m"]["min"],
                                    "elev_max_m": z["elevation_m"]["max"], "slope_mean_pct": z["slope_pct"]["mean"],
                                    "aspect_dominant": z["aspect"]["dominant"], "n_pixels": z["n_pixels"],
                                    "source": "Copernicus DEM GLO-30 (DSM); ver relatorio.pdf"})
        gj["metadata"] = {"crs": "EPSG:4326", "limitations": res["limitations"]}
        return Response(json.dumps(gj, ensure_ascii=False), media_type="application/geo+json",
                        headers={"Content-Disposition": 'attachment; filename="zonas_com_estatisticas.geojson"'})
    if kind not in EXPORTS:
        raise HTTPException(404, f"Exportação desconhecida: {kind}. Opções: geojson, {', '.join(EXPORTS)}")
    fn, mt, dl = EXPORTS[kind]
    f = d / fn
    if not f.exists():
        raise HTTPException(404, "Arquivo não gerado")
    return FileResponse(f, media_type=mt, filename=dl)


@app.get("/api/analyses/{aid}/compare", tags=["análises"])
def compare(aid: str, a: str = Query(..., description="zona A: 'property' ou nome do talhão"),
            b: str = Query(..., description="zona B")):
    res = json.loads((_done(aid) / "results.json").read_text(encoding="utf-8"))
    for k in (a, b):
        if k not in res["zones"]:
            raise HTTPException(404, f"Zona inexistente: {k}")
    za, zb = res["zones"][a], res["zones"][b]
    t = {"elevation_mean_m": [za["elevation_m"]["mean"], zb["elevation_m"]["mean"]],
         "slope_mean_pct": [za["slope_pct"]["mean"], zb["slope_pct"]["mean"]],
         "slope_p95_pct": [za["slope_pct"]["p95"], zb["slope_pct"]["p95"]],
         "aspect_dominant": [za["aspect"]["dominant"], zb["aspect"]["dominant"]]}
    terrain = {k: {"a": v[0], "b": v[1], "delta": (v[1] - v[0]) if isinstance(v[0], (int, float)) else None} for k, v in t.items()}
    soil_out, notes = [], []
    soil = res.get("soil")
    if soil and "zones" in soil:
        sa, sb = soil["zones"][a], soil["zones"][b]
        for p in soil["zones"][a]["properties"]:
            for d in soil["depths"]:
                x, y = sa["properties"][p]["depths"][d], sb["properties"][p]["depths"][d]
                if not (x.get("available") and y.get("available")):
                    continue
                overlap = max(x["q05_mean"], y["q05_mean"]) < min(x["q95_mean"], y["q95_mean"])
                same = abs(x["mean"] - y["mean"]) < 1e-6
                soil_out.append({"property": p, "depth": d, "a": x["mean"], "b": y["mean"], "delta": y["mean"] - x["mean"],
                                 "intervals_overlap": overlap, "identical_pixels": same,
                                 "reading": ("valores idênticos: mesmo pixel do SoilGrids, sem informação para comparar" if same else
                                             "diferença dentro da incerteza (intervalos de 90% se sobrepõem)" if overlap else "intervalos não se sobrepõem")})
        if any(r["identical_pixels"] for r in soil_out):
            notes.append("Zonas com valores de solo idênticos compartilham o mesmo pixel de 250 m.")
        if all(r["intervals_overlap"] for r in soil_out):
            notes.append("Todas as diferenças de solo estão dentro da incerteza do SoilGrids: não há evidência de diferença de solo entre as zonas.")
    return {"a": a, "b": b, "terrain": terrain, "soil": soil_out, "notes": notes,
            "flags": {a: za["quality_flags"], b: zb["quality_flags"]}}


@app.post("/api/demo/seed", tags=["sistema"])
def demo_seed():
    seed_demo()
    return {"ok": True}
