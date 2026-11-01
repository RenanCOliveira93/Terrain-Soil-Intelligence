"""Fluxos principais pela interface real (Chromium headless): sobe o backend (modo demo) e o frontend compilado.

Rode com:  TSI_RUN_E2E=1 pytest tests/e2e -q      (precisa de `npm run build` em frontend/ e `playwright install chromium`)
Gera os screenshots de docs/screenshots/.
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "screenshots"
pytestmark = pytest.mark.skipif(os.environ.get("TSI_RUN_E2E") != "1", reason="TSI_RUN_E2E!=1")


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _wait(url, t=40):
    import urllib.request
    end = time.time() + t
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except Exception:
            time.sleep(0.3)
    raise TimeoutError(url)


@pytest.fixture(scope="module")
def servers():
    tmp = tempfile.mkdtemp(prefix="tsi_e2e_")
    api_port, web_port = _free_port(), _free_port()
    env = {**os.environ, "TSI_MODE": "demo", "TSI_DATA_DIR": tmp, "TSI_DATABASE_URL": f"sqlite:///{tmp}/e2e.db",
           "TSI_CORS_ORIGINS": f"http://127.0.0.1:{web_port}", "VITE_API_TARGET": f"http://127.0.0.1:{api_port}"}
    be = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(api_port), "--log-level", "warning"],
                          cwd=ROOT / "backend", env=env)
    fe = subprocess.Popen([str(ROOT / "frontend/node_modules/.bin/vite"), "preview", "--port", str(web_port), "--strictPort", "--host", "127.0.0.1"],
                          cwd=ROOT / "frontend", env=env, stdout=subprocess.DEVNULL)
    try:
        _wait(f"http://127.0.0.1:{api_port}/api/health")
        _wait(f"http://127.0.0.1:{web_port}/")
        yield f"http://127.0.0.1:{web_port}", f"http://127.0.0.1:{api_port}"
    finally:
        be.terminate(); fe.terminate()
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="module")
def page(servers):
    from playwright.sync_api import sync_playwright
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 860}, accept_downloads=True, locale="pt-BR")
        pg = ctx.new_page()
        pg.errors = []
        pg.on("pageerror", lambda e: pg.errors.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and "openstreetmap" not in m.text and "Failed to load resource" not in m.text and pg.errors.append(m.text))
        pg.goto(servers[0])
        yield pg
        b.close()


def idle(page, ms=1200):
    page.wait_for_function("() => window.__tsiMap && window.__tsiMap.loaded()", timeout=20000)
    page.wait_for_timeout(ms)


def shot(page, name):
    idle(page)
    page.screenshot(path=str(SHOTS / f"{name}.png"))


def test_01_carrega_modo_demo_e_propriedade(page):
    page.wait_for_selector("[data-testid=prop-select] option", state="attached")
    assert "demonstração" in page.inner_text("[data-testid=mode]").lower()
    assert "Fazenda Demo" in page.inner_text("[data-testid=prop-select]")
    assert page.locator(".dsm-badge").is_visible()
    assert page.locator("[data-testid=draw-property]").is_visible()
    shot(page, "01_inicio_sem_analise")


def test_02_executar_analise_com_progresso(page):
    page.click("[data-testid=run]")
    page.wait_for_selector("[data-testid=indicators]", timeout=60000)
    txt = page.inner_text("[data-testid=indicators]")
    assert "332,9 ha" in txt and "Declividade média" in txt and "Aspecto dominante" in txt
    assert page.evaluate("() => !!window.__tsiMap.getLayer('overlay')")  # camada raster desenhada
    assert page.locator("[data-testid=export-pdf]").count() == 1
    shot(page, "02_declividade_e_indicadores")


def test_03_camadas_legenda_e_opacidade(page):
    for label, shot_name in [("Elevação (DSM GLO-30)", "03_elevacao"), ("Orientação de encostas", "04_aspecto")]:
        page.get_by_label(label).check()
        page.wait_for_timeout(400)
        assert page.locator(".legend").is_visible()
        shot(page, shot_name)
    page.get_by_label("Camada de solo").check()
    page.get_by_label("Atributo do solo").select_option("clay")
    assert "Argila" in page.inner_text(".legend")
    shot(page, "05_solo_argila")
    page.get_by_role("button", name="Largura do intervalo 90%").click()
    assert "largura" in page.inner_text(".legend")
    page.get_by_label("Profundidade").select_option("15-30cm")
    assert "15-30cm" in page.inner_text(".legend")
    shot(page, "06_solo_incerteza_argila")
    page.locator(".layers").get_by_label("Curvas de nível").uncheck()
    assert page.evaluate("() => window.__tsiMap.getSource('contours')._data.features.length") == 0
    page.locator(".layers").get_by_label("Curvas de nível").check()
    page.get_by_label("Declividade (classes)").check()


def test_04_talhao_pequeno_mostra_aviso(page):
    page.get_by_role("tab", name="Talhão D (pequeno)").click()
    assert "Apenas" in page.inner_text("[data-testid=indicators]")
    page.get_by_role("tab", name="Propriedade").click()


def test_05_comparar_talhoes(page):
    page.get_by_role("button", name="Comparar talhões").click()
    page.wait_for_selector("[data-testid=compare] table")
    t = page.inner_text("[data-testid=compare]")
    assert "dentro da incerteza" in t or "idênticos" in t
    page.screenshot(path=str(SHOTS / "07_comparar_talhoes.png"))


def test_06_pagina_de_solo_e_fontes(page):
    page.get_by_role("button", name="Solo", exact=True).click()
    page.wait_for_selector("[data-testid=soil-panel]")
    assert "intervalo de predição de 90%" in page.inner_text("[data-testid=soil-panel]")
    page.screenshot(path=str(SHOTS / "08_solo_incertezas.png"))
    page.get_by_role("button", name="Fontes e limites").click()
    page.wait_for_selector("[data-testid=sources]")
    t = page.inner_text("[data-testid=sources]")
    assert "DSM" in t and "EGM2008" in t and "compactação" in t
    page.screenshot(path=str(SHOTS / "09_fontes_e_limites.png"), full_page=True)


def test_07_lista_com_filtros(page):
    page.get_by_role("button", name="Propriedades").click()
    page.get_by_label("Buscar por nome").fill("zzzz")
    page.wait_for_selector("text=Nenhuma propriedade com esses filtros")
    page.get_by_label("Buscar por nome").fill("")
    page.wait_for_selector("[data-testid=prop-table] tbody tr.click")
    page.screenshot(path=str(SHOTS / "10_propriedades.png"))
    page.get_by_role("button", name="Mapa e análise").click()


def test_08_importar_kml_e_recusar_coordenadas_utm(page, servers):
    page.click("[data-testid=open-import]")
    page.set_input_files("[data-testid=file-input]", str(ROOT / "sample_data/invalido_coordenadas_utm.geojson"))
    page.wait_for_selector("text=recusada")
    assert page.locator("[data-testid=import-confirm]").is_disabled()
    page.set_input_files("[data-testid=file-input]", str(ROOT / "sample_data/propriedade_demo.kml"))
    page.wait_for_selector("text=Origem: EPSG:4326")
    page.screenshot(path=str(SHOTS / "11_importar.png"))
    page.click("[data-testid=import-confirm]")
    page.wait_for_function("() => document.querySelector('[data-testid=prop-select]').selectedOptions[0].text.includes('Fazenda Demo') && document.querySelectorAll('[data-testid=prop-select] option').length === 2")
    from playwright.sync_api import expect
    expect(page.locator("button:has-text('Editar vértices')")).to_be_enabled(timeout=10000)  # a cópia importada é editável


def test_09_desenhar_poligono_e_salvar(page):
    n0 = page.locator("[data-testid=prop-select] option").count()
    page.click("[data-testid=draw-property]")
    box = page.locator("[data-testid=map]").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    for dx, dy in [(-90, -60), (90, -60), (90, 60)]:
        page.mouse.click(cx + dx, cy + dy)
    page.mouse.dblclick(cx - 90, cy + 60)
    page.wait_for_selector("[data-testid=name-input]")
    page.fill("[data-testid=name-input]", "Área desenhada E2E")
    page.get_by_role("button", name="Salvar").click()
    page.wait_for_function(f"() => document.querySelectorAll('[data-testid=prop-select] option').length === {n0 + 1}")
    assert "Área desenhada E2E" in page.inner_text("[data-testid=prop-select]")


def test_10_analise_da_area_desenhada_e_pdf(page):
    page.click("[data-testid=run]")
    page.wait_for_selector("[data-testid=indicators]", timeout=60000)
    page.wait_for_function("() => document.querySelector('[data-testid=export-pdf]')")
    with page.expect_download() as d:
        page.click("[data-testid=export-pdf]")
    path = d.value.path()
    assert Path(path).read_bytes()[:5] == b"%PDF-"


def test_11_edicao_de_vertices_salva(page):
    page.get_by_role("button", name="Editar vértices").click()
    page.wait_for_selector("text=arraste os vértices")
    page.get_by_role("button", name="Salvar").click()
    page.wait_for_selector("text=Geometria salva")


def test_12_layout_mobile(page):
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(600)
    overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 1")
    assert not overflow
    shot(page, "12_mobile")
    page.set_viewport_size({"width": 1440, "height": 860})


def test_99_sem_erros_de_console(page):
    assert page.errors == [], page.errors
