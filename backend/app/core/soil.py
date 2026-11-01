"""SoilGrids 2.0 (ISRIC, 250 m): pH, carbono orgânico, argila, silte, areia, com intervalo de predição de 90%.

Lemos os VRT/COG de files.isric.org (CC BY 4.0). A API REST do ISRIC estava fora do ar (503) na verificação,
e o COG dá os mesmos dados, por pixel. A camada `uncertainty` NÃO é usada: empiricamente ela é ≈ 10 × (Q0.95 − Q0.05)/Q0.50 (notebook 03),
mas a documentação oficial estava indisponível para confirmar; a incerteza vem direto dos quantis Q0.05 e Q0.95.
"""
from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine, from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

from ..config import settings

# fator: valor mapeado / fator = unidade convencional. Verificado empiricamente (areia+silte+argila ≈ 1000 g/kg;
# pH ≈ 5,3; carbono 29,9 g/kg na área de teste) e em fonte secundária (soilDB); a tabela oficial do ISRIC
# (docs.isric.org) estava indisponível (HTTP 502) na verificação.
PROPERTIES = {
    "phh2o": {"label": "pH (H2O)", "factor": 10.0, "unit": "pH", "mapped_unit": "pH×10"},
    "soc": {"label": "Carbono orgânico do solo", "factor": 10.0, "unit": "g/kg", "mapped_unit": "dg/kg"},
    "clay": {"label": "Argila", "factor": 10.0, "unit": "%", "mapped_unit": "g/kg"},
    "silt": {"label": "Silte", "factor": 10.0, "unit": "%", "mapped_unit": "g/kg"},
    "sand": {"label": "Areia", "factor": 10.0, "unit": "%", "mapped_unit": "g/kg"},
}
DEPTHS = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm", "100-200cm"]
STATS = {"mean": "mean", "q05": "Q0.05", "q50": "Q0.5", "q95": "Q0.95"}
GRID_RES = 0.0025  # ~ 250 m; reamostragem por vizinho mais próximo (não altera valores)

SOIL_META = {
    "product": "SoilGrids 2.0 (ISRIC – World Soil Information)",
    "resolution": "250 m (projeção Interrupted Goode Homolosine; reamostrado p/ EPSG:4326 por vizinho mais próximo)",
    "method": "Quantile Random Forest sobre perfis WoSIS + covariáveis ambientais",
    "uncertainty": "Intervalo de predição de 90% por pixel (Q0.05–Q0.95); NÃO é intervalo de confiança da média da área",
    "license": "CC BY 4.0",
    "citation": "Poggio et al. (2021), SoilGrids 2.0, revista SOIL, v. 7, p. 217–240 (referência de memória; título e volume não reconfirmados nesta sessão — conferir antes de citar).",
    "reference_period": "Perfis de solo e covariáveis até ~2020 (snapshot de março de 2020, conforme metadados do VRT)",
    "depth_note": "Profundidades padrão GlobalSoilMap em cm a partir da superfície",
}


def layer_name(prop: str, depth: str, stat: str) -> str:
    return f"{prop}|{depth}|{stat}"


def grid_for_bbox(bbox, res: float = GRID_RES):
    minx = np.floor(bbox[0] / res) * res
    maxy = np.ceil(bbox[3] / res) * res
    w = int(np.ceil((bbox[2] - minx) / res))
    h = int(np.ceil((maxy - bbox[1]) / res))
    return from_origin(minx, maxy, res, res), h, w


def _read_layer(prop, depth, stat, transform, h, w) -> np.ndarray:
    url = f"/vsicurl/{settings.soilgrids_base_url}/{prop}/{prop}_{depth}_{STATS[stat]}.vrt"
    with rasterio.open(url) as src:
        nd = src.nodata  # int16: -32768; (uint16 nas camadas de incerteza: 65535) — sempre do próprio arquivo
        with WarpedVRT(src, crs="EPSG:4326", transform=transform, width=w, height=h,
                       resampling=Resampling.nearest, nodata=nd) as vrt:
            a = vrt.read(1).astype("float32")
    a[a == nd] = np.nan
    return a / PROPERTIES[prop]["factor"]


def fetch_live(bbox, props=None, depths=None) -> dict:
    props = props or list(PROPERTIES)
    depths = depths or DEPTHS[:3]
    tr, h, w = grid_for_bbox(bbox)
    jobs = [(p, d, s) for p in props for d in depths for s in STATS]
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda j: _read_layer(*j, tr, h, w), jobs))
    layers = {layer_name(*j): a for j, a in zip(jobs, res)}
    return {"layers": layers, "transform": tr, "crs": "EPSG:4326", "props": props, "depths": depths,
            "meta": {**SOIL_META, "mode": "live", "source": settings.soilgrids_base_url}}


def fetch_demo(bbox) -> dict:
    path = settings.sample_dir / "demo_soilgrids.tif"
    with rasterio.open(path) as src:
        b = src.bounds
        if bbox[0] < b.left or bbox[2] > b.right or bbox[1] < b.bottom or bbox[3] > b.top:
            raise ValueError("Modo demonstração: polígono fora do recorte de amostra do SoilGrids.")
        data = src.read()
        desc = list(src.descriptions)
        tr = src.transform
    layers = {d: data[i] for i, d in enumerate(desc)}
    layers = {k: np.where(np.isfinite(v), v, np.nan).astype("float32") for k, v in layers.items()}
    props = sorted({k.split("|")[0] for k in layers}, key=list(PROPERTIES).index)
    depths = sorted({k.split("|")[1] for k in layers}, key=DEPTHS.index)
    return {"layers": layers, "transform": tr, "crs": "EPSG:4326", "props": props, "depths": depths,
            "meta": {**SOIL_META, "mode": "demo", "source": "sample_data/demo_soilgrids.tif (recorte real do SoilGrids 2.0)"}}


def fetch_soil(bbox, mode=None, props=None, depths=None) -> dict:
    mode = mode or settings.mode
    return fetch_demo(bbox) if mode == "demo" else fetch_live(bbox, props, depths)


def texture_class(clay: float, silt: float, sand: float) -> str | None:
    """Classe textural USDA (triângulo de 12 classes) a partir de % de argila, silte e areia."""
    if not all(np.isfinite([clay, silt, sand])):
        return None
    tot = clay + silt + sand
    if tot <= 0:
        return None
    clay, silt, sand = (100 * clay / tot, 100 * silt / tot, 100 * sand / tot)
    if silt + 1.5 * clay < 15:
        return "Areia"
    if silt + 1.5 * clay >= 15 and silt + 2 * clay < 30:
        return "Areia franca"
    if (7 <= clay < 20 and sand > 52 and silt + 2 * clay >= 30) or (clay < 7 and silt < 50 and silt + 2 * clay >= 30):
        return "Franco arenoso"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52:
        return "Franco"
    if (silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12):
        return "Franco siltoso"
    if silt >= 80 and clay < 12:
        return "Silte"
    if 20 <= clay < 35 and silt < 28 and sand > 45:
        return "Franco argilo-arenoso"
    if 27 <= clay < 40 and 20 < sand <= 45:
        return "Franco argiloso"
    if 27 <= clay < 40 and sand <= 20:
        return "Franco argilo-siltoso"
    if clay >= 35 and sand > 45:
        return "Argila arenosa"
    if clay >= 40 and silt >= 40:
        return "Argila siltosa"
    if clay >= 40:
        return "Argila"
    return "Franco"
