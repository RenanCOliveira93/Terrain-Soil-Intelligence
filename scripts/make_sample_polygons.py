"""Gera polígonos ILUSTRATIVOS (não são uma propriedade real) em GeoJSON, KML e Shapefile ZIP + arquivos inválidos."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon, box, mapping

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sample_data"

prop = Polygon([(-46.7905, -22.2075), (-46.7840, -22.2095), (-46.7770, -22.2080), (-46.7715, -22.2040), (-46.7700, -22.1985),
                (-46.7745, -22.1925), (-46.7820, -22.1915), (-46.7885, -22.1940), (-46.7915, -22.2000)])
W, S, E, N = prop.bounds
A = prop.intersection(box(W, S, -46.7840, N)).buffer(-0.0001)
B = prop.intersection(box(-46.7840, S, E, -22.2010)).buffer(-0.0001)
D = box(-46.7800, -22.1990, -46.7787, -22.1978)  # ~ 2 ha: menor que um pixel do SoilGrids
C = prop.intersection(box(-46.7840, -22.2010, E, N)).difference(D.buffer(0.0001)).buffer(-0.0001)
plots = {"Talhão A (oeste)": A, "Talhão B (sul)": B, "Talhão C (norte)": C, "Talhão D (pequeno)": D}


def fc(feats):
    return {"type": "FeatureCollection", "features": feats}


def feat(name, g, **p):
    return {"type": "Feature", "properties": {"name": name, **p}, "geometry": json.loads(json.dumps(mapping(g)))}


gj = fc([feat("Fazenda Demo (ilustrativa)", prop, kind="property")] + [feat(k, v, kind="plot") for k, v in plots.items()])
(OUT / "propriedade_demo.geojson").write_text(json.dumps(gj, ensure_ascii=False, indent=1), encoding="utf-8")

# KML
def ring(r):
    return " ".join(f"{x:.6f},{y:.6f},0" for x, y in r.coords)
pm = []
for k, g in [("Fazenda Demo (ilustrativa)", prop)] + list(plots.items()):
    for poly in ([g] if g.geom_type == "Polygon" else g.geoms):
        pm.append(f"<Placemark><name>{k}</name><Polygon><outerBoundaryIs><LinearRing><coordinates>{ring(poly.exterior)}</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>")
(OUT / "propriedade_demo.kml").write_text('<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>' + "".join(pm) + "</Document></kml>", encoding="utf-8")

# Shapefile em SIRGAS 2000 / UTM 23S (EPSG:31983) para testar a reprojeção a partir do .prj
gdf = gpd.GeoDataFrame({"nome": ["Fazenda Demo (ilustrativa)"] + list(plots), "tipo": ["property"] + ["plot"] * len(plots)},
                       geometry=[prop] + list(plots.values()), crs=4326).to_crs(31983)
with tempfile.TemporaryDirectory() as td:
    gdf.to_file(Path(td) / "propriedade_demo.shp")
    shutil.make_archive(str(OUT / "propriedade_demo_shp"), "zip", td)

# Casos inválidos (usados em testes)
bow = Polygon([(-46.79, -22.20), (-46.78, -22.19), (-46.78, -22.20), (-46.79, -22.19)])
(OUT / "invalido_gravata.geojson").write_text(json.dumps(fc([feat("gravata (auto-interseção)", bow)])), encoding="utf-8")
utm = gdf.iloc[[0]]
(OUT / "invalido_coordenadas_utm.geojson").write_text(json.dumps(fc([{"type": "Feature", "properties": {"name": "UTM em GeoJSON"},
      "geometry": json.loads(utm.geometry.to_json())["features"][0]["geometry"] if False else mapping(utm.geometry.iloc[0])}])), encoding="utf-8")
over = [feat("Propriedade", prop, kind="property"), feat("T1", box(-46.789, -22.206, -46.780, -22.197), kind="plot"),
        feat("T2", box(-46.784, -22.204, -46.775, -22.195), kind="plot")]
(OUT / "invalido_talhoes_sobrepostos.geojson").write_text(json.dumps(fc(over)), encoding="utf-8")
for k, v in plots.items():
    print(k, v.geom_type, round(gpd.GeoSeries([v], crs=4326).to_crs(31983).area.iloc[0] / 1e4, 1), "ha")
print("prop", round(gpd.GeoSeries([prop], crs=4326).to_crs(31983).area.iloc[0] / 1e4, 1), "ha")
