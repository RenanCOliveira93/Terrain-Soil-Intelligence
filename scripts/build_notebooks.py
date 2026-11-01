"""Gera e executa os notebooks de validação (notebooks/*.ipynb).  Uso: python scripts/build_notebooks.py [--no-run]"""
import sys
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks"
SETUP = '''import os, sys, json, warnings
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
os.environ.setdefault("TSI_MODE", "demo")
sys.path.insert(0, str(ROOT / "backend"))
warnings.filterwarnings("ignore")
import numpy as np, rasterio, matplotlib
matplotlib.use("module://matplotlib_inline.backend_inline")
import matplotlib.pyplot as plt
from rasterio.transform import from_origin
from app.core import terrain, dem as demmod, soil as soilmod, zonal, geometry as geom, contours
plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": .25})
with rasterio.open(ROOT / "sample_data/demo_dem_glo30.tif") as s:
    DEM, TR = s.read(1), s.transform
'''

NB1 = [
("md", "# 01 · Validação do cálculo de terreno\n\nO objetivo é **medir o erro** do nosso gradiente de Horn contra superfícies cuja declividade é conhecida, e mostrar como a resolução e o ruído vertical do DEM alteram as estatísticas. Nada aqui valida o DEM contra o terreno real: isso exige levantamento de campo.\n\n**Perguntas:** (1) o código acerta declividade e aspecto em superfícies analíticas? (2) quanto a resolução de ~30 m subestima a declividade? (3) quanto o erro vertical especificado (< 4 m) infla ou desloca os resultados?"),
("code", SETUP),
("md", "## 1. Planos inclinados: erro de declividade e de aspecto\n\nConstruímos planos com gradiente exato (em m/m) em uma grade geográfica de 1\" a 22,2°S. O aspecto esperado é o azimute da **descida**."),
("code", '''def plane(sx, sy, n=40, lat0=-22.2, lon0=-46.8, res=1/3600):
    tr = from_origin(lon0, lat0 + n*res/2, res, res)
    dx, dy = terrain.cell_size_m(tr, n)
    j, i = np.arange(n)[None, :], np.arange(n)[:, None]
    return (500 + sx*j*dx[:, None] - sy*i*dy.mean()).astype("float32"), tr

rows = []
for pct in (1, 5, 10, 30, 60, 100):
    for az in range(0, 360, 45):
        sx = -np.sin(np.radians(az)) * pct/100   # subir para o lado oposto à descida
        sy = -np.cos(np.radians(az)) * pct/100
        z, tr = plane(sx, sy)
        sl, a = terrain.slope_aspect(z, tr)
        core = (slice(3, -3), slice(3, -3))
        pct_est = float(np.nanmean(terrain.slope_pct(sl[core])))
        da = float(np.nanmax(np.abs(((a[core] - az + 180) % 360) - 180))) if pct > 1 else np.nan
        rows.append((pct, az, pct_est, abs(pct_est - pct)/pct*100, da))
import pandas as pd
df = pd.DataFrame(rows, columns=["declividade_real_%", "aspecto_real", "declividade_est_%", "erro_rel_%", "erro_aspecto_graus"])
print(df.groupby("declividade_real_%")[["erro_rel_%", "erro_aspecto_graus"]].max().round(3))
print("\\nErro relativo máximo de declividade:", round(df["erro_rel_%"].max(), 3), "% · erro máximo de aspecto:", round(df["erro_aspecto_graus"].max(), 3), "°")'''),
("md", "**Leitura.** Em planos exatos o erro relativo máximo de declividade é de ~0,002% e o de aspecto, de ~0,005° (resíduo da pequena variação de dx/dy com a latitude dentro da grade). O cálculo está correto como *aritmética*. Isso não diz nada sobre quanto o DEM representa o terreno."),
("md", "## 2. Superfície curva (paraboloide): viés do kernel 3×3\n\nPara z = k·r², a declividade exata a distância r do vértice é arctan(2kr). Testamos se a diferença finita de Horn tem viés em superfícies curvas."),
("code", '''n = 81; res = 1/3600; lat0 = -22.2
tr = from_origin(-46.8, lat0 + n*res/2, res, res)
dx, dy = terrain.cell_size_m(tr, n)
X = (np.arange(n)[None, :] - n//2) * dx.mean(); Y = (np.arange(n)[:, None] - n//2) * dy.mean()
R = np.hypot(X, Y)
fig, ax = plt.subplots(figsize=(6.2, 3.6))
for k in (1e-4, 5e-4, 2e-3):
    z = (k * R**2).astype("float32")
    sl, _ = terrain.slope_aspect(z, tr)
    exact = np.degrees(np.arctan(2*k*R))
    err = (sl - exact)
    m = np.isfinite(err)
    ax.scatter(R[m], err[m], s=3, label=f"k={k:g} (declividade máx. {np.nanmax(terrain.slope_pct(sl)):.0f}%)")
    print(f"k={k:g}: erro médio {np.nanmean(err):+.4f}° · máx |erro| {np.nanmax(np.abs(err)):.4f}°")
ax.set_xlabel("distância ao vértice (m)"); ax.set_ylabel("erro de declividade (graus)"); ax.legend(fontsize=7); plt.show()'''),
("md", "**Leitura.** Nos três casos o erro máximo é < 0,001°: para uma superfície quadrática o kernel de Horn praticamente não tem viés. Isso vale para a *aritmética* sobre uma superfície suave; o DEM real tem feições abaixo de 30 m que o kernel não vê."),
("md", "## 3. Resolução: quanto a declividade 'some' ao agregar o DEM\n\nAgregamos o DEM real (média em blocos) de 30 m para 60, 90, 150 e 300 m e recalculamos. Isso mostra, com dados reais, por que **declividade de 30 m subestima a declividade local** e por que números de declividade de DEMs de resoluções diferentes não são comparáveis."),
("code", '''def aggregate(z, f):
    h, w = (z.shape[0]//f)*f, (z.shape[1]//f)*f
    return np.nanmean(z[:h, :w].reshape(h//f, f, w//f, f), axis=(1, 3))
res_rows = []
for f in (1, 2, 3, 5, 10):
    zz = aggregate(DEM, f) if f > 1 else DEM
    tr_f = from_origin(TR.c, TR.f, abs(TR.a)*f, abs(TR.e)*f)
    sl, _ = terrain.slope_aspect(zz.astype("float32"), tr_f)
    p = terrain.slope_pct(sl[np.isfinite(sl)])
    res_rows.append((f"{30*f} m", p.mean(), np.percentile(p, 95), (p >= 20).mean()*100))
r = pd.DataFrame(res_rows, columns=["resolução", "declividade média (%)", "P95 (%)", "% da área ≥ 20% (forte ondulado+)"]).round(2)
print(r.to_string(index=False))
fig, ax = plt.subplots(1, 2, figsize=(9, 3))
ax[0].plot(r["resolução"], r["declividade média (%)"], "o-"); ax[0].set_ylabel("média (%)"); ax[0].set_xlabel("resolução")
ax[1].plot(r["resolução"], r["% da área ≥ 20% (forte ondulado+)"], "o-", color="C3"); ax[1].set_ylabel("% ≥ 20%"); ax[1].set_xlabel("resolução")
plt.tight_layout(); plt.show()'''),
("md", "## 4. Ruído vertical: efeito do erro do DEM sobre a declividade\n\nA especificação do Copernicus DEM dá exatidão vertical absoluta < 4 m (LE90). O erro **relativo** entre pixels vizinhos é o que importa para declividade e ele é, em geral, menor, mas não o conhecemos para esta área. Simulamos ruído aleatório (independente por pixel, hipótese simples) de σ = 0,5, 1, 2 e 4 m **só para dimensionar a sensibilidade**, não para estimar o erro real."),
("code", '''rng = np.random.default_rng(42)
base_sl, _ = terrain.slope_aspect(DEM, TR)
b = terrain.slope_pct(base_sl[np.isfinite(base_sl)])
out = [("0 (original)", b.mean(), np.percentile(b, 95), (b < 3).mean()*100)]
for sig in (0.5, 1, 2, 4):
    z = (DEM + rng.normal(0, sig, DEM.shape)).astype("float32")
    sl, _ = terrain.slope_aspect(z, TR)
    p = terrain.slope_pct(sl[np.isfinite(sl)])
    out.append((f"σ = {sig} m", p.mean(), np.percentile(p, 95), (p < 3).mean()*100))
nr = pd.DataFrame(out, columns=["ruído", "declividade média (%)", "P95 (%)", "% 'plano' (<3%)"]).round(2)
print(nr.to_string(index=False))'''),
("md", "**Leitura.** Ruído independente por pixel *infla* a declividade (média e P95) de forma modesta: de 14,16% para 14,62% com σ = 2 m e 15,97% com σ = 4 m. A fatia 'plano' (< 3%) quase não muda (3,01% → 2,82%). O kernel 3×3 já faz alguma suavização. Este teste assume ruído independente por pixel; o erro real do DEM é espacialmente correlacionado e não o conhecemos para esta área, então o resultado dimensiona a sensibilidade e não prova que a declividade é confiável. Por isso o relatório não trata a declividade de 30 m como medida precisa e não usa limiares operacionais."),
("md", "## 5. Curvas de nível: incerteza horizontal implícita no intervalo\n\nUma curva de cota *h* tem posição incerta de ≈ σᵥ / tan(β) na horizontal, onde β é a declividade. Com σᵥ de 4 m e 12% (mediana da área), a incerteza horizontal é de dezenas de metros, comparável ao pixel. Isso justifica o piso de 5 m e o padrão de 10 m."),
("code", '''sl_pct = terrain.slope_pct(base_sl[np.isfinite(base_sl)])
for sv in (1, 2, 4):
    q = np.percentile(sl_pct, [10, 50, 90])
    print(f"σv = {sv} m → incerteza horizontal da curva: P10 {sv/(q[0]/100):.0f} m · mediana {sv/(q[1]/100):.0f} m · P90 {sv/(q[2]/100):.0f} m (declividades P10/P50/P90 = {q.round(1)}%)")
rel = float(np.nanmax(DEM) - np.nanmin(DEM))
print("\\nRelevo do recorte:", round(rel), "m → intervalo recomendado:", contours.recommended_interval(rel), "m")
print("Intervalo de 2 m →", end=" ")
try: contours.check_interval(2)
except ValueError as e: print("recusado:", str(e)[:90], "…")'''),
("md", "## Conclusões\n\n1. O gradiente de Horn com dx/dy por latitude **reproduz** declividade e aspecto de planos exatos com erro desprezível, e tem viés pequeno e conhecido em superfícies curvas.\n2. A **resolução** domina: agregar de 30 m para 150 m reduz a declividade média de 14,2% para 8,7% e a área ≥ 20% de 18,4% para 4,2%; os valores não são comparáveis entre resoluções.\n3. O **ruído vertical** infla a declividade de forma modesta nesta área (+13% na média com σ = 4 m, +3% com σ = 2 m); a classe 'plano' praticamente não muda. O efeito mais relevante do erro vertical é na **posição das curvas de nível** (seção 5).\n4. Com σᵥ = 4 m, a posição horizontal de uma curva é incerta em ~32 m na declividade mediana (≈ 1 pixel) e em ~72 m nas áreas mais suaves; por isso o padrão é ≥ 10 m e intervalos < 5 m são recusados.\n\n**Não validado aqui:** exatidão do DEM contra o terreno real (precisa de pontos GNSS/levantamento)."),
]

NB2 = [
("md", "# 02 · Validação do DEM real (Copernicus GLO-30)\n\nVerificamos o recorte versionado em `sample_data/`, a consistência geométrica (tamanho de célula, área por pixels × área do polígono) e, **se houver rede**, se o recorte é idêntico ao tile ao vivo da AWS."),
("code", SETUP),
("md", "## 1. Metadados e estatísticas do recorte"),
("code", '''with rasterio.open(ROOT / "sample_data/demo_dem_glo30.tif") as s:
    print("CRS:", s.crs, "| shape:", s.shape, "| dtype:", s.dtypes[0], "| nodata:", s.nodata)
    print("bounds:", tuple(round(v, 5) for v in s.bounds))
    print("tags:", {k: v[:70] for k, v in s.tags().items()})
print("\\nNaN:", int(np.isnan(DEM).sum()), "· min/média/máx (m):", np.nanmin(DEM).round(1), np.nanmean(DEM).round(1), np.nanmax(DEM).round(1))
dx, dy = terrain.cell_size_m(TR, DEM.shape[0])
print(f"célula: {dx.mean():.2f} m (E–O) × {dy.mean():.2f} m (N–S) a {TR.f + TR.e*DEM.shape[0]/2:.2f}°")
plt.figure(figsize=(5.5, 3)); plt.hist(DEM.ravel(), 60, color="#2e7d32"); plt.xlabel("altura ortométrica, EGM2008 (m)"); plt.ylabel("pixels"); plt.show()'''),
("md", "**Observação sobre o datum:** as alturas são **ortométricas (EGM2008)**, isto é, referidas ao geoide, não ao elipsoide WGS 84. Comparar com altitudes GNSS elipsoidais exige subtrair a ondulação geoidal (N), da ordem de metros no Sudeste do Brasil (valor não calculado aqui)."),
("md", "## 2. Consistência: pixels × área do polígono"),
("code", '''gj = json.loads((ROOT / "sample_data/propriedade_demo.geojson").read_text())
prop = [f for f in gj["features"] if f["properties"]["kind"] == "property"][0]["geometry"]
P = geom.validate_geometry(prop).geometry
m = geom.metrics(P)
sl, asp = terrain.slope_aspect(DEM, TR)
mask = zonal.cell_mask(P, TR, DEM.shape)
cell_ha = (dx.mean()*dy.mean())/1e4
print(f"polígono: {m['area_ha']:.2f} ha (UTM) · {m['area_ha_geodesic']:.2f} ha (geodésica)")
print(f"pixels no polígono: {int(mask.sum())} × {cell_ha:.4f} ha = {mask.sum()*cell_ha:.2f} ha → razão {mask.sum()*cell_ha/m['area_ha']:.4f}")
print("Quanto menor o polígono, maior o erro de borda: talhão D (1,8 ha):")
D = [f for f in gj["features"] if f["properties"]["name"].startswith("Talhão D")][0]["geometry"]
Dg = geom.validate_geometry(D).geometry; dm = geom.metrics(Dg); mk = zonal.cell_mask(Dg, TR, DEM.shape)
print(f"  {dm['area_ha']:.2f} ha vs {mk.sum()} pixels × {cell_ha:.4f} = {mk.sum()*cell_ha:.2f} ha (razão {mk.sum()*cell_ha/dm['area_ha']:.2f})")'''),
("md", "## 3. Consistência de aspecto × sombreamento\n\nO relevo sombreado com sol a NO (azimute 315°) deve ser mais claro onde a encosta *olha* para NO. Correlação positiva entre iluminação e proximidade do aspecto a 315° confirma a convenção de aspecto (azimute da descida)."),
("code", '''hs = terrain.hillshade(DEM, TR)
ok = np.isfinite(asp) & np.isfinite(hs) & (terrain.slope_pct(sl) > 10)
closeness = np.cos(np.radians(asp[ok] - 315))
print("correlação (iluminação × cos(aspecto − 315°)) em encostas > 10%:", np.corrcoef(hs[ok], closeness)[0, 1].round(3))'''),
("md", "## 4. DEM ao vivo × recorte versionado (opcional, precisa de internet)"),
("code", '''if os.environ.get("TSI_RUN_NETWORK") == "1" or True:
    try:
        bbox = (-46.80, -22.22, -46.76, -22.18)
        live = demmod.fetch_live(bbox)
        with rasterio.open(ROOT / "sample_data/demo_dem_glo30.tif") as s:
            arr, _ = demmod.read_window(s, bbox)
        print("shape ao vivo:", live.array.shape, "· amostra:", arr.shape, "· idênticos:", bool(np.allclose(live.array, arr, equal_nan=True)))
        print("recuperado em:", live.meta["retrieved_at"], "\\nfonte:", live.meta["source"])
    except Exception as e:
        print("Sem rede/fonte indisponível, comparação ao vivo PULADA:", repr(e)[:120])'''),
("md", "## Conclusões\n\n- O recorte é um DSM real (663–1106 m), sem lacunas, em EPSG:4326 com células de ≈ 28,6 × 30,8 m. A fonte marca `AREA_OR_POINT=Point`; usamos a geotransformação do arquivo (limites a meio pixel de graus inteiros), então pode haver uma ambiguidade posicional de até meio pixel (~15 m) que não verificamos.\n- A soma de pixels reproduz a área da propriedade (razão 0,999); no talhão de 1,8 ha os 16 pixels cobrem só 79% da área, razão do aviso de 'poucos pixels'.\n- A convenção de aspecto é consistente com o sombreamento (correlação 0,92 em encostas > 10%).\n- O recorte versionado é idêntico ao tile ao vivo (verificado em 31/10/2026).\n- **Limite:** nada aqui mede a exatidão do DEM contra o terreno."),
]

NB3 = [
("md", "# 03 · SoilGrids: o que a incerteza diz sobre o que podemos concluir\n\nO SoilGrids entrega, para cada pixel de 250 m, a média predita e o intervalo de predição de 90% (Q0.05–Q0.95). Este notebook mede **quão largo** é esse intervalo frente à variação espacial da média, e **verifica a camada `uncertainty`** do ISRIC, que decidimos não usar."),
("code", SETUP),
("code", '''import pandas as pd
bbox = (-46.7915, -22.2095, -46.77, -22.1915)
S = soilmod.fetch_demo(bbox); L = S["layers"]
g = lambda p, d, s: L[soilmod.layer_name(p, d, s)]
print("propriedades:", S["props"], "· profundidades:", S["depths"], "· grade:", g("clay", "0-5cm", "mean").shape)'''),
("md", "## 1. Largura do intervalo de 90% × variação espacial da média\n\nSe a **variação espacial** da média predita é minúscula perto da **largura do intervalo**, os mapas de solo dentro de uma propriedade pequena mostram quase só a estrutura do modelo (covariáveis suaves), não diferenças medidas."),
("code", '''rows = []
for p in S["props"]:
    for d in S["depths"]:
        m, lo, hi = g(p, d, "mean"), g(p, d, "q05"), g(p, d, "q95")
        ok = np.isfinite(m)
        rows.append((p, d, np.nanmean(m[ok]), np.nanstd(m[ok]), np.nanmean((hi - lo)[ok]), np.nanstd(m[ok]) / np.nanmean((hi - lo)[ok])))
t = pd.DataFrame(rows, columns=["atributo", "prof.", "média", "desvio espacial da média", "largura média do IC90", "desvio ÷ largura"]).round(3)
print(t.to_string(index=False))
print("\\nMediana de (desvio espacial ÷ largura do intervalo):", t["desvio ÷ largura"].median().round(3))'''),
("code", '''fig, ax = plt.subplots(1, 3, figsize=(11, 3.2))
for a, (p, d, ttl) in zip(ax, [("clay", "0-5cm", "Argila 0–5 cm (%)"), ("soc", "0-5cm", "COS 0–5 cm (g/kg)"), ("phh2o", "0-5cm", "pH 0–5 cm")]):
    m, lo, hi = g(p, d, "mean"), g(p, d, "q05"), g(p, d, "q95")
    ok = np.isfinite(m)
    idx = np.argsort(m[ok])
    mm, ll, hh = m[ok][idx], lo[ok][idx], hi[ok][idx]
    a.fill_between(range(len(mm)), ll, hh, alpha=.3, color="C2", label="IC 90%"); a.plot(mm, "k.", ms=2, label="média"); a.set_title(ttl, fontsize=9); a.set_xlabel("pixels ordenados pela média")
ax[0].legend(fontsize=7); plt.tight_layout(); plt.show()'''),
("md", "## 2. Textura é composicional: soma ≈ 100%\n\nAreia + silte + argila devem somar ~100% (SoilGrids modela a textura como dado composicional). Serve de verificação do **fator de conversão** (g/kg → %)."),
("code", '''tot = g("sand", "0-5cm", "mean") + g("silt", "0-5cm", "mean") + g("clay", "0-5cm", "mean")
print("soma textura 0–5 cm: min/méd/máx =", np.nanmin(tot).round(2), np.nanmean(tot).round(2), np.nanmax(tot).round(2))
cls = pd.Series([soilmod.texture_class(c, si, sa) for c, si, sa in zip(g("clay", "0-5cm", "mean").ravel(), g("silt", "0-5cm", "mean").ravel(), g("sand", "0-5cm", "mean").ravel())]).value_counts()
print("\\nclasse textural USDA das médias preditas (0–5 cm):\\n", cls.to_string())
lo_c, hi_c = np.nanmean(g("clay", "0-5cm", "q05")), np.nanmean(g("clay", "0-5cm", "q95"))
lo_s, hi_s = np.nanmean(g("sand", "0-5cm", "q05")), np.nanmean(g("sand", "0-5cm", "q95"))
print(f"\\nLimites médios do IC90 (0–5 cm): argila {lo_c:.1f}–{hi_c:.1f}% · areia {lo_s:.1f}–{hi_s:.1f}% → o intervalo abrange texturas muito diferentes; a classe das médias não é determinada pelos dados.")'''),
("md", "## 3. Resolução: quantos pixels do SoilGrids cabem em cada zona?"),
("code", '''gj = json.loads((ROOT / "sample_data/propriedade_demo.geojson").read_text())
shape = g("clay", "0-5cm", "mean").shape
rows = []
for f in gj["features"]:
    G = geom.validate_geometry(f["geometry"]).geometry
    mk, mode = zonal._soil_stat(G, g("clay", "0-5cm", "mean"), S["transform"], shape)
    v = g("clay", "0-5cm", "mean")[mk]
    rows.append((f["properties"]["name"], round(geom.metrics(G)["area_ha"], 1), int(np.isfinite(v).sum()), mode, round(float(np.nanmean(v)), 2)))
print(pd.DataFrame(rows, columns=["zona", "área (ha)", "pixels 250 m", "amostragem", "argila média (%)"]).to_string(index=False))'''),
("md", "## 4. Verificação da camada `uncertainty` do ISRIC (precisa de internet)\n\nUma fonte secundária descreve `uncertainty` como (Q0.95 − Q0.05)/Q0.50. A página oficial de documentação do ISRIC estava indisponível (HTTP 502) durante a construção, então **testamos a definição nos dados**: baixamos a camada `uncertainty` do mesmo recorte e comparamos com a razão calculada."),
("code", '''import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
try:
    tr, h, w = soilmod.grid_for_bbox(bbox)
    url = "/vsicurl/https://files.isric.org/soilgrids/latest/data/clay/clay_0-5cm_uncertainty.vrt"
    with rasterio.open(url) as src:
        print("dtype:", src.dtypes[0], "· nodata declarado:", src.nodata, "· tags:", {k: v for k, v in src.tags().items() if k in ("Description", "Units", "Unit")})
        with WarpedVRT(src, crs="EPSG:4326", transform=tr, width=w, height=h, resampling=Resampling.nearest, nodata=src.nodata) as v:
            u = v.read(1).astype("float64")
    u[u == src.nodata] = np.nan
    q05, q50, q95 = (soilmod._read_layer("clay", "0-5cm", s, tr, h, w) for s in ("q05", "q50", "q95"))
    ratio = (q95 - q05) / q50
    ok = np.isfinite(u) & np.isfinite(ratio)
    print(f"pixels comparáveis: {ok.sum()}")
    print("uncertainty (bruto): P5/P50/P95 =", np.nanpercentile(u[ok], [5, 50, 95]).round(1))
    print("(Q95−Q05)/Q50:        P5/P50/P95 =", np.nanpercentile(ratio[ok], [5, 50, 95]).round(3))
    print("correlação de Pearson:", np.corrcoef(u[ok], ratio[ok])[0, 1].round(3), "· razão mediana uncertainty/ratio:", np.nanmedian(u[ok]/ratio[ok]).round(2))
except Exception as e:
    print("Sem rede/fonte indisponível, verificação PULADA:", repr(e)[:150])'''),
("md", "## Conclusões\n\n- A variação espacial da média predita dentro de uma propriedade é uma **fração pequena** da largura do intervalo de 90%: os mapas mostram estrutura do modelo, não diferenças medidas entre talhões.\n- A soma da textura ≈ 100% confirma o fator g/kg → %.\n- Talhões de poucos hectares **herdam o pixel** de 250 m; talhões vizinhos podem ter valor idêntico.\n- Sobre a camada `uncertainty`: nos 68 pixels comparados, ela é ≈ 10 × (Q0.95 − Q0.05)/Q0.50 (razão mediana 9,98; correlação 0,955; o valor bruto é inteiro, o que explica parte da diferença). Isso é **consistente** com a descrição de fonte secundária (a razão), mas a documentação oficial do ISRIC estava indisponível, então a definição e o fator 10 não estão confirmados. O projeto usa Q0.05/Q0.95, que dão a mesma informação diretamente.\n- **Não conclui:** nada sobre fertilidade, adubação ou compactação; isso exige amostragem e análise de solo."),
]


def build(cells, name):
    nb = nbf.v4.new_notebook()
    nb.cells = [nbf.v4.new_markdown_cell(c) if k == "md" else nbf.v4.new_code_cell(c) for k, c in cells]
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    return nb


if __name__ == "__main__":
    run = "--no-run" not in sys.argv
    for name, cells in [("01_validacao_terreno", NB1), ("02_validacao_dem_real", NB2), ("03_soilgrids_incerteza", NB3)]:
        nb = build(cells, name)
        if run:
            NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(OUT)}}).execute()
        nbf.write(nb, OUT / f"{name}.ipynb")
        print("ok", name)
