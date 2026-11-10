# Guia técnico · Terrain & Soil Intelligence

Documentação de engenharia da plataforma: arquitetura, fontes de dados, instalação e execução, metodologia, API, testes, limitações e licenças.

## Sumário
1. [Escopo e avisos de uso](#1-escopo-e-avisos-de-uso)
2. [Arquitetura](#2-arquitetura)
3. [Fontes de dados e proveniência](#3-fontes-de-dados-e-proveniência)
4. [Instalação, execução e reprodução](#4-instalação-execução-e-reprodução)
5. [Metodologia e pipeline](#5-metodologia-e-pipeline)
6. [API](#6-api)
7. [Interpretação dos resultados](#7-interpretação-dos-resultados)
8. [Testes e validação](#8-testes-e-validação)
9. [Limitações conhecidas](#9-limitações-conhecidas)
10. [Licenças e atribuições](#10-licenças-e-atribuições)
11. [Solução de problemas](#11-solução-de-problemas)

---

## 1. Escopo e avisos de uso

A plataforma recebe o perímetro de uma propriedade (desenhado ou importado em GeoJSON, KML ou Shapefile ZIP) e calcula área, perímetro, elevação, declividade, aspecto, hipsometria, curvas de nível e atributos de solo estimados, com comparação de talhões, exportação (GeoTIFF, GeoJSON, PDF) e relatório com metodologia, fontes e limitações.

Avisos que se aplicam a todos os resultados:

- O **Copernicus DEM GLO-30 é um DSM** (modelo de superfície; inclui copas e construções), com célula de cerca de 30 m. Não é levantamento topográfico: não representa microdesníveis nem serve para planejar trajetórias de pulverizadores ou máquinas.
- As curvas de nível são **interpoladas** do DSM, não são medidas de campo.
- O **SoilGrids** é uma **predição de modelo** a 250 m, com intervalos de 90% muito largos (na demonstração, argila 37,8% [5,8–79,9]). A aplicação não afirma diferenças de solo entre talhões.
- A aplicação **não estima** compactação, fertilidade real, necessidade de calagem ou adubação, risco de tráfego ou de tombamento. Um teste automatizado impede que o resultado contenha esses indicadores.
- Os polígonos do modo demonstração são **fictícios** (sobre dados reais).
- A exatidão do DEM não foi validada contra levantamento de campo.

## 2. Arquitetura

```
Usuário
  └─ Frontend (React + TypeScript + MapLibre GL JS)
       └─ /api (JSON, PNG, GeoTIFF, PDF)
            └─ Backend FastAPI ── Banco (PostGIS; SQLite no modo demo)
                 └─ Jobs assíncronos (ThreadPoolExecutor)
                      └─ Núcleo geoespacial (Shapely · GeoPandas · Rasterio · rasterstats)
                           ├─ Copernicus DEM GLO-30 (COG na AWS, leitura por janela HTTP range)
                           ├─ SoilGrids 2.0 (files.isric.org, VRT/COG)
                           └─ sample_data/ (recortes reais, modo demo offline)
                      └─ data/analyses/<id>/ (GeoTIFF · GeoJSON · PNG · PDF)
```

### 2.1 Componentes

| Caminho | Conteúdo |
|---|---|
| `backend/app/main.py` | rotas FastAPI, validação de entrada, exportações |
| `backend/app/core/geometry.py` | validação, escolha de UTM, área/perímetro/centroide/bbox, talhões |
| `backend/app/core/io.py` | GeoJSON, KML (lxml seguro), Shapefile ZIP |
| `backend/app/core/dem.py` | tiles do Copernicus (COG remoto), cache, modo demo |
| `backend/app/core/terrain.py` | gradiente de Horn, aspecto, hipsometria, *hillshade*, classes |
| `backend/app/core/contours.py` | curvas de nível e política de intervalo |
| `backend/app/core/soil.py` | SoilGrids, conversões, textura USDA |
| `backend/app/core/zonal.py` | estatísticas zonais com avisos de qualidade |
| `backend/app/core/analysis.py` | orquestra a análise e grava os artefatos |
| `backend/app/core/render.py` | PNG das camadas e legendas |
| `backend/app/core/report.py` | relatório PDF |
| `backend/app/store.py`, `backend/app/jobs.py` | persistência SQLAlchemy (PostGIS/SQLite) e jobs |
| `frontend/src` | `App.tsx` e `components/` (mapa, painéis, gráficos SVG, diálogos) |
| `infra/` | Dockerfiles, nginx, `init.sql` |

### 2.2 Fluxo de uma análise (job assíncrono)

1. `POST /properties/{id}/analyses` responde 202 com `{analysis_id}` e submete o job.
2. O frontend consulta `GET /jobs/{id}` a cada 300 ms (`status`, `progress`, `stage`).
3. Etapas e progresso aproximado: validação das geometrias (3%), leitura da janela do DEM (10%), declividade/aspecto/zonais (35–50%), curvas de nível (60%), leitura do SoilGrids (68%), zonais do solo (85%), GeoTIFF/PNG/JSON/PDF (90–100%).
4. `GET /analyses/{id}` devolve os resultados e as camadas PNG.

O progresso é gravado na tabela `analyses` (`status`, `progress`, `stage`), de modo que qualquer réplica da API vê o estado. Se uma etapa **opcional** (solo) falha, a análise termina com aviso explícito; se uma etapa essencial (DEM) falha, o job termina como `failed` com a mensagem.

### 2.3 Modelo de dados

- `properties`: `id`, `name`, `geom` (MULTIPOLYGON 4326, índice GiST no PostGIS), `area_ha`, `is_demo`.
- `plots`: `id`, `property_id`, `name`, `geom`, `area_ha` (muitos por propriedade).
- `analyses`: `id`, `property_id`, `status`, `progress`, `stage`, `params`, `summary`, `mode`.

Rasters e resultados detalhados ficam em `data/analyses/<id>/` (fora do banco): `results.json`, `dem_clip.tif`, `slope_deg.tif`, `aspect_deg.tif`, `contours.geojson`, `property.geojson`, `layers.npz`, `soil.npz`, `relatorio.pdf`.

PostGIS e SQLite: o tipo `GeomType` grava `geometry(MULTIPOLYGON, 4326)` no PostgreSQL (índice GiST criado pelo GeoAlchemy2) e GeoJSON em texto no SQLite.

### 2.4 Decisões de projeto

| Decisão | Motivo |
|---|---|
| Não reprojetar o DEM; dx/dy por latitude | evita interpolar a elevação antes de derivar a declividade |
| Medir área em UTM e conferir no elipsoide | rigor e autoverificação |
| Camadas como PNG + `image` source no MapLibre | leve, funciona offline, fácil legenda (não é pirâmide de tiles) |
| `ThreadPoolExecutor` em vez de Celery | a análise de uma propriedade leva segundos; se a carga crescer, usar fila externa |
| Solo opcional, com falha isolada | o SoilGrids pode estar indisponível |
| Avisos de qualidade no resultado (`quality_flags`) | números sem aviso de representatividade enganam |
| Faixas fixas nas legendas de solo | a autoescala faria diferenças ínfimas parecerem grandes |
| Mapa de cores `cividis` para elevação | `terrain` tem degrau de cor que parece uma borda no relevo |

## 3. Fontes de dados e proveniência

| Fonte | Uso | Acesso |
|---|---|---|
| Copernicus DEM GLO-30 (Cloud Optimized GeoTIFF, AWS Open Data, bucket `copernicus-dem-30m`, versão 2021) | elevação, declividade, aspecto, curvas | `TSI_DEM_BASE_URL` (padrão `https://copernicus-dem-30m.s3.amazonaws.com`) |
| SoilGrids 2.0 (ISRIC) | pH, carbono orgânico, argila, silte, areia | `TSI_SOILGRIDS_BASE_URL` (padrão `https://files.isric.org/soilgrids/latest/data`) |
| OpenStreetMap | mapa base opcional (desligado por padrão) | online |

### 3.1 Copernicus DEM GLO-30

| Item | Valor | Origem da informação |
|---|---|---|
| Resolução | 1 arco-segundo (~30 m; a 22,2°S, ≈ 28,6 m E–O × 30,8 m N–S, medido) | registro AWS / medição |
| Horizontal | WGS 84 (EPSG:4326) | fonte secundária (EMD) |
| Vertical | EGM2008 (EPSG:3855), altura ortométrica | fonte secundária (catálogo GEE) |
| Exatidão vertical absoluta | < 4 m (LE90), especificação | Copernicus Data Space |
| Exatidão horizontal absoluta | < 6 m (CE90), especificação | Copernicus Data Space |
| Aquisição | 2010–2015 (TanDEM-X) | fonte secundária (EMD) |

O *Product Handbook* só pôde ser consultado como índice; datum e exatidão vêm de fontes secundárias. LE90 significa que 90% dos erros verticais são menores que 4 m nas condições da especificação; o erro local pode ser maior em encostas íngremes, floresta densa e áreas urbanas, e não foi medido para a região de demonstração. Oceano não possui tiles (assume-se altura 0); o tratamento de corpos d'água continentais não foi verificado.

### 3.2 SoilGrids 2.0

Mapas globais a 250 m produzidos pelo ISRIC com Quantile Random Forest sobre perfis do WoSIS e covariáveis ambientais. São predições de modelo, não medições. A incerteza é o intervalo de predição de 90% (Q0.05 e Q0.95) por pixel.

| Atributo | Código | Unidade mapeada | Unidade exibida | Conversão |
|---|---|---|---|---|
| pH em água | `phh2o` | pH × 10 | pH | ÷ 10 |
| Carbono orgânico | `soc` | dg/kg | g/kg | ÷ 10 |
| Argila | `clay` | g/kg | % | ÷ 10 |
| Silte | `silt` | g/kg | % | ÷ 10 |
| Areia | `sand` | g/kg | % | ÷ 10 |

Profundidades (cm): 0–5, 5–15, 15–30, 30–60, 60–100, 100–200; a amostra offline contém as três primeiras. Estatísticas por camada: média, Q0.05, Q0.5 e Q0.95.

**Verificação das unidades.** A documentação oficial do ISRIC (`docs.isric.org`) estava indisponível (HTTP 502) e a API REST (`rest.isric.org`) respondia 503 na data da consulta (31/10/2026); por isso as unidades foram conferidas nos dados: areia + silte + argila (0–5 cm) somam 99,9–100,1 por pixel (notebook 03), pH médio ≈ 5,3 e carbono ≈ 30,8 g/kg (0–5 cm) são plausíveis, e o pacote `soilDB` aplica o mesmo divisor. É evidência forte, mas não confirmação oficial; confirme na tabela do ISRIC antes de uso crítico.

**Camada `uncertainty` do ISRIC (não usada).** Nos mesmos 68 pixels (argila 0–5 cm), vale ≈ 10 × (Q0.95 − Q0.05) / Q0.50 (razão mediana 9,98; correlação de Pearson 0,955; valores brutos 20–24). A definição e o fator 10 não estão confirmados em documentação oficial; como os quantis fornecem a mesma informação diretamente, a aplicação usa Q0.05/Q0.95.

**Acesso.** Os VRT/COG são lidos com `rasterio` + `WarpedVRT`. A REST do ISRIC não é usada. A amostra offline (`sample_data/demo_soilgrids.tif`, 60 bandas) foi gerada pelo mesmo código; um teste marcado `network` confere que a leitura ao vivo reproduz a amostra pixel a pixel.

### 3.3 Dados de amostra (`sample_data/`)

| Arquivo | Conteúdo |
|---|---|
| `demo_dem_glo30.tif` | recorte real do Copernicus DEM GLO-30 (tile `Copernicus_DSM_COG_10_S23_00_W047_00_DEM`; recorte −46,84…−46,72 / −22,26…−22,14; ≈ 620 KB, 433×433 px, região de Espírito Santo do Pinhal, SP; obtido em 31/10/2026) |
| `demo_soilgrids.tif` | recorte real do SoilGrids 2.0 (5 atributos × 3 profundidades × 4 estatísticas = 60 bandas, ≈ 240 KB), reamostrado por vizinho mais próximo para EPSG:4326 (0,0025°) e convertido para pH, g/kg e % |
| `propriedade_demo.geojson`, `.kml`, `propriedade_demo_shp.zip` | polígonos ilustrativos (fictícios) gerados por `scripts/make_sample_polygons.py` (o Shapefile está em SIRGAS 2000 / UTM 23S) |
| `invalido_gravata.geojson`, `invalido_coordenadas_utm.geojson`, `invalido_talhoes_sobrepostos.geojson` | casos sintéticos para testes de validação |

O modo demo só atende a região do recorte; fora dela a análise falha com a mensagem "polígono fora do recorte de amostra". Regeneração: `python scripts/build_sample_data.py` (requer rede) e `python scripts/make_sample_polygons.py`.

## 4. Instalação, execução e reprodução

Pré-requisitos: Python 3.11, Node.js e npm. Docker é opcional.

### 4.1 Instalação

```bash
make install                 # cria .venv, instala requirements-dev.txt e roda npm install em frontend/
cp .env.example .env         # TSI_MODE=demo
```

`requirements.lock.txt` registra as versões fixadas do ambiente de desenvolvimento.

### 4.2 Demonstração offline

```bash
make api                     # terminal 1: http://localhost:8000/docs
make web                     # terminal 2: http://localhost:5173
```

1. Abra `http://localhost:5173`; a faixa lateral indica "Modo demonstração · offline".
2. Selecione **Fazenda Demo (ilustrativa)** e execute a análise (a barra de progresso mostra as etapas; leva cerca de 1 s).
3. Alterne entre as camadas Declividade (classes), Elevação, Relevo sombreado e Orientação de encostas.
4. Selecione o **Talhão D (pequeno)** para ver o aviso de poucos pixels (16).
5. Em Solo, escolha *Mostrar camada de solo* → *Argila* → *Largura do intervalo 90%*; os pixels grandes são os de 250 m.

### 4.3 Importar e desenhar

- **Importar**: aceita `.geojson`, `.kml` e `.zip` (Shapefile com `.prj`). A tabela mostra cada feição como ok, reparada ou recusada, com os problemas; selecione qual é a propriedade e quais são talhões. Arquivos de teste em `sample_data/`: `propriedade_demo.kml`, `propriedade_demo_shp.zip` (UTM 23S, reprojetado), `invalido_gravata.geojson` (auto-interseção, reparada com aviso), `invalido_coordenadas_utm.geojson` (recusado) e `invalido_talhoes_sobrepostos.geojson` (avisos de sobreposição).
- **Desenhar**: marque vértices e conclua com duplo clique; com a propriedade selecionada, adicione talhões e edite vértices. A propriedade de demonstração é somente leitura (use *Duplicar para editar*). Após editar, execute a análise novamente: resultados antigos pertencem à geometria antiga.
- **Comparar e exportar**: a aba Comparar mostra Δ de terreno e solo e a leitura. O topo oferece PDF, DEM.tif, Declividade.tif, Curvas.geojson e Zonas.geojson (os GeoTIFF abrem no QGIS: EPSG:4326, `nodata = -9999`).

### 4.4 Modo live

Defina `TSI_MODE=live` em `.env` e reinicie a API. Requer acesso a `copernicus-dem-30m.s3.amazonaws.com` e `files.isric.org`. A primeira análise de uma área baixa a janela do DEM (cache em `data/cache/`) e 60 camadas do SoilGrids (5 atributos × 3 profundidades × 4 estatísticas). Se o SoilGrids estiver indisponível, a análise termina sem solo e exibe aviso; o relevo continua válido.

### 4.5 Docker Compose (PostGIS)

```bash
cp .env.example .env         # defina POSTGRES_PASSWORD
docker compose up --build    # http://localhost:8080
```

`python scripts/check_infra.py` valida a consistência do compose, dos arquivos referenciados e das variáveis. A execução dos contêineres e o armazenamento em PostGIS não possuem validação registrada neste repositório (ver seção 9).

### 4.6 Uso apenas como biblioteca

```python
import sys; sys.path.insert(0, "backend")
from pathlib import Path
from app.core.analysis import run_analysis
import json
gj = json.load(open("sample_data/propriedade_demo.geojson"))
prop = [f for f in gj["features"] if f["properties"]["kind"] == "property"][0]["geometry"]
res = run_analysis(prop, [], {}, Path("saida"), progress=lambda p, m: print(f"{p:.0%} {m}"), mode="demo")
print(res["zones"]["property"]["slope_pct"])
```

### 4.7 Alvos do Makefile

| Alvo | Ação |
|---|---|
| `make install` | venv, dependências Python e `npm install` |
| `make api` / `make web` | API (uvicorn, porta 8000) / frontend (Vite, porta 5173) |
| `make test` | `pytest tests -q`, `npm run typecheck`, `npm test` |
| `make test-net` | testes com rede (`TSI_RUN_NETWORK=1`) |
| `make e2e` | build do frontend e testes E2E (`TSI_RUN_E2E=1`, Playwright/Chromium) |
| `make notebooks` | `scripts/build_notebooks.py` (gera e executa os notebooks) |
| `make sample` | regenera dados de amostra e polígonos (requer rede) |
| `make openapi` | exporta `docs/openapi.json` |
| `make check` | `scripts/check_infra.py` |

### 4.8 Variáveis de ambiente (`.env.example`)

| Variável | Padrão | Descrição |
|---|---|---|
| `TSI_MODE` | `demo` | `demo` lê só de `sample_data/`; `live` baixa DEM e SoilGrids |
| `TSI_DATABASE_URL` | `sqlite:///./data/tsi.db` | sobrescrita pelo compose para PostGIS |
| `TSI_DATA_DIR`, `TSI_SAMPLE_DIR` | `./data`, `./sample_data` | diretórios de dados |
| `TSI_DEM_BASE_URL`, `TSI_SOILGRIDS_BASE_URL` | ver seção 3 | mude apenas para usar espelho próprio |
| `TSI_MAX_AREA_HA` | `20000` | limite de proteção de recursos |
| `TSI_MAX_UPLOAD_MB` | `20` | limite de upload |
| `TSI_JOB_WORKERS` | `2` | threads de jobs |
| `TSI_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | origens CORS |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | `tsi`, `troque-esta-senha`, `tsi` | usados pelo compose; troque a senha |

Versionado: `backend/`, `frontend/`, `scripts/`, notebooks, testes, `sample_data/`. Não versionado: `data/` (cache do modo live e SQLite em execução), `.env`, `node_modules/`.

## 5. Metodologia e pipeline

### 5.1 Datums, CRS e área

- **Armazenamento, API e DEM**: EPSG:4326 (WGS 84), ordem lon, lat.
- **Exibição**: EPSG:3857 apenas no mapa; nunca para medir (a área é inflada por 1/cos²φ, ≈ 17% a 22°S).
- **Medição**: SIRGAS 2000 / UTM (EPSG:31978–31985, zonas 18S–25S) no Brasil; WGS 84 / UTM (EPSG:326xx/327xx) fora dele. A zona é escolhida por `utm_epsg(lon, lat)`: zona = ⌊(lon+180)/6⌋+1; usa SIRGAS 2000 para lon entre −80° e −28° no hemisfério sul (zonas 18–25). Exemplos testados: (−46,78; −22,2) → EPSG:31983; (−51; −22) → 31982; (10; 45) → 32632.
- **Área**: primária em UTM; conferência geodésica com `pyproj.Geod` no elipsoide WGS 84. Distorção de escala UTM até ≈ 0,04% (erro de área ≈ 0,08% no pior caso). Na propriedade de demonstração: 332,86 ha (UTM) × 332,85 ha (geodésica), diferença de +0,003%. Propriedades com mais de 3° E–O geram o aviso `UTM_SPAN`.
- **WGS 84 × SIRGAS 2000**: diferenças horizontais da ordem de decímetros, muito abaixo da resolução de 30 m; a entrada permanece em WGS 84 e não há transformação de datum por grade.
- **Altura**: o DEM usa altura ortométrica (EGM2008). Uma altura elipsoidal de GNSS não é diretamente comparável (h ≈ H + N); a conversão exige um modelo geoidal (por exemplo MAPGEO/IBGE), não implementado.
- **Tamanho da célula**: dx(φ) e dy(φ) são calculados por linha com as séries padrão do elipsoide, em vez de assumir 30 m × 30 m.

### 5.2 Entrada de geometrias

| Situação | Comportamento |
|---|---|
| GeoJSON com coordenadas em UTM (metros) | recusado (`CRS_RANGE`): valores fora de ±180/±90 |
| GeoJSON com membro `crs` diferente de WGS 84 | recusado (RFC 7946 exige lon/lat WGS 84) |
| Shapefile em UTM com `.prj` | reprojetado para EPSG:4326, com nota exibida |
| Shapefile sem `.prj` | recusado (CRS não é inferido) |
| Ordem lat/lon trocada | não detectável com segurança se os valores couberem em ±90; conferir no mapa |
| KML | sempre WGS 84 (lon, lat, alt); altitude ignorada |
| Auto-interseção | reparada com aviso (`GEOM_REPAIRED`) ou recusada sem reparo (`GEOM_INVALID`) |
| Talhões sobrepostos ou fora da propriedade | avisos `PLOT_OVERLAP`, `PLOT_OUTSIDE` |

Segurança na leitura: ZIP com limite de descompactação e extração apenas dos componentes do `.shp` escolhido (evita *path traversal*); KML lido com entidades externas desligadas (teste de XXE).

### 5.3 Raster, máscara e estatísticas zonais

- A máscara usa `rasterio.features.geometry_mask` com `all_touched=False` (a célula entra se o centro está no polígono). Na propriedade de 332,86 ha: 3775 pixels × 0,0881 ha = 332,60 ha (razão 0,999).
- Polígonos pequenos: se nenhum centro cair dentro, usa-se `all_touched=True`; informa-se `n_pixels` e emite-se aviso com menos de 30 pixels (`quality_flags`). No talhão D (1,78 ha) restam 16 pixels (1,41 ha, razão 0,79).
- No SoilGrids (250 m, ≈ 6–7 ha por pixel), uma zona com menos de 1 pixel recebe o valor do pixel que a contém (`centroid_pixel`); zonas vizinhas podem ter valores idênticos, o que é avisado e marcado na comparação.
- Estatísticas com `rasterstats.zonal_stats`: mínimo, máximo, média, mediana, desvio, P5, P95; distribuição por classe de declividade; aspecto por oitantes, direção média circular e comprimento resultante; hipsometria por quantis.
- **Nodata**: o DEM não tem lacunas na amostra; NaN propaga para a declividade vizinha. No SoilGrids, camadas de valor são int16 com nodata −32768 e as de incerteza são uint16 com 65535; o nodata é sempre lido do próprio arquivo. Cerca de 9% dos pixels do recorte são nodata (máscara do ISRIC).
- **Posição do pixel**: a fonte marca `AREA_OR_POINT=Point`, mas os limites dos tiles estão deslocados em meio pixel de graus inteiros. Usa-se a geotransformação do arquivo como está; pode haver ambiguidade de até meio pixel (~15 m), não verificada.
- **Leitura remota**: o DEM é lido por janela (HTTP range) em COG, com margem de 3 pixels, e armazenado em `data/cache/` por hash da caixa envolvente.

### 5.4 Declividade e aspecto

Gradiente de Horn (3×3), com janela `a b c / d e f / g h i` (norte no topo):

```
dz/dx = ((c + 2f + i) − (a + 2d + g)) / (8·Δx)      (leste positivo)
dz/dy = ((a + 2b + c) − (g + 2h + i)) / (8·Δy)      (norte positivo)
declividade (°) = arctan( √( (dz/dx)² + (dz/dy)² ) )
declividade (%) = tan(declividade) × 100
aspecto = atan2(−dz/dx, −dz/dy) mod 360°            (azimute da descida, horário a partir do N)
```

Δx e Δy são em metros e variam por linha. O pixel central não entra no gradiente, por isso a declividade é anulada onde a própria elevação é NaN. Bordas ficam NaN.

- Aspecto é a direção de descida. Declividade < 1° é plano: aspecto indefinido (NaN); na propriedade de demonstração, 2,1% da área.
- A direção média usa média circular; o comprimento resultante R ∈ [0,1] indica a concentração das orientações.
- Classes de relevo (EMBRAPA/SiBCS, descritivas; não são limiares de mecanização, erosão ou tombamento):

| Classe | Declividade (%) | Demonstração |
|---|---|---|
| Plano | 0–3 | 5,7% |
| Suave ondulado | 3–8 | 24,8% |
| Ondulado | 8–20 | 60,6% |
| Forte ondulado | 20–45 | 8,8% |
| Montanhoso | 45–75 | 0,1% |
| Escarpado | > 75 | 0,0% |

- **Efeito da resolução** (DEM real da região de amostra, agregado por média em blocos):

| Resolução | Decl. média (%) | P95 (%) | Área ≥ 20% |
|---|---|---|---|
| 30 m | 14,16 | 31,07 | 18,4% |
| 60 m | 12,13 | 25,79 | 11,3% |
| 90 m | 10,74 | 22,68 | 7,5% |
| 150 m | 8,69 | 18,70 | 4,2% |
| 300 m | 5,95 | 13,83 | 1,4% |

A declividade de 30 m subestima a local e não é comparável à de um DEM de outra resolução.

- **Sensibilidade a ruído vertical** (ruído independente por pixel): média 14,16% → 14,19 (σ = 0,5 m) → 14,28 (1) → 14,62 (2) → 15,97% (σ = 4 m); a classe "plano" (< 3%) quase não muda. O erro real do DEM é espacialmente correlacionado e desconhecido; o teste dimensiona apenas a sensibilidade.

### 5.5 Curvas de nível

Marching squares (`contourpy`) com interpolação linear entre centros de células. As curvas são rotuladas `derivada_do_DEM_GLO30_DSM`, com aviso de interpolação na camada e no GeoJSON exportado.

A posição horizontal de uma curva é incerta em ≈ σᵥ / tan(β). Para σᵥ = 4 m e declividade P10/P50/P90 = 5,6 / 12,3 / 25,1%: 72 / 32 / 16 m.

| Intervalo pedido | Comportamento |
|---|---|
| < 5 m | recusado (HTTP 422) |
| 5 a < 10 m | aceito com aviso |
| ≥ 10 m | aceito |
| em branco | automático: o maior entre 10 m e um intervalo "redondo" que gera ≈ 10 curvas (10, 20, 25, 50, 100…) |

Na propriedade de demonstração (relevo de 80 m) o intervalo automático é 10 m.

### 5.6 Interpolação e reamostragem

| Onde | Método | Efeito |
|---|---|---|
| DEM → declividade | nenhuma (sem reamostragem) | não altera valores |
| SoilGrids (Interrupted Goode Homolosine → 4326) | vizinho mais próximo | não cria valores; desloca até meio pixel (~125 m) |
| Camadas PNG no MapLibre | `raster-resampling: nearest` | pixels visíveis, sem suavização |
| Curvas de nível | linear entre centros | ver 5.5 |

Não há krigagem nem suavização de solo.

### 5.7 Solo

- Intervalo de 90% por pixel é de **predição**, não intervalo de confiança da média da zona. Na agregação, a aplicação mostra a média dos Q0.05 e Q0.95 dos pixels (`pi90_note` no JSON).
- Valores na propriedade de demonstração (0–5 cm):

| Atributo | Média predita | Intervalo 90% (média dos pixels) | Largura média |
|---|---|---|---|
| Argila (%) | 37,8 | 5,8–79,9 | 74 |
| Carbono (g/kg) | 29,5 | 5,3–73,6 | 68 |
| pH | 5,3 | 4,3–6,7 | 2,4 |

- Variação espacial × incerteza (notebook 03): o desvio padrão espacial da média predita é ≈ 2 pontos de argila, contra largura de intervalo ≈ 71; a razão desvio ÷ largura tem mediana 0,036 nos 15 pares atributo × profundidade. Diferenças de cor entre pixels do mapa de solo estão muito abaixo da incerteza.
- Pixels do SoilGrids por zona na demonstração: propriedade (332,9 ha) 40; talhão A (108,0 ha) 11; B (90,4 ha) 12; C (117,4 ha) 14; D (1,8 ha) 1.
- Textura: a partir das médias preditas de areia, silte e argila, informa-se a classe textural USDA (12 classes). Na propriedade: *Franco argiloso* em 0–5, 5–15 e 15–30 cm (maioria dos pixels; ocorrem também *Franco argilo-arenoso* e *Argila arenosa*). Com os intervalos acima a classe real pode ser outra.

## 6. API

Base: `http://localhost:8000/api` (ou `/api` atrás do nginx). Swagger em `/docs`, ReDoc em `/redoc`; o esquema OpenAPI está versionado em [`openapi.json`](openapi.json) (gerado por `python scripts/export_openapi.py`).

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | status, modo (`demo`/`live`), banco |
| GET | `/sources` | metadados das fontes, unidades e limitações |
| POST | `/geometry/validate` | valida um GeoJSON; devolve problemas, métricas e geometria (reparada se `repair`) |
| POST | `/import` | multipart `file` (`.geojson`/`.kml`/`.zip` Shapefile): lê, reprojeta, valida cada feição |
| GET/POST | `/properties` | lista (filtros `q`, `min_area_ha`, `max_area_ha`, `has_analysis`) / cria propriedade com talhões |
| GET/PUT/DELETE | `/properties/{id}` | detalhe / atualiza / exclui (a propriedade demo é somente leitura) |
| POST | `/properties/{id}/analyses` | inicia job assíncrono: `{contour_interval_m?, soil}` → 202 `{analysis_id, job_id, status_url}` |
| GET | `/jobs/{id}` | `status` (`queued/running/done/failed`), `progress` 0–1, `stage`, `error` |
| GET | `/analyses/{id}` | resultados completos (JSON) |
| GET | `/analyses/{id}/layers/{layer}` | PNG RGBA (`elevation`, `hillshade`, `slope`, `aspect`, `soil:<attr>:<prof>:<mean\|pi>`); cabeçalho `X-Bounds` = `[oeste, sul, leste, norte]` |
| GET | `/analyses/{id}/contours` | curvas de nível (GeoJSON) |
| GET | `/analyses/{id}/compare?a=&b=` | compara duas zonas (`property` ou nome do talhão) |
| GET | `/analyses/{id}/export/{kind}` | `dem`, `slope`, `aspect` (GeoTIFF), `contours`, `geojson`, `report` (PDF), `results` (JSON) |

Códigos de erro: 409 (resultados pedidos antes do término), 413 (upload acima de `TSI_MAX_UPLOAD_MB`), 422 (geometria inválida/irreparável, CRS fora de faixa, formato não suportado, intervalo de curvas < 5 m), 403 (alterar/excluir a propriedade demo), 404 (recurso inexistente). Erros de geometria trazem `detail.issues[]` com `code`, `severity` e `message` (`CRS_RANGE`, `GEOM_INVALID`, `GEOM_REPAIRED`, `PLOT_OVERLAP`, `PLOT_OUTSIDE`, `AREA_HUGE`, `UTM_SPAN`).

Exemplo com curl:

```bash
API=http://localhost:8000/api
curl -s -X POST $API/properties -H 'content-type: application/json' \
  -d '{"name":"Minha área","geometry":{"type":"Polygon","coordinates":[[[-46.79,-22.21],[-46.78,-22.21],[-46.78,-22.20],[-46.79,-22.20],[-46.79,-22.21]]]}}'
curl -s -X POST $API/properties/<ID>/analyses -H 'content-type: application/json' -d '{"contour_interval_m":10,"soil":true}'
curl -s $API/jobs/<ANALYSIS_ID>
curl -sLo relatorio.pdf $API/analyses/<ANALYSIS_ID>/export/report
curl -sLo dem.tif       $API/analyses/<ANALYSIS_ID>/export/dem
```

Exemplo em Python:

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

Formato dos GeoTIFF exportados: EPSG:4326, `float32`, `nodata = -9999`, recortados à caixa envolvente e mascarados fora do perímetro. DEM em metros (EGM2008); declividade em graus; aspecto em graus (azimute da descida; −9999 = plano).

Segurança: não há autenticação. A aplicação é voltada a uso local ou de equipe; não a exponha à internet sem um proxy autenticado.

## 7. Interpretação dos resultados

Resultados de referência da propriedade de demonstração (332,86 ha, polígono fictício em Espírito Santo do Pinhal, SP):

| Indicador | Valor | Observação |
|---|---|---|
| Área | 332,9 ha (UTM) · 332,8 ha (geodésica) | concordância de 0,003% |
| Perímetro | 6,68 km | medido em UTM |
| Elevação | 794–874 m, média 834 m | altura do DSM (inclui copa), EGM2008 |
| Declividade média | 11,5% (P95 22,8%) | escala de 30 m |
| Aspecto dominante | Leste; plano 2,1% | todas as orientações presentes; usar R |
| Pixels | 3775 | poucos pixels geram aviso |

Talhões:

| Zona | Área (ha) | Elev. média | Decliv. média | Aspecto | Aviso |
|---|---|---|---|---|---|
| A (oeste) | 108,0 | 845 m | 13,3% | S | – |
| B (sul) | 90,4 | 828 m | 11,5% | L | – |
| C (norte) | 117,4 | 830 m | 10,0% | L | – |
| D (pequeno) | 1,8 | 826 m | 10,6% | SO | 16 pixels |

- Leitura correta da declividade por classe: "no DSM de 30 m, a maior parte da propriedade tem declividade entre 8 e 20%". Os percentuais por classe não indicam área mecanizável nem risco de tombamento.
- Diferenças entre médias de elevação de talhões são relativas e aproximadas: erros aleatórios diminuem na média, erros sistemáticos (vegetação, viés regional) não.
- A aba Comparar classifica cada atributo de solo como *diferença dentro da incerteza* (intervalos de 90% se sobrepõem), *valores idênticos* (as zonas caem no mesmo pixel de 250 m; sem informação para comparar) ou *intervalos não se sobrepõem* (única situação em que a aplicação sugere diferença, ainda como predição). Na demonstração, todas as comparações de solo A × B ficam em "dentro da incerteza".
- Médias de solo devem ser lidas sempre com o intervalo (argila 37,8% [5,8–79,9]).
- Para uso decisório, confirme com topografia (RTK/drone), amostragem de solo e profissional habilitado.

## 8. Testes e validação

### 8.1 Comandos

| Camada | Comando |
|---|---|
| Backend (unidade + API) | `pytest tests -q` |
| Backend com rede | `TSI_RUN_NETWORK=1 pytest tests -q` |
| Interface (E2E, Chromium) | `TSI_RUN_E2E=1 pytest tests/e2e -q` (após `cd frontend && npm run build`) |
| Frontend | `cd frontend && npm run typecheck && npm test` |
| Notebooks | `python scripts/build_notebooks.py` |
| Infraestrutura | `python scripts/check_infra.py` |

Resultado de referência registrado em 31/10/2026 (macOS, Python 3.11.9, Node 24): backend 63 testes passaram, 16 pulados (13 E2E, 2 `network`, 1 `postgis`); com rede, 65 passaram e 14 pulados; E2E 13 passaram, sem erros de console; frontend 5 testes; 3 notebooks executados sem erro. Esses números são o registro daquela execução, não resultado de CI.

### 8.2 Cobertura

- **Geometria** (`test_geometry.py`): escolha de UTM, área UTM × geodésica, centroide/bbox, auto-interseção reparada ou recusada, coordenadas UTM recusadas, Z ignorado, talhões sobrepostos/fora, limite operacional.
- **Importação** (`test_io.py`): GeoJSON, KML (com comentários e buracos), Shapefile ZIP reprojetado, ZIP sem `.prj`/sem `.shp`/incompleto, `crs` não-WGS84, XXE, formatos inválidos.
- **Terreno** (`test_terrain.py`): planos inclinados com declividade e aspecto analíticos, diagonal, plano horizontal, propagação de NaN, tamanho de célula, classes, aspecto circular, hipsometria monotônica, política de intervalo de curvas.
- **Zonal e solo** (`test_zonal_soil.py`): `rasterstats` × média por máscara, polígono menor que pixel, polígono fora do DEM, soma da textura ≈ 100%, Q05 ≤ Q50 ≤ Q95, nodata, classe USDA, URLs de tiles, DEM e SoilGrids ao vivo idênticos à amostra (`network`).
- **API** (`test_api_flow.py`): job com progresso monotônico, resultados com datum/resolução/limitações, avisos do talhão pequeno, comparação, exportações, PDF com ressalvas e fontes, camadas PNG, CRUD, importação com erros amigáveis, área fora da amostra.
- **Persistência** (`test_store.py`): ida e volta no SQLite e cascata; teste PostGIS (`postgis`, índice GiST, `ST_Intersects`) existe e é pulado sem PostGIS.
- **E2E** (`tests/e2e/test_ui_flows.py`): carregar, analisar com progresso, camadas e legenda, aviso do talhão pequeno, comparar, solo, fontes, filtros, importar KML e recusar UTM, desenhar polígono e salvar, editar vértices, baixar PDF, layout de celular. Gera as capturas em `docs/screenshots/`.

### 8.3 Validação científica (notebooks)

- `01_validacao_terreno`: erro de declividade 0,002% em planos exatos (1–100%, 8 aspectos), erro de aspecto ≤ 0,005°; paraboloides com erro máximo < 0,001°; efeito da resolução e do ruído vertical; incerteza horizontal das curvas. Valida a aritmética, não o DEM.
- `02_validacao_dem_real`: razão pixels × área 0,999 (propriedade) e 0,79 (talhão de 1,8 ha); correlação 0,92 entre sombreamento e aspecto; DEM ao vivo idêntico à amostra.
- `03_soilgrids_incerteza`: razão desvio espacial ÷ largura do intervalo, mediana 0,036; textura soma ≈ 100%; verificação da camada `uncertainty`.

### 8.4 Defeitos encontrados pelos testes e corrigidos

KML com comentário XML derrubava o parser; pixel sem dado no DEM recebia declividade válida; estilos de desenho do `mapbox-gl-draw` geravam erro de console no MapLibre (`line-dasharray`); 30 botões de camada de solo foram substituídos por seletores; afirmações de notebooks que contradiziam as saídas foram reescritas.

### 8.5 Fora do escopo de validação

Exatidão do DEM contra o terreno (requer GNSS/levantamento); PostGIS e Docker Compose; modo live em outras regiões, tiles que cruzam o meridiano de 180° e áreas sem tile público; carga, concorrência e autenticação; navegadores além do Chromium; acessibilidade além de rótulos ARIA básicos.

## 9. Limitações conhecidas

1. **DSM, não terreno**: copas e construções entram na elevação.
2. **~30 m**: sem microrrelevo, terraços e estradas internas; declividade subestimada (14,2% → 8,7% de 30 m a 150 m).
3. **Exatidão vertical < 4 m (LE90)** é a especificação, não erro medido; sem validação contra GNSS.
4. **Datum vertical EGM2008** (ortométrico): não comparável com altura elipsoidal sem N.
5. **Aquisição 2010–2015**: cortes, aterros e barragens posteriores não aparecem.
6. **Curvas de nível interpoladas**, com posição incerta em ~32 m (σᵥ = 4 m, declividade mediana).
7. **SoilGrids 250 m**: predição de modelo, intervalos de 90% muito largos; variação espacial interna ≪ intervalo.
8. **Talhões menores que um pixel** herdam o pixel (solo) ou poucos pixels (DEM); a aplicação avisa.
9. **Ambiguidade posicional de meio pixel (~15 m)** possível no DEM, não verificada.
10. **Corpos d'água** no DEM: tratamento do produto não verificado.
11. **Uma única zona UTM**: propriedades com mais de 3° E–O geram aviso.
12. **PostGIS e Docker Compose**: código e configuração presentes; sem validação de execução registrada (apenas `check_infra.py` e SQLite).
13. **Sem autenticação nem multiusuário.**
14. **Modo demo** restrito à região do recorte.

Fora de escopo por decisão de projeto: compactação, fertilidade real, necessidade de adubação, tráfego seguro, risco de tombamento, trajetórias de máquinas e uso das classes EMBRAPA como limiares operacionais.

Usos indevidos e riscos: planejar trajetória ou pulverização com o DSM (microdesníveis invisíveis; inseguro); afirmar que um talhão tem solo melhor que outro (diferença dentro da incerteza); recomendar adubação pelos mapas (SoilGrids não substitui análise de solo); comparar declividades de DEMs de resoluções diferentes; tratar curvas de nível como levantamento.

Desenvolvimentos possíveis: validação do DEM com GNSS/RTK; execução e teste de PostGIS/Compose e teste de carga; conversão ortométrica ↔ elipsoidal (MAPGEO/EGM2008); outras fontes de DEM (FABDEM, NASADEM, TOPODATA/INPE); tiles dinâmicos (COG/TiTiler); autenticação e multiusuário.

## 10. Licenças e atribuições

| Item | Licença / termos | Atribuição |
|---|---|---|
| Código | GPL-3.0 (`LICENSE`) | – |
| Copernicus DEM GLO-30 | Licença Copernicus (acesso gratuito; citar a fonte) | *Copernicus DEM © DLR e.V. 2010-2014 e © Airbus Defence and Space GmbH 2014-2018, fornecido sob COPERNICUS pela União Europeia e ESA; acessado via https://registry.opendata.aws/copernicus-dem* |
| SoilGrids 2.0 | CC BY 4.0 | citar o ISRIC e Poggio et al. (2021) (referência a conferir) |
| OpenStreetMap | ODbL | atribuição exibida no mapa quando ativado |

Os termos de redistribuição dos recortes do Copernicus DEM em `sample_data/` não foram revisados juridicamente; confirme a Licença Copernicus antes de redistribuir. A CC BY 4.0 do SoilGrids permite a redistribuição com atribuição. Detalhes por arquivo em [`../sample_data/ATTRIBUTION.md`](../sample_data/ATTRIBUTION.md).

## 11. Solução de problemas

| Sintoma | Causa provável e ação |
|---|---|
| Análise falha com "polígono fora do recorte de amostra" | o modo demo cobre só a região de Espírito Santo do Pinhal (SP); use `TSI_MODE=live` |
| Análise do modo live termina sem solo, com aviso | SoilGrids indisponível; o relevo permanece válido; tente novamente depois |
| HTTP 422 ao criar análise | intervalo de curvas < 5 m ou geometria inválida; veja `detail.issues[]` |
| HTTP 409 ao pedir resultados | a análise ainda não terminou; acompanhe `GET /jobs/{id}` |
| HTTP 413 no import | arquivo acima de `TSI_MAX_UPLOAD_MB` |
| GeoJSON recusado com `CRS_RANGE` | coordenadas em metros (UTM); converta para lon/lat WGS 84 |
| Shapefile recusado | falta `.prj` ou componente do `.shp` |
| Valores de solo idênticos entre talhões | as zonas estão no mesmo pixel de 250 m |
| Edição não altera resultados | execute a análise novamente após editar a geometria |
| Propriedade demo não pode ser alterada (403) | duplique-a para editar |
| `make api` não encontra `uvicorn` | rode `make install`; o venv `.venv` deve existir na raiz |
| Cache obsoleto no modo live | remova `data/cache/` |
