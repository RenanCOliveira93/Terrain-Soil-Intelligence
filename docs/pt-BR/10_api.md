# 10 · API

Base: `http://localhost:8000/api` (ou `/api` atrás do nginx). Documentação interativa em **`/docs`** (Swagger) e **`/redoc`**; o esquema está versionado em [`../openapi.json`](../openapi.json) (gerado por `python scripts/export_openapi.py`).

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | status, modo (`demo`/`live`), banco |
| GET | `/sources` | metadados das fontes (DEM, SoilGrids), unidades, limitações |
| POST | `/geometry/validate` | valida um GeoJSON; devolve problemas, métricas e geometria (reparada se `repair`) |
| POST | `/import` | multipart `file` (`.geojson`/`.kml`/`.zip` Shapefile): lê, reprojeta, valida cada feição |
| GET/POST | `/properties` | lista (filtros `q`, `min_area_ha`, `max_area_ha`, `has_analysis`) / cria propriedade com talhões |
| GET/PUT/DELETE | `/properties/{id}` | detalhe / atualiza / exclui (a propriedade demo é somente leitura) |
| POST | `/properties/{id}/analyses` | **inicia job assíncrono**: `{contour_interval_m?, soil}` → 202 `{analysis_id, job_id, status_url}` |
| GET | `/jobs/{id}` | `status` (`queued/running/done/failed`), `progress` 0–1, `stage`, `error` |
| GET | `/analyses/{id}` | resultados completos (JSON) |
| GET | `/analyses/{id}/layers/{layer}` | PNG RGBA da camada (`elevation`, `hillshade`, `slope`, `aspect`, `soil:<attr>:<prof>:<mean\|pi>`); cabeçalho `X-Bounds` = `[oeste, sul, leste, norte]` |
| GET | `/analyses/{id}/contours` | curvas de nível (GeoJSON) |
| GET | `/analyses/{id}/compare?a=&b=` | compara duas zonas (`property` ou nome do talhão) |
| GET | `/analyses/{id}/export/{kind}` | `dem`, `slope`, `aspect` (GeoTIFF), `contours`, `geojson` (zonas + estatísticas), `report` (PDF), `results` (JSON) |

## Códigos de erro
| Código | Quando |
|---|---|
| 409 | resultados pedidos antes de a análise terminar |
| 413 | upload acima de `TSI_MAX_UPLOAD_MB` |
| 422 | geometria inválida/irreparável, CRS fora de faixa, formato não suportado, intervalo de curvas < 5 m |
| 403 | tentar alterar/excluir a propriedade de demonstração |
| 404 | recurso inexistente |

Os erros de geometria trazem `detail.issues[]` com `code`, `severity` e `message` (ex.: `CRS_RANGE`, `GEOM_INVALID`, `GEOM_REPAIRED`, `PLOT_OVERLAP`, `PLOT_OUTSIDE`, `AREA_HUGE`, `UTM_SPAN`).

## Exemplo com curl
```bash
API=http://localhost:8000/api
# 1) criar propriedade a partir de um GeoJSON
curl -s -X POST $API/properties -H 'content-type: application/json' \
  -d '{"name":"Minha área","geometry":{"type":"Polygon","coordinates":[[[-46.79,-22.21],[-46.78,-22.21],[-46.78,-22.20],[-46.79,-22.20],[-46.79,-22.21]]]}}'
# 2) iniciar a análise e acompanhar
curl -s -X POST $API/properties/<ID>/analyses -H 'content-type: application/json' -d '{"contour_interval_m":10,"soil":true}'
curl -s $API/jobs/<ANALYSIS_ID>
# 3) baixar o PDF e o GeoTIFF do DEM recortado
curl -sLo relatorio.pdf  $API/analyses/<ANALYSIS_ID>/export/report
curl -sLo dem.tif        $API/analyses/<ANALYSIS_ID>/export/dem
```

## Exemplo em Python
```python
import httpx, time
api = httpx.Client(base_url="http://localhost:8000/api", timeout=60)
pid = api.get("/properties").json()[0]["id"]
aid = api.post(f"/properties/{pid}/analyses", json={"soil": True}).json()["analysis_id"]
while (j := api.get(f"/jobs/{aid}").json())["status"] in ("queued", "running"):
    print(f"{j['progress']:.0%} {j['stage']}"); time.sleep(0.3)
r = api.get(f"/analyses/{aid}").json()
print(r["zones"]["property"]["slope_pct"], r["dem"]["vertical_datum"])
```

## Formato dos GeoTIFF exportados
EPSG:4326, `float32`, `nodata = -9999`, recortados à caixa envolvente do polígono e **mascarados fora do perímetro**. DEM em metros (EGM2008); declividade em **graus**; aspecto em graus (azimute da descida; −9999 = plano).

## Segurança e limites
Sem autenticação (é uma ferramenta local/de equipe: **não exponha à internet sem um proxy autenticado**). Upload limitado em tamanho; ZIP com limite de descompactação e só os componentes do `.shp` escolhido são extraídos (evita *path traversal*); o KML é lido com entidades externas desligadas (teste de XXE).
