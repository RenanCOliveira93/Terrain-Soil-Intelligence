# Terrain & Soil Intelligence

[Português](README.md) · [English](README.en.md)

Plataforma web para análise territorial de propriedades agrícolas: a partir de um perímetro desenhado ou importado (GeoJSON, KML, Shapefile ZIP), calcula área, perímetro, elevação, declividade, aspecto, hipsometria, curvas de nível e atributos de solo estimados, com mapas interativos, comparação de talhões, exportação (GeoTIFF/GeoJSON) e relatório PDF com metodologia, fontes e limitações.

![Declividade e indicadores](docs/screenshots/02_declividade_e_indicadores.png)

## Funcionalidades

- Desenho, edição e importação de polígonos, com validação de geometria e CRS (reparo com aviso, recusa de coordenadas UTM em GeoJSON, detecção de talhões sobrepostos).
- Área, perímetro, centroide e caixa envolvente em SIRGAS 2000 / UTM, com conferência geodésica no elipsoide.
- Copernicus DEM GLO-30 recortado ao polígono: elevação, declividade (gradiente de Horn), aspecto, hipsometria e curvas de nível com política de intervalo coerente com a resolução.
- SoilGrids 2.0 (pH, carbono orgânico, argila, silte, areia) com intervalo de predição de 90% por pixel.
- Estatísticas zonais por propriedade e talhão, com avisos de qualidade (poucos pixels, talhão menor que o pixel).
- Jobs assíncronos com progresso; modo demonstração offline com recortes reais versionados.
- Exportação de GeoTIFF (DEM, declividade, aspecto), GeoJSON e relatório PDF.

## Avisos de uso

- O Copernicus DEM GLO-30 é um DSM (inclui copas e construções) com célula de ~30 m. Não substitui levantamento topográfico e não serve para planejar trajetórias de máquinas.
- As curvas de nível são interpoladas do DSM, não medidas de campo.
- O SoilGrids é uma predição de modelo a 250 m com intervalos amplos (demonstração: argila 37,8% [5,8–79,9]); a aplicação não afirma diferenças de solo entre talhões.
- A aplicação não estima compactação, fertilidade, necessidade de adubação, risco de tráfego ou de tombamento.
- Os polígonos do modo demonstração são fictícios (sobre dados reais).

## Arquitetura

```
Frontend (React + TypeScript + MapLibre GL JS)
   └─ /api ─ Backend FastAPI ─ PostGIS (SQLite no modo demo)
                └─ Jobs assíncronos ─ Núcleo geoespacial (Shapely, GeoPandas, Rasterio, rasterstats)
                                        ├─ Copernicus DEM GLO-30 (COG, AWS Open Data)
                                        ├─ SoilGrids 2.0 (ISRIC)
                                        └─ sample_data/ (modo demo offline)
```

## Início rápido (modo demonstração, offline)

Requer Python 3.11 e Node.js.

```bash
make install                 # venv + dependências Python + npm install
cp .env.example .env         # TSI_MODE=demo
make api                     # terminal 1: http://localhost:8000/docs
make web                     # terminal 2: http://localhost:5173
```

Selecione **Fazenda Demo (ilustrativa)** e execute a análise. Para dados reais de qualquer local do Brasil (requer internet), defina `TSI_MODE=live`. A execução com Docker Compose (PostGIS) está descrita no [guia técnico](docs/GUIA_TECNICO.md#45-docker-compose-postgis).

## Estrutura do repositório

```
backend/app/      API FastAPI e núcleo geoespacial (core/)
frontend/src/     React + TypeScript + MapLibre
infra/            Dockerfiles, nginx, init.sql
tests/            unidade, API e e2e/ (Playwright)
sample_data/      recortes reais (DEM, SoilGrids), polígonos fictícios e arquivos inválidos de teste
notebooks/        validação do terreno, do DEM real e da incerteza do SoilGrids
scripts/          dados de amostra, notebooks, OpenAPI, verificação da infraestrutura
docs/             GUIA_TECNICO.md, openapi.json, screenshots/
```

## Testes

```bash
make test        # pytest + typecheck e testes do frontend
make test-net    # testes que acessam as fontes remotas
make e2e         # testes de interface (Playwright/Chromium)
```

Escopo, resultados de referência e itens fora da validação (exatidão do DEM contra o terreno, PostGIS) estão na seção 8 do [guia técnico](docs/GUIA_TECNICO.md#8-testes-e-validação).

## Dados e licenças

Dados: Copernicus DEM (Licença Copernicus, citar a fonte) e SoilGrids (CC BY 4.0). Os termos de redistribuição dos recortes do Copernicus não foram revisados juridicamente; veja [sample_data/ATTRIBUTION.md](sample_data/ATTRIBUTION.md).

## Documentação

[Guia técnico](docs/GUIA_TECNICO.md): arquitetura, fontes de dados, instalação e reprodução, metodologia, API, testes, limitações e licenças. Esquema OpenAPI em [docs/openapi.json](docs/openapi.json).

## Licença

Código sob GPL-3.0 (arquivo [LICENSE](LICENSE)).
