"""Relatório PDF: resultados, metodologia, fontes e limitações (sempre juntos)."""
from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import matplotlib
import numpy as np
from matplotlib import font_manager

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402

from . import render, terrain  # noqa: E402
from . import soil as soilmod  # noqa: E402

_FONT = Path(font_manager.findfont("DejaVu Sans"))
_FONT_B = Path(font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans", weight="bold")))
pdfmetrics.registerFont(TTFont("DV", str(_FONT)))
pdfmetrics.registerFont(TTFont("DV-B", str(_FONT_B)))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV", boldItalic="DV-B")

SS = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=SS["Heading1"], fontName="DV-B", fontSize=17, spaceAfter=6, textColor=colors.HexColor("#14532d"))
H2 = ParagraphStyle("H2", parent=SS["Heading2"], fontName="DV-B", fontSize=12, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#14532d"))
P = ParagraphStyle("P", parent=SS["BodyText"], fontName="DV", fontSize=8.6, leading=12)
SM = ParagraphStyle("SM", parent=P, fontSize=7.4, leading=10)
WARN = ParagraphStyle("W", parent=P, backColor=colors.HexColor("#fff4e5"), borderColor=colors.HexColor("#f59e0b"), borderWidth=0.6,
                      borderPadding=5, spaceBefore=4, spaceAfter=8)

SOURCES = [
    ("Copernicus DEM GLO-30", "https://registry.opendata.aws/copernicus-dem/", "Licença Copernicus; DSM de 1\" (~30 m); EGM2008; WGS 84"),
    ("SoilGrids 2.0 (ISRIC)", "https://www.isric.org/explore/soilgrids", "CC BY 4.0; 250 m; Poggio et al. (2021), SOIL 7:217–240 (referência não reconfirmada)"),
    ("Classes de relevo (declividade)", "Santos et al., Sistema Brasileiro de Classificação de Solos (SiBCS), EMBRAPA", "Classes: plano, suave ondulado, ondulado, forte ondulado, montanhoso, escarpado (referência bibliográfica; link não verificado)"),
    ("Horn (1981)", "https://doi.org/10.1109/PROC.1981.11918", "Hill shading and the reflectance map — gradiente 3×3 ponderado"),
]


def _tbl(data, widths=None, head=True, fs=7.4):
    cell = ParagraphStyle("c", parent=P, fontSize=fs, leading=fs + 2.2)
    hcell = ParagraphStyle("h", parent=cell, fontName="DV-B", textColor=colors.white)

    def wrap(v, h):
        if isinstance(v, str):
            return Paragraph(v.replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br/>"), hcell if h else cell)
        return v
    data = [[wrap(v, head and i == 0) for v in row] for i, row in enumerate(data)]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")])]
    if head:
        st += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14532d"))]
    t.setStyle(TableStyle(st))
    return t


def _fig_img(fig, width_cm):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    im = Image(buf)
    r = im.imageHeight / im.imageWidth
    im.drawWidth, im.drawHeight = width_cm * cm, width_cm * cm * r
    return im


def _maps_figure(outdir: Path, res: dict):
    z = np.load(outdir / "layers.npz")
    dem, slope, aspect, hs, mask = z["dem"], z["slope"], z["aspect"], z["hs"], z["mask"]
    tr = z["tr"]
    ext = [tr[2], tr[2] + tr[0] * dem.shape[1], tr[5] + tr[4] * dem.shape[0], tr[5]]
    cont = json.loads((outdir / "contours.geojson").read_text())
    geo = json.loads((outdir / "property.geojson").read_text())
    fig, axs = plt.subplots(1, 3, figsize=(11, 4.1))
    lg = [l for l in res["layers"] if l["id"] == "elevation"][0]["legend"]
    layers = [("Elevação (m, DSM)", render.continuous(dem, mask, lg["min"], lg["max"], "cividis")),
              ("Declividade (classes EMBRAPA)", render.slope_rgba(slope, mask)),
              ("Orientação das encostas", render.aspect_rgba(aspect, mask, dem))]
    for ax, (title, rgba) in zip(axs, layers):
        ax.imshow(np.stack([(hs * 255).astype(np.uint8)] * 3, -1), extent=ext, alpha=0.9)
        ax.imshow(rgba, extent=ext, alpha=0.8)
        ax.set_title(title, fontsize=8)
        for f in geo["features"]:
            if f["properties"]["kind"] == "plot":
                for poly in ([f["geometry"]["coordinates"]] if f["geometry"]["type"] == "Polygon" else f["geometry"]["coordinates"]):
                    xs, ys = zip(*poly[0])
                    ax.plot(xs, ys, color="white", lw=0.8)
        ax.set_xticks([]), ax.set_yticks([])
    for f in cont["features"]:
        g = f["geometry"]
        lines = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"] if g["type"] == "MultiLineString" else []
        for ln in lines:
            xs, ys = zip(*ln)
            axs[0].plot(xs, ys, color="black", lw=0.35, alpha=0.7)
    fig.text(0.5, 0.01, "Curvas: interpoladas do DSM, não medidas de campo. Fonte: Copernicus DEM GLO-30.", ha="center", fontsize=6.5)
    return fig


def _charts_figure(res: dict):
    z = res["zones"]["property"]
    fig, axs = plt.subplots(1, 3, figsize=(11, 3.1))
    h = z["hypsometry"]
    axs[0].plot(np.array(h["area_above"]) * 100, h["elevation"], color="#14532d")
    axs[0].set_xlabel("% da área acima"), axs[0].set_ylabel("Elevação (m)"), axs[0].set_title("Curva hipsométrica", fontsize=8)
    cl = z["slope_classes"]
    axs[1].barh([c["class"] for c in cl][::-1], [c["share"] * 100 for c in cl][::-1], color=render.SLOPE_COLORS[::-1])
    axs[1].set_xlabel("% da área"), axs[1].set_title("Classes de declividade", fontsize=8)
    ax = plt.subplot(133, projection="polar")
    axs[2].remove()
    oc = z["aspect"]["octants"]
    th = np.radians(np.arange(0, 360, 45))
    ax.bar(th, [oc[k] * 100 for k in terrain.ASPECT_NAMES], width=np.radians(40), color=[render.ASPECT_COLORS[k] for k in terrain.ASPECT_NAMES])
    ax.set_theta_zero_location("N"), ax.set_theta_direction(-1), ax.set_xticks(th), ax.set_xticklabels(terrain.ASPECT_NAMES, fontsize=6)
    ax.tick_params(labelsize=6)
    ax.set_title(f"Aspecto (plano: {z['aspect']['flat_share'] * 100:.1f}%)", fontsize=8)
    for a in axs[:2]:
        a.tick_params(labelsize=7)
    fig.tight_layout()
    return fig


def _f(v, n=1, unit=""):
    return "–" if v is None else f"{v:,.{n}f}{unit}".replace(",", " ")


def build_pdf(outdir: Path, res: dict) -> Path:
    path = outdir / "relatorio.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            title=f"Relatório territorial — {res['name']}", author="Terrain & Soil Intelligence")
    m = res["metrics"]["property"]
    d = res["dem"]
    story = [Paragraph(f"Análise territorial — {res['name']}", H1),
             Paragraph(f"Gerado em {datetime.fromisoformat(res['created_at']).strftime('%d/%m/%Y %H:%M UTC')} · modo: <b>{'DEMONSTRAÇÃO (dados de amostra offline)' if res['mode'] == 'demo' else 'LIVE (fontes remotas)'}</b>", P),
             Paragraph("<b>Leia antes de usar.</b> O Copernicus DEM GLO-30 é um modelo digital de <b>superfície</b> (DSM), com célula de ~30 m. Não é "
                       "levantamento topográfico: não captura microdesníveis nem serve para planejar trajetórias de pulverizadores. "
                       "Atributos de solo são estimativas de modelo (250 m) com intervalos de predição largos. Este relatório não estima compactação, "
                       "fertilidade real, necessidade de adubação nem risco de tráfego ou tombamento.", WARN),
             Paragraph("1. Geometria", H2)]
    story.append(_tbl([["Indicador", "Valor", "Observação"],
                       ["Área (UTM)", _f(m["area_ha"], 2, " ha"), f"{m['crs_projected']} · {m['crs_projected_name']}"],
                       ["Área (geodésica, WGS 84)", _f(m["area_ha_geodesic"], 2, " ha"), f"diferença UTM×geodésica: {m['area_diff_pct']:+.3f}%"],
                       ["Perímetro", _f(m["perimeter_m"], 0, " m"), f"geodésico: {_f(m['perimeter_m_geodesic'], 0, ' m')}"],
                       ["Centroide (lon, lat)", f"{m['centroid']['lon']:.5f}, {m['centroid']['lat']:.5f}", "EPSG:4326"],
                       ["Caixa envolvente", ", ".join(f"{v:.5f}" for v in m["bbox"]), "minx, miny, maxx, maxy (graus)"],
                       ["Talhões", str(len(res["metrics"]["plots"])), ", ".join(res["metrics"]["plots"]) or "–"]],
                      [4.4 * cm, 4.5 * cm, 8.8 * cm]))
    for i in res["geometry_issues"]:
        if i["severity"] != "info":
            story.append(Paragraph(f"⚠ {i['message']}" + (f" ({i['feature']})" if i.get("feature") else ""), SM))
    story += [Paragraph("2. Terreno", H2), _fig_img(_maps_figure(outdir, res), 17.4), _fig_img(_charts_figure(res), 17.4)]
    rows = [["Zona", "Área (ha)", "Pixels", "Elev. mín–méd–máx (m)", "Decliv. média / P95 (%)", "Aspecto dominante", "Avisos"]]
    for k, z in res["zones"].items():
        a = m["area_ha"] if k == "property" else res["metrics"]["plots"][k]["area_ha"]
        rows.append([("Propriedade" if k == "property" else k), _f(a, 1), str(z["n_pixels"]),
                     f"{_f(z['elevation_m']['min'], 0)}–{_f(z['elevation_m']['mean'], 0)}–{_f(z['elevation_m']['max'], 0)}",
                     f"{_f(z['slope_pct']['mean'])} / {_f(z['slope_pct']['p95'])}", z["aspect"]["dominant"] or "–",
                     "sim" if z["quality_flags"] else "–"])
    story.append(_tbl(rows, [3.6 * cm, 1.6 * cm, 1.3 * cm, 3.7 * cm, 3.3 * cm, 2.2 * cm, 1.4 * cm]))
    for k, z in res["zones"].items():
        for f in z["quality_flags"]:
            story.append(Paragraph(f"⚠ {k}: {f}", SM))
    story.append(Paragraph(f"Curvas de nível a cada <b>{res['params']['contour_interval_m']:g} m</b> (intervalo coerente com a exatidão vertical especificada, &lt; 4 m LE90). "
                           "A elevação é altura ortométrica (EGM2008), não altura elipsoidal.", SM))

    story.append(Paragraph("3. Solo (SoilGrids 2.0)", H2))
    soil = res.get("soil")
    if not soil or "error" in (soil or {}):
        story.append(Paragraph(f"Solo não disponível nesta análise: {(soil or {}).get('error', 'desativado')}.", P))
    else:
        story.append(Paragraph("Cada célula traz a <b>média predita</b> e, entre colchetes, a média dos limites <b>Q0.05–Q0.95</b> do intervalo de predição de 90% "
                               "<i>por pixel</i>. Não é intervalo de confiança da média da zona, e a faixa larga indica que o modelo, nessa escala, "
                               "não distingue a zona de uma ampla faixa de valores.", P))
        depth = soil["depths"][0]
        hdr = ["Zona"] + [f"{soilmod.PROPERTIES[p]['label']} ({soilmod.PROPERTIES[p]['unit']})" for p in ("phh2o", "soc", "clay", "silt", "sand")]
        for dd in soil["depths"]:
            rows = [hdr]
            for k, zz in soil["zones"].items():
                r = [("Propriedade" if k == "property" else k)]
                for p in ("phh2o", "soc", "clay", "silt", "sand"):
                    x = zz["properties"][p]["depths"][dd]
                    r.append("–" if not x.get("available") else f"{x['mean']:.1f}\n[{x['q05_mean']:.1f}–{x['q95_mean']:.1f}]")
                rows.append(r)
            story += [Paragraph(f"Profundidade {dd}", SM), _tbl(rows, [3.4 * cm] + [2.8 * cm] * 5, fs=6.8)]
        for k, zz in soil["zones"].items():
            for f in zz["quality_flags"]:
                story.append(Paragraph(f"⚠ {k}: {f}", SM))
        tx = soil["zones"]["property"]["texture_class_of_means"]
        if tx:
            story.append(Paragraph("Classe textural USDA da <i>média predita</i> da propriedade: " + "; ".join(f"{k}: {v}" for k, v in tx.items()) +
                                   ". Com intervalos tão largos, a classe real pode ser outra.", SM))
    story += [PageBreak(), Paragraph("4. Metodologia", H2)]
    px = d["pixel_size_m_at_centroid"]
    meth = [
        f"<b>Elevação:</b> {d['product']} ({d['model_type']}), {d['nominal_resolution']}; célula local ≈ {px[0]:.1f} m (E–O) × {px[1]:.1f} m (N–S). "
        f"CRS horizontal {d['horizontal_crs']}; datum vertical {d['vertical_datum']}. Aquisição: {d['acquisition_period']}. Exatidão vertical: {d['vertical_accuracy_spec']}. "
        f"Fonte: {d.get('source', '')}" + (f"; acessado em {d['retrieved_at']}" if d.get("retrieved_at") else "; recorte de amostra versionado no repositório") + ".",
        "<b>Área e perímetro:</b> polígono projetado para SIRGAS 2000 / UTM (zona do centroide), com conferência geodésica no elipsoide WGS 84.",
        "<b>Declividade e aspecto:</b> gradiente de Horn (3×3) com tamanho de célula em metros calculado por latitude (sem reamostrar a elevação). "
        "Declividade = arctan(√(dz/dx² + dz/dy²)); aspecto = azimute da descida, horário a partir do Norte; células com declividade &lt; 1° são 'planas'.",
        "<b>Classes de relevo:</b> EMBRAPA/SiBCS (0–3, 3–8, 8–20, 20–45, 45–75, &gt;75%). É classificação descritiva, não de risco operacional.",
        "<b>Estatísticas por zona:</b> rasterstats sobre os pixels cujo centro cai no polígono; polígonos menores que um pixel usam os pixels tocados.",
        "<b>Curvas de nível:</b> isolinhas do DSM (contourpy) em múltiplos do intervalo, recortadas ao perímetro. São interpoladas.",
        "<b>Solo:</b> SoilGrids 2.0 (Quantile Random Forest), camadas média, Q0.05, Q0.5 e Q0.95; valores convertidos das unidades mapeadas (pH×10, dg/kg, g/kg). "
        "A camada 'uncertainty' do ISRIC não foi usada: os quantis Q0.05/Q0.95 dão a informação diretamente (a camada é ≈ 10 × (Q0.95 − Q0.05)/Q0.50, verificado empiricamente; definição oficial não confirmada).",
    ]
    story += [Paragraph(t, P) for t in meth]
    story.append(Paragraph("5. Limitações", H2))
    story += [Paragraph("• " + t, P) for t in res["limitations"]]
    for w in res["warnings"]:
        story.append(Paragraph("• Aviso desta execução: " + w, P))
    story.append(Paragraph("6. Fontes e licenças", H2))
    story.append(_tbl([["Fonte", "Endereço", "Observação"]] + [[Paragraph(a, SM), Paragraph(b, SM), Paragraph(c, SM)] for a, b, c in SOURCES], [3.8 * cm, 6.3 * cm, 7.6 * cm], fs=7))
    story.append(Spacer(1, 6))
    story.append(Paragraph(d["attribution"], SM))
    doc.build(story)
    return path
