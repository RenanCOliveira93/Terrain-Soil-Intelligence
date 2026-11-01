# 01 · Arquitetura

## Visão geral
```mermaid
flowchart LR
    U[Usuário] --> FE[Frontend<br/>React + TypeScript + MapLibre GL JS]
    FE -- "/api (JSON, PNG, GeoTIFF, PDF)" --> API[Backend FastAPI]
    API --> JOBS[Jobs assíncronos<br/>ThreadPoolExecutor]
    API --> DB[(PostGIS<br/>ou SQLite no demo)]
    JOBS --> CORE[Núcleo geoespacial<br/>Shapely · GeoPandas · Rasterio · rasterstats]
    CORE -- "janela COG (HTTP range)" --> AWS[(Copernicus DEM GLO-30<br/>AWS Open Data)]
    CORE -- "VRT/COG" --> ISRIC[(SoilGrids 2.0<br/>files.isric.org)]
    CORE -. "modo demo" .-> SAMPLE[(sample_data/<br/>recortes reais offline)]
    JOBS --> FS[(data/analyses/&lt;id&gt;/<br/>GeoTIFF · GeoJSON · PNG · PDF)]
```

## Componentes
| Pasta | Conteúdo |
|---|---|
| `backend/app/main.py` | rotas FastAPI, validação de entrada, exportações |
| `backend/app/core/geometry.py` | validação, escolha de UTM, área/perímetro/centroide/bbox, talhões |
| `backend/app/core/io.py` | GeoJSON, KML (lxml seguro), Shapefile ZIP |
| `backend/app/core/dem.py` | tiles do Copernicus (COG remoto), cache, modo demo |
| `backend/app/core/terrain.py` | Horn, aspecto, hipsometria, *hillshade*, classes |
| `backend/app/core/contours.py` | curvas de nível e política de intervalo |
| `backend/app/core/soil.py` | SoilGrids, conversões, textura USDA |
| `backend/app/core/zonal.py` | estatísticas zonais com avisos de qualidade |
| `backend/app/core/analysis.py` | orquestra a análise e grava os artefatos |
| `backend/app/core/render.py` | PNG das camadas e legendas |
| `backend/app/core/report.py` | PDF |
| `backend/app/store.py` | SQLAlchemy (PostGIS/SQLite) · `jobs.py` jobs |
| `frontend/src` | `App.tsx` + `components/` (mapa, painéis, gráficos SVG, diálogos) |
| `infra/` | Dockerfiles, nginx, `init.sql` |

## Fluxo de uma análise (job assíncrono)
```mermaid
sequenceDiagram
    participant UI as Frontend
    participant API as FastAPI
    participant J as Job (thread)
    participant S as Fontes (DEM, SoilGrids)
    UI->>API: POST /properties/{id}/analyses
    API-->>UI: 202 {analysis_id}
    API->>J: submit
    loop a cada 300 ms
        UI->>API: GET /jobs/{id}
        API-->>UI: {status, progress, stage}
    end
    J->>J: valida geometrias (3%)
    J->>S: lê janela do DEM (10%)
    J->>J: declividade, aspecto, zonais (35–50%)
    J->>J: curvas de nível (60%)
    J->>S: lê camadas do SoilGrids (68%)
    J->>J: zonais do solo (85%)
    J->>J: GeoTIFF, PNG, JSON, PDF (90–100%)
    UI->>API: GET /analyses/{id} (+ camadas PNG)
```
O progresso é gravado na tabela `analyses` (`status`, `progress`, `stage`), portanto qualquer réplica da API enxerga o estado. Se uma etapa **opcional** (solo) falha, a análise termina com **aviso explícito**; se uma etapa essencial (DEM) falha, o job vira `failed` com a mensagem.

## Modelo de dados
```mermaid
erDiagram
    PROPERTIES ||--o{ PLOTS : tem
    PROPERTIES ||--o{ ANALYSES : tem
    PROPERTIES { string id PK
      string name
      geometry geom "MULTIPOLYGON 4326 (GiST no PostGIS)"
      float area_ha
      string is_demo }
    PLOTS { string id PK
      string property_id FK
      string name
      geometry geom
      float area_ha }
    ANALYSES { string id PK
      string property_id FK
      string status
      float progress
      string stage
      json params
      json summary
      string mode }
```
Os rasters e os resultados detalhados ficam em `data/analyses/<id>/` (não no banco): `results.json`, `dem_clip.tif`, `slope_deg.tif`, `aspect_deg.tif`, `contours.geojson`, `property.geojson`, `layers.npz`, `soil.npz`, `relatorio.pdf`.

**PostGIS × SQLite:** o tipo `GeomType` grava `geometry(MULTIPOLYGON, 4326)` no PostgreSQL (índice espacial GiST criado pelo GeoAlchemy2) e GeoJSON em texto no SQLite. O código do PostGIS **não foi executado** nesta máquina (veja `12_testes_e_validacao.md`).

## Decisões de projeto
| Decisão | Motivo |
|---|---|
| Não reprojetar o DEM; dx/dy por latitude | evita interpolar a elevação antes de derivar declividade |
| Medir área em UTM e conferir no elipsoide | rigor + autoverificação |
| Camadas como PNG + `image` source no MapLibre | leve, funciona offline, fácil legenda; não é tile pyramid |
| `ThreadPoolExecutor` em vez de Celery | análise de uma propriedade leva segundos; menos peças. Se a carga crescer: fila externa |
| Solo opcional e com falha isolada | SoilGrids pode estar fora do ar (a REST estava em 503) |
| Avisos de qualidade no resultado (`quality_flags`) | números sem aviso de representatividade enganam |
| Faixas **fixas** nas legendas de solo | autoescala faria diferenças ínfimas parecerem grandes |
| Mapa de cores `cividis` para elevação | `terrain` tem degrau de cor que parece uma borda no relevo |
