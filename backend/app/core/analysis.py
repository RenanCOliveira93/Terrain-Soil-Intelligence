"""Orquestra a análise territorial: DEM → terreno → zonais → curvas de nível → solo → artefatos."""
from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import rasterio
from rasterio.transform import Affine
from shapely.geometry import MultiPolygon, mapping

from ..config import settings
from . import contours as contourmod
from . import dem as demmod
from . import geometry as geom
from . import render, terrain, zonal
from . import soil as soilmod

Progress = Callable[[float, str], None]
NODATA = -9999.0

LIMITATIONS = [
    "O Copernicus DEM GLO-30 é um modelo digital de SUPERFÍCIE (DSM): inclui copas, construções e infraestrutura; não é o terreno nu nem um levantamento topográfico.",
    "Célula de ~30 m: não representa microdesníveis, terraços, sulcos, estradas internas nem planeja trajetórias de máquinas ou pulverizadores.",
    "Declividade e aspecto são suavizados pela resolução; declividades locais reais podem ser maiores ou menores.",
    "Curvas de nível são interpoladas do DEM e NÃO são medidas de campo.",
    "SoilGrids tem 250 m e modelos que explicam 30–70% da variação; os intervalos de 90% são largos. Zonas pequenas herdam o valor do pixel.",
    "Nada aqui estima compactação, fertilidade real, necessidade de adubação, risco de tráfego ou de tombamento: isso exige dados de campo e validação especializada.",
]


def _to_mp(g) -> MultiPolygon:
    return g if isinstance(g, MultiPolygon) else MultiPolygon([g])


def write_geotiff(path: Path, arr, transform, window_mask=None, dtype="float32"):
    a = np.where(np.isfinite(arr), arr, NODATA).astype(dtype)
    if window_mask is not None:
        a = np.where(window_mask, a, NODATA)
    with rasterio.open(path, "w", driver="GTiff", height=a.shape[0], width=a.shape[1], count=1, dtype=dtype,
                       crs="EPSG:4326", transform=transform, compress="deflate", nodata=NODATA) as d:
        d.write(a, 1)


def crop_to_mask(mask, transform, margin=0):
    rows = np.where(mask.any(1))[0]
    cols = np.where(mask.any(0))[0]
    r0, r1 = max(rows[0] - margin, 0), min(rows[-1] + 1 + margin, mask.shape[0])
    c0, c1 = max(cols[0] - margin, 0), min(cols[-1] + 1 + margin, mask.shape[1])
    return (slice(r0, r1), slice(c0, c1)), transform * Affine.translation(c0, r0)


def bounds_of(transform, shape):
    w, n = transform.c, transform.f
    e, s = w + transform.a * shape[1], n + transform.e * shape[0]
    return [w, s, e, n]


def run_analysis(prop_geom: dict, plots: list[dict], params: dict, outdir: Path, progress: Progress | None = None,
                 mode: str | None = None, name: str = "Propriedade") -> dict:
    """prop_geom: GeoJSON EPSG:4326. plots: [{name, geometry}]. params: contour_interval_m, soil (bool)."""
    prog = progress or (lambda p, m: None)
    mode = mode or settings.mode
    outdir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    prog(0.03, "Validando geometrias")
    v = geom.validate_geometry(prop_geom, name, repair=True, max_area_ha=settings.max_area_ha)
    if not v.ok:
        raise ValueError("; ".join(i.message for i in v.issues if i.severity == "error"))
    P = v.geometry
    plot_geoms = {}
    for pl in plots:
        pv = geom.validate_geometry(pl["geometry"], pl["name"], repair=True)
        if not pv.ok:
            raise ValueError(f"Talhão '{pl['name']}': " + "; ".join(i.message for i in pv.issues if i.severity == "error"))
        plot_geoms[pl["name"]] = pv.geometry
    issues = [i.asdict() for i in v.issues]
    if plot_geoms:
        issues += [i.asdict() for i in geom.check_plots(P, plot_geoms)]
    metrics = {"property": geom.metrics(P), "plots": {k: geom.metrics(g) for k, g in plot_geoms.items()}}

    prog(0.10, "Obtendo DEM Copernicus GLO-30" + (" (amostra offline)" if mode == "demo" else " (AWS)"))
    bbox = demmod.buffered_bbox(P.bounds)
    clip = demmod.fetch_dem(bbox, mode)
    dem = clip.array
    tr = clip.transform
    prog(0.35, "Calculando declividade, aspecto e relevo sombreado")
    slope, aspect = terrain.slope_aspect(dem, tr)
    hs = terrain.hillshade(dem, tr)
    full_mask = zonal.cell_mask(P, tr, dem.shape)
    if not full_mask.any():
        full_mask = zonal.cell_mask(P, tr, dem.shape, all_touched=True)
    if np.isfinite(dem[full_mask]).mean() < 0.95:
        warnings.append("Mais de 5% das células do polígono sem dado no DEM.")

    prog(0.50, "Estatísticas zonais do terreno")
    zones = {"property": zonal.terrain_zone(P, dem, slope, aspect, tr)}
    for k, g in plot_geoms.items():
        zones[k] = zonal.terrain_zone(g, dem, slope, aspect, tr)

    prog(0.60, "Curvas de nível")
    rel = zones["property"]["elevation_m"]["range"] or 0.0
    interval = float(params.get("contour_interval_m") or contourmod.recommended_interval(rel))
    warnings += contourmod.check_interval(interval)
    cf = contourmod.contour_features(dem, tr, interval, clip=[P])
    contours = {"type": "FeatureCollection", "features": cf, "metadata": {
        "interval_m": interval, "derived_from": "Copernicus DEM GLO-30 (DSM)",
        "warning": "Curvas interpoladas de um DSM de ~30 m. Não são medidas de campo."}}
    (outdir / "contours.geojson").write_text(json.dumps(contours), encoding="utf-8")

    soil_res = None
    soil_data = None
    if params.get("soil", True):
        prog(0.68, "Obtendo atributos do SoilGrids" + (" (amostra offline)" if mode == "demo" else " (ISRIC)"))
        try:
            soil_data = soilmod.fetch_soil(P.bounds, mode)
            prog(0.85, "Estatísticas zonais do solo")
            soil_res = {"meta": soil_data["meta"], "depths": soil_data["depths"], "zones": {}}
            soil_res["zones"]["property"] = zonal.soil_zone(P, soil_data, metrics["property"]["area_ha"])
            for k, g in plot_geoms.items():
                soil_res["zones"][k] = zonal.soil_zone(g, soil_data, metrics["plots"][k]["area_ha"])
        except Exception as exc:  # solo é opcional: o erro vira aviso explícito, não silêncio
            warnings.append(f"SoilGrids indisponível: {exc}. A análise segue sem solo.")
            soil_res = {"error": str(exc)}

    prog(0.90, "Gravando rasters e camadas")
    sl, tr_c = crop_to_mask(full_mask, tr)
    cm = full_mask[sl]
    write_geotiff(outdir / "dem_clip.tif", dem[sl], tr_c, cm)
    write_geotiff(outdir / "slope_deg.tif", slope[sl], tr_c, cm)
    write_geotiff(outdir / "aspect_deg.tif", aspect[sl], tr_c, cm)
    np.savez_compressed(outdir / "layers.npz", dem=dem[sl], slope=slope[sl], aspect=aspect[sl], hs=hs[sl], mask=cm,
                        tr=np.array(tr_c)[:6])
    layer_catalog = [
        {"id": "elevation", "label": "Elevação (DSM GLO-30)", "group": "Terreno", "unit": "m, EGM2008",
         "legend": render.legend_continuous(float(np.nanmin(dem[sl][cm])), float(np.nanmax(dem[sl][cm])), "cividis", "m")},
        {"id": "hillshade", "label": "Relevo sombreado", "group": "Terreno", "unit": "", "legend": {"type": "none"}},
        {"id": "slope", "label": "Declividade (classes)", "group": "Terreno", "unit": "%", "legend": render.legend_slope()},
        {"id": "aspect", "label": "Orientação de encostas", "group": "Terreno", "unit": "", "legend": render.legend_aspect()},
    ]
    bounds = bounds_of(tr_c, cm.shape)
    if soil_data:
        sm = zonal.cell_mask(P, soil_data["transform"], next(iter(soil_data["layers"].values())).shape, all_touched=True)
        ssl, str_c = crop_to_mask(sm, soil_data["transform"])
        np.savez_compressed(outdir / "soil.npz", names=np.array(list(soil_data["layers"])),
                            data=np.stack([a[ssl] for a in soil_data["layers"].values()]),
                            mask=sm[ssl], tr=np.array(str_c)[:6])
        soil_bounds = bounds_of(str_c, sm[ssl].shape)
        for p in soil_data["props"]:
            for d in soil_data["depths"]:
                for kind in ("mean", "pi"):
                    s = render.soil_spec(p, d, kind)
                    layer_catalog.append({"id": f"soil:{p}:{d}:{kind}", "label": s["label"], "group": "Solo (SoilGrids)",
                                          "unit": s["unit"], "bounds": soil_bounds,
                                          "soil": {"prop": p, "depth": d, "kind": kind, "prop_label": soilmod.PROPERTIES[p]["label"]},
                                          "legend": render.legend_continuous(s["vmin"], s["vmax"], s["cmap"], s["unit"])})
    for L in layer_catalog:
        L.setdefault("bounds", bounds)

    res = {
        "schema": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "name": name,
        "mode": mode,
        "params": {"contour_interval_m": interval, "soil": bool(params.get("soil", True))},
        "geometry_issues": issues,
        "metrics": metrics,
        "dem": {k: clip.meta[k] for k in clip.meta if k not in ("tiles",)} | {
            "pixel_size_deg": [abs(tr.a), abs(tr.e)],
            "pixel_size_m_at_centroid": [float(terrain.cell_size_m(tr, dem.shape[0])[0].mean()), float(terrain.cell_size_m(tr, dem.shape[0])[1].mean())],
            "grid_crs": clip.crs, "shape": list(dem.shape)},
        "zones": zones,
        "contours_meta": contours["metadata"],
        "soil": soil_res,
        "layers": layer_catalog,
        "warnings": warnings,
        "limitations": LIMITATIONS,
        "software": {"python": platform.python_version(), "rasterio": rasterio.__version__},
    }
    (outdir / "results.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    (outdir / "property.geojson").write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {"name": name, "kind": "property", **{"area_ha": metrics["property"]["area_ha"]}},
                      "geometry": mapping(P)}] +
                    [{"type": "Feature", "properties": {"name": k, "kind": "plot", "area_ha": metrics["plots"][k]["area_ha"]},
                      "geometry": mapping(g)} for k, g in plot_geoms.items()]}), encoding="utf-8")
    prog(1.0, "Concluído")
    return res


def render_layer_png(outdir: Path, layer_id: str) -> tuple[bytes, list[float]]:
    res = json.loads((outdir / "results.json").read_text(encoding="utf-8"))
    cat = {l["id"]: l for l in res["layers"]}
    if layer_id not in cat:
        raise KeyError(layer_id)
    L = cat[layer_id]
    z = np.load(outdir / "layers.npz")
    if not layer_id.startswith("soil:"):
        dem, slope, aspect, hs, mask = z["dem"], z["slope"], z["aspect"], z["hs"], z["mask"]
        if layer_id == "elevation":
            lg = L["legend"]
            rgba = render.continuous(dem, mask, lg["min"], lg["max"], "cividis")
        elif layer_id == "hillshade":
            rgba = render.hillshade_rgba(hs, mask)
        elif layer_id == "slope":
            rgba = render.slope_rgba(slope, mask)
        else:
            rgba = render.aspect_rgba(aspect, mask, dem)
    else:
        _, p, d, kind = layer_id.split(":")
        sz = np.load(outdir / "soil.npz")
        names = list(sz["names"])
        data = sz["data"]
        g = lambda st: data[names.index(soilmod.layer_name(p, d, st))]  # noqa: E731
        s = render.soil_spec(p, d, kind)
        arr = g("mean") if kind == "mean" else g("q95") - g("q05")
        rgba = render.continuous(arr, sz["mask"], s["vmin"], s["vmax"], s["cmap"])
    return render._png(rgba), L["bounds"]
