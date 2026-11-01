# 12 · Testes e validação

## Resumo (execução de 31/10/2026, macOS, Python 3.11.9, Node 24)
| Camada | Comando | Resultado |
|---|---|---|
| Backend (unidade + API) | `pytest tests -q` | **63 passaram, 16 pulados** (13 E2E, 2 `network`, 1 `postgis`) |
| Backend com rede | `TSI_RUN_NETWORK=1 pytest tests -q` | **65 passaram, 14 pulados** (13 E2E, 1 PostGIS) |
| Interface (E2E, Chromium) | `TSI_RUN_E2E=1 pytest tests/e2e -q` | **13 passaram** (3 execuções seguidas), 0 erros de console |
| Frontend | `npm run typecheck && npm test` | tipos OK; 5 testes |
| Notebooks | `python scripts/build_notebooks.py` | 3 notebooks executados sem erro |
| Infraestrutura | `python scripts/check_infra.py` | sintaxe/referências OK (**não executada**) |

## O que os testes cobrem
- **Geometria** (`test_geometry.py`): escolha de UTM, área UTM × geodésica, centroide/bbox, auto-interseção reparada com aviso e recusada sem reparo, coordenadas UTM em GeoJSON recusadas, Z ignorado, talhões sobrepostos/fora, limite operacional.
- **Importação** (`test_io.py`): GeoJSON, KML (com comentários e buracos), Shapefile ZIP em UTM reprojetado, ZIP sem `.prj`/sem `.shp`/incompleto, `crs` não-WGS84, XXE, formatos inválidos.
- **Terreno** (`test_terrain.py`): planos inclinados com declividade e aspecto **analíticos**, diagonal, plano horizontal (aspecto indefinido, *hillshade* = sen 45°), propagação de NaN, tamanho de célula, classes, aspecto circular, hipsometria monotônica, política de intervalo de curvas.
- **Zonal/solo** (`test_zonal_soil.py`): `rasterstats` × média por máscara, polígono menor que pixel, polígono fora do DEM, soma da textura ≈ 100%, Q05 ≤ Q50 ≤ Q95, nodata nunca vira valor, classe textural USDA, URLs de tiles, **DEM e SoilGrids ao vivo idênticos à amostra** (`network`).
- **API** (`test_api_flow.py`): job com progresso monotônico, resultados com datum/resolução/limitações, avisos do talhão pequeno, comparação, exportações (GeoTIFF abre em `rasterio`, recortado ao polígono), PDF com ressalvas e fontes, camadas PNG, CRUD, importação com erros amigáveis, área fora da amostra falha com mensagem (409 nos resultados).
- **Persistência** (`test_store.py`): ida e volta no SQLite e cascata; teste PostGIS (índice GiST, `ST_Intersects`) **pulado**.
- **E2E** (`tests/e2e`): carregar, analisar com progresso, camadas e legenda, aviso do talhão pequeno, comparar, solo, fontes, filtros, importar KML e recusar UTM, **desenhar um polígono com o mouse e salvar**, editar vértices, **baixar o PDF**, layout de celular sem rolagem horizontal.

## Bugs que os testes encontraram (e foram corrigidos)
1. **KML com comentário XML** derrubava o parser com `ValueError` (o iterador devolve nós de comentário).
2. **Pixel sem dado no DEM** recebia declividade válida (o centro do kernel de Horn não entra no gradiente).
3. **Estilos de desenho** do `mapbox-gl-draw` geravam erro de console no MapLibre (`line-dasharray`).
4. **Interface**: 30 botões de camada de solo → trocados por seletores; botões estourando o painel.
5. **Notebooks**: três afirmações minhas contradiziam os números (erro de planos, efeito do ruído, definição de `uncertainty`) e foram reescritas a partir das saídas.

## Validação científica (notebooks)
- `01_validacao_terreno`: erro de declividade **0,002%** em planos exatos; < 0,001° em paraboloides; efeito da resolução (14,2% → 8,7% de 30 m a 150 m) e do ruído vertical; incerteza horizontal das curvas.
- `02_validacao_dem_real`: razão pixels×área 0,999 (propriedade) e 0,79 (talhão de 1,8 ha); correlação 0,92 entre sombreamento e aspecto; DEM ao vivo idêntico à amostra.
- `03_soilgrids_incerteza`: desvio espacial ÷ largura do IC mediana 0,036; textura soma ≈ 100%; verificação da camada `uncertainty`.

## O que **não** foi validado
- **Exatidão do DEM contra o terreno** (precisa de GNSS/levantamento de campo).
- **PostGIS e Docker Compose** não foram executados (sem Docker nesta máquina); só o SQLite foi exercitado. O `GeomType` para PostGIS e o `test_postgis_roundtrip` existem, mas ficaram sem rodar.
- **Modo live** foi exercitado apenas para uma região (recorte e testes de rede); outras regiões, tiles que cruzam o meridiano de 180° e áreas sem tile público não foram testados.
- **Carga/concorrência** e **autenticação** (não há).
- **Navegadores** além do Chromium; **acessibilidade** além de rótulos ARIA básicos (sem auditoria).
