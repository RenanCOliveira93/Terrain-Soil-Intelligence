import json

import pytest
from shapely.geometry import box, mapping

from app.core import geometry as g


def test_utm_epsg_brasil_sirgas_e_mundo():
    assert g.utm_epsg(-46.78, -22.2) == 31983  # SIRGAS 2000 / 23S
    assert g.utm_epsg(-51.0, -22.0) == 31982
    assert g.utm_epsg(10.0, 45.0) == 32632  # WGS 84 / 32N
    assert g.utm_epsg(-100.0, -10.0) == 32714  # fora do Brasil: WGS 84 / 14S


def test_area_utm_vs_geodesica_quadrado_de_1km():
    # 0,01° × 0,01° a -22,205°: (0,01·111,32 km·cos φ) × (0,01·110,6 km) ≈ 1,031 km × 1,106 km ≈ 114 ha (cálculo independente)
    sq = box(-46.80, -22.21, -46.79, -22.20)
    m = g.metrics(g.to_multipolygon(sq))
    assert abs(m["area_diff_pct"]) < 0.05
    import math
    ref = (0.01 * 111320 * math.cos(math.radians(22.205))) * (0.01 * 110600) / 1e4
    assert m["area_ha"] == pytest.approx(ref, rel=5e-3)
    assert m["crs_projected"] == "EPSG:31983"
    assert m["perimeter_m"] == pytest.approx(m["perimeter_m_geodesic"], rel=5e-4)


def test_centroide_e_bbox():
    m = g.metrics(g.to_multipolygon(box(-46.80, -22.21, -46.79, -22.20)))
    assert m["centroid"]["lon"] == pytest.approx(-46.795, abs=1e-4)
    assert m["bbox"] == [-46.80, -22.21, -46.79, -22.20]


def test_gravata_e_reparada_com_aviso_e_recusada_sem_reparo():
    bow = json.loads(open("sample_data/invalido_gravata.geojson").read())["features"][0]["geometry"]
    v = g.validate_geometry(bow, "x", repair=True)
    assert v.ok and v.repaired and any(i.code == "GEOM_REPAIRED" for i in v.issues)
    v2 = g.validate_geometry(bow, "x", repair=False)
    assert not v2.ok and v2.issues[0].code == "GEOM_INVALID"


def test_coordenadas_utm_em_geojson_sao_detectadas():
    gj = json.loads(open("sample_data/invalido_coordenadas_utm.geojson").read())["features"][0]["geometry"]
    v = g.validate_geometry(gj)
    assert not v.ok and v.issues[0].code == "CRS_RANGE"


def test_tipo_errado_e_vazio():
    assert g.validate_geometry({"type": "Point", "coordinates": [0, 0]}).issues[0].code == "GEOM_TYPE"
    assert g.validate_geometry({"type": "Polygon", "coordinates": []}).ok is False


def test_area_limite_operacional():
    big = box(-50, -22, -48, -20)
    v = g.validate_geometry(mapping(big), max_area_ha=20000)
    assert not v.ok and any(i.code == "AREA_HUGE" for i in v.issues)


def test_z_e_ignorado_com_info():
    poly = {"type": "Polygon", "coordinates": [[[-46.8, -22.2, 800], [-46.79, -22.2, 800], [-46.79, -22.19, 800], [-46.8, -22.19, 800], [-46.8, -22.2, 800]]]}
    v = g.validate_geometry(poly)
    assert v.ok and any(i.code == "GEOM_Z" for i in v.issues)
    assert not v.geometry.has_z


def test_talhoes_sobrepostos_e_fora():
    prop = g.to_multipolygon(box(-46.80, -22.21, -46.79, -22.20))
    plots = {"A": g.to_multipolygon(box(-46.80, -22.21, -46.795, -22.205)),
             "B": g.to_multipolygon(box(-46.798, -22.208, -46.792, -22.202)),
             "C": g.to_multipolygon(box(-46.792, -22.205, -46.785, -22.199))}
    codes = {i.code for i in g.check_plots(prop, plots)}
    assert {"PLOT_OVERLAP", "PLOT_OUTSIDE", "PLOT_COVERAGE"} <= codes
    sem = g.check_plots(prop, {"A": plots["A"]})
    assert not any(i.code in ("PLOT_OVERLAP", "PLOT_OUTSIDE") for i in sem)


def test_demo_talhoes_nao_se_sobrepoem(demo_parts):
    prop, plots = demo_parts
    P = g.validate_geometry(prop).geometry
    pg = {p["name"]: g.validate_geometry(p["geometry"]).geometry for p in plots}
    codes = [i.code for i in g.check_plots(P, pg)]
    assert "PLOT_OVERLAP" not in codes and "PLOT_OUTSIDE" not in codes
