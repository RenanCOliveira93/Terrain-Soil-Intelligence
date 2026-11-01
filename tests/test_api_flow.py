import io
import json
import time

import pytest
import rasterio
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def wait(c, url, timeout=60):
    t = time.time()
    while time.time() - t < timeout:
        j = c.get(url).json()
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(0.1)
    raise TimeoutError


@pytest.fixture(scope="module")
def analysis(client):
    pid = client.get("/api/properties").json()[0]["id"]
    r = client.post(f"/api/properties/{pid}/analyses", json={"contour_interval_m": 20})
    assert r.status_code == 202
    j = wait(client, r.json()["status_url"])
    assert j["status"] == "done", j
    return pid, r.json()["analysis_id"]


def test_health_e_fontes(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["mode"] == "demo"
    s = client.get("/api/sources").json()
    assert s["dem"]["model_type"] == "DSM" and "uncertainty" in s["soil"] and len(s["limitations"]) >= 5


def test_demo_property_semeada_e_somente_leitura(client):
    props = client.get("/api/properties").json()
    assert len(props) == 1 and props[0]["is_demo"] and 330 < props[0]["area_ha"] < 335
    full = client.get(f"/api/properties/{props[0]['id']}").json()
    assert len(full["plots"]) == 4
    assert client.delete(f"/api/properties/{props[0]['id']}").status_code == 403
    body = {"name": "x", "geometry": full["geometry"]}
    assert client.put(f"/api/properties/{props[0]['id']}", json=body).status_code == 403


def test_job_com_progresso_monotono_e_resultado(client):
    pid = client.get("/api/properties").json()[0]["id"]
    r = client.post(f"/api/properties/{pid}/analyses").json()
    seen = []
    t = time.time()
    while time.time() - t < 60:
        j = client.get(r["status_url"]).json()
        seen.append(j["progress"])
        if j["status"] == "done":
            break
        time.sleep(0.02)
    assert seen == sorted(seen) and seen[-1] == 1.0 and j["summary"]["area_ha"] > 300


def test_resultados_cientificamente_completos(client, analysis):
    _, aid = analysis
    r = client.get(f"/api/analyses/{aid}").json()
    d = r["dem"]
    assert d["model_type"] == "DSM" and "EGM2008" in d["vertical_datum"] and d["horizontal_crs"].startswith("EPSG:4326")
    assert d["nominal_resolution"] and d["acquisition_period"] and d["vertical_accuracy_spec"]
    z = r["zones"]["property"]
    assert 790 < z["elevation_m"]["min"] < z["elevation_m"]["max"] < 880
    assert 5 < z["slope_pct"]["mean"] < 20
    assert r["params"]["contour_interval_m"] == 20 and r["contours_meta"]["warning"].startswith("Curvas interpoladas")
    assert any("Nada aqui estima compactação" in l for l in r["limitations"])
    cl = r["soil"]["zones"]["property"]["properties"]["clay"]["depths"]["0-5cm"]
    assert cl["q05_mean"] < cl["mean"] < cl["q95_mean"] and "NÃO é IC" in cl["pi90_note"]
    # nunca produz indicadores agronômicos que o projeto se recusa a estimar
    txt = json.dumps(r).lower()
    for banned in ("recomendação de adubação", "risco de tombamento:", "compactação:"):
        assert banned not in txt.replace("nada aqui estima compactação", "")


def test_talhao_pequeno_tem_avisos_e_zonas_vizinhas_valores_iguais(client, analysis):
    _, aid = analysis
    r = client.get(f"/api/analyses/{aid}").json()
    assert r["zones"]["Talhão D (pequeno)"]["quality_flags"]
    assert r["soil"]["zones"]["Talhão D (pequeno)"]["quality_flags"]
    c = client.get(f"/api/analyses/{aid}/compare", params={"a": "Talhão A (oeste)", "b": "Talhão B (sul)"}).json()
    assert c["terrain"]["elevation_mean_m"]["delta"] == pytest.approx(r["zones"]["Talhão B (sul)"]["elevation_m"]["mean"] - r["zones"]["Talhão A (oeste)"]["elevation_m"]["mean"])
    assert any("dentro da incerteza" in x["reading"] or "idênticos" in x["reading"] for x in c["soil"])
    assert client.get(f"/api/analyses/{aid}/compare", params={"a": "zzz", "b": "property"}).status_code == 404


def test_exportacoes(client, analysis):
    _, aid = analysis
    for k, mt in [("dem", "image/tiff"), ("slope", "image/tiff"), ("aspect", "image/tiff")]:
        x = client.get(f"/api/analyses/{aid}/export/{k}")
        assert x.status_code == 200 and mt in x.headers["content-type"]
        with rasterio.MemoryFile(x.content) as mf, mf.open() as ds:
            assert ds.crs.to_epsg() == 4326 and ds.nodata == -9999.0
            a = ds.read(1)
            assert (a == -9999).any() and (a != -9999).any()  # recortado ao polígono: fora = nodata
            if k == "dem":
                v = a[a != -9999]
                assert 790 < v.min() and v.max() < 880
    gj = client.get(f"/api/analyses/{aid}/export/geojson").json()
    assert len(gj["features"]) == 5 and "elev_mean_m" in gj["features"][0]["properties"] and gj["metadata"]["limitations"]
    ct = client.get(f"/api/analyses/{aid}/export/contours").json()
    assert ct["type"] == "FeatureCollection" and ct["features"] and ct["metadata"]["interval_m"] == 20
    assert all(f["properties"]["elevation_m"] % 20 == 0 for f in ct["features"])
    pdf = client.get(f"/api/analyses/{aid}/export/report")
    assert pdf.content[:5] == b"%PDF-" and len(pdf.content) > 50_000
    assert client.get(f"/api/analyses/{aid}/export/xyz").status_code == 404


def test_pdf_contem_ressalvas_e_fontes(analysis, client):
    import pymupdf
    _, aid = analysis
    doc = pymupdf.open(stream=client.get(f"/api/analyses/{aid}/export/report").content, filetype="pdf")
    txt = " ".join(p.get_text() for p in doc)
    for must in ("DSM", "EGM2008", "SoilGrids", "CC BY 4.0", "Limitações", "Metodologia", "interpoladas", "não é intervalo de confiança", "Copernicus"):
        assert must.lower() in txt.lower(), must


def test_camadas_png(client, analysis):
    _, aid = analysis
    for lid in ("elevation", "slope", "aspect", "hillshade", "soil:clay:0-5cm:mean", "soil:phh2o:5-15cm:pi"):
        x = client.get(f"/api/analyses/{aid}/layers/{lid}")
        assert x.status_code == 200 and x.content[:4] == b"\x89PNG" and len(json.loads(x.headers["x-bounds"])) == 4
    assert client.get(f"/api/analyses/{aid}/layers/nada").status_code == 404


def test_intervalo_de_curvas_incoerente_e_recusado(client):
    pid = client.get("/api/properties").json()[0]["id"]
    assert client.post(f"/api/properties/{pid}/analyses", json={"contour_interval_m": 2}).status_code == 422


def test_crud_importacao_e_validacao(client, demo_geojson):
    files = {"file": ("p.geojson", open("sample_data/propriedade_demo.geojson", "rb"), "application/json")}
    imp = client.post("/api/import", files=files).json()
    assert len(imp["features"]) == 5 and all(f["ok"] for f in imp["features"])
    prop = imp["features"][0]
    body = {"name": "Minha área", "geometry": prop["geometry"], "plots": [{"name": f["name"], "geometry": f["geometry"]} for f in imp["features"][1:3]]}
    c = client.post("/api/properties", json=body)
    assert c.status_code == 201
    pid = c.json()["id"]
    assert client.get("/api/properties", params={"q": "minha"}).json()[0]["id"] == pid
    assert client.get("/api/properties", params={"min_area_ha": 1e6}).json() == []
    up = client.put(f"/api/properties/{pid}", json={**body, "name": "Renomeada", "plots": body["plots"][:1]}).json()
    assert up["name"] == "Renomeada" and len(up["plots"]) == 1
    assert client.delete(f"/api/properties/{pid}").status_code == 204
    assert client.get(f"/api/properties/{pid}").status_code == 404


def test_importacao_com_erros_amigaveis(client):
    r = client.post("/api/import", files={"file": ("a.txt", b"x", "text/plain")})
    assert r.status_code == 422 and "não suportado" in r.json()["detail"]
    r = client.post("/api/import", files={"file": ("a.geojson", open("sample_data/invalido_coordenadas_utm.geojson", "rb"), "application/json")})
    f = r.json()["features"][0]
    assert not f["ok"] and f["issues"][0]["code"] == "CRS_RANGE"
    r = client.post("/api/import", files={"file": ("g.geojson", open("sample_data/invalido_gravata.geojson", "rb"), "application/json")}).json()
    assert r["features"][0]["repaired"] and any(i["code"] == "GEOM_REPAIRED" for i in r["features"][0]["issues"])


def test_validate_endpoint_e_poligono_invalido_na_criacao(client):
    bow = json.load(open("sample_data/invalido_gravata.geojson"))["features"][0]["geometry"]
    v = client.post("/api/geometry/validate", json={"geometry": bow, "repair": False}).json()
    assert not v["ok"] and v["issues"][0]["code"] == "GEOM_INVALID"
    r = client.post("/api/properties", json={"name": "ruim", "geometry": {"type": "Point", "coordinates": [0, 0]}})
    assert r.status_code == 422 and r.json()["detail"]["issues"][0]["code"] == "GEOM_TYPE"


def test_area_fora_da_amostra_falha_com_mensagem(client):
    poly = {"type": "Polygon", "coordinates": [[[-40.0, -10.0], [-39.99, -10.0], [-39.99, -9.99], [-40.0, -9.99], [-40.0, -10.0]]]}
    pid = client.post("/api/properties", json={"name": "longe", "geometry": poly}).json()["id"]
    r = client.post(f"/api/properties/{pid}/analyses").json()
    j = wait(client, r["status_url"])
    assert j["status"] == "failed" and "fora do recorte" in j["error"]
    assert client.get(f"/api/analyses/{r['analysis_id']}").status_code == 409
    client.delete(f"/api/properties/{pid}")
