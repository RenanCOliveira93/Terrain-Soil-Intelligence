# 13 · Limitações, dependências externas e licenças

## 1. Estado das dependências externas (verificado em 31/10/2026)
| Item | Estado | Observação |
|---|---|---|
| Copernicus DEM GLO-30 (AWS S3, COG) | ✅ funcionando | tile lido remotamente; recorte idêntico ao versionado |
| SoilGrids via `files.isric.org` (VRT/COG) | ✅ funcionando | usado no modo live e para gerar a amostra |
| SoilGrids API REST (`rest.isric.org`) | ❌ HTTP 503 | **não usada**; o COG dá os mesmos dados |
| Documentação do ISRIC (`docs.isric.org`) | ❌ HTTP 502 | unidades e `uncertainty` verificadas **nos dados** (não na tabela oficial) |
| Copernicus DEM Product Handbook | ⚠ só índice | datum/exatidão vêm de fontes secundárias (Copernicus Data Space, GEE, EMD) |
| OpenStreetMap (mapa base opcional) | ⚠ online | desligado por padrão; não usado em testes |
| PostGIS / Docker Compose | ⚠ **não executados** | sem Docker nesta máquina; sintaxe validada por `check_infra.py` |

## 2. Limitações científicas
1. **DSM, não terreno**: copas e construções entram na elevação.
2. **~30 m**: sem microrrelevo, terraços, estradas internas; declividade subestimada (14,2% → 8,7% ao passar de 30 m para 150 m).
3. **Exatidão vertical < 4 m (LE90)** é a **especificação**, não o erro medido aqui; **não validamos contra GNSS**.
4. **Datum vertical EGM2008** (ortométrico): não comparável com altura elipsoidal sem N.
5. **Aquisição 2010–2015**: mudanças posteriores (cortes, aterros, barragens) não aparecem.
6. **Curvas de nível interpoladas**; posição incerta em ~32 m (σᵥ = 4 m, declividade mediana).
7. **SoilGrids 250 m**, predição de modelo; intervalos de 90% muito largos (argila 6–80%); variação espacial dentro da propriedade ≪ intervalo.
8. **Talhões menores que um pixel** herdam o pixel (solo) ou poucos pixels (DEM); o app avisa.
9. **Ambiguidade posicional possível de meio pixel (~15 m)** no DEM (`AREA_OR_POINT=Point` na fonte), não verificada.
10. **Corpos d'água** no DEM: tratamento do produto não verificado.
11. **Uma zona UTM**: propriedades > 3° E–O geram aviso.

## 3. O que o app **não** faz, de propósito
Não estima **compactação**, **fertilidade real**, **necessidade de adubação**, **risco seguro de tráfego** nem **risco de tombamento**; não gera trajetórias para máquinas; não usa as classes EMBRAPA como limiares operacionais. Esses temas exigem dados de campo, calibração local e profissional habilitado. Um teste automatizado impede que o resultado da análise contenha esses indicadores.

## 4. Modo demonstração: dados reais, polígonos fictícios
- `sample_data/demo_dem_glo30.tif`: **recorte real** do Copernicus DEM GLO-30 (≈ 620 KB, 433×433 px, 12 km, região de Espírito Santo do Pinhal, SP).
- `sample_data/demo_soilgrids.tif`: **recorte real** do SoilGrids 2.0 (60 bandas, ≈ 240 KB).
- `propriedade_demo.*`: polígonos **ilustrativos** gerados por `scripts/make_sample_polygons.py`. **Não são uma propriedade real.**
- `invalido_*.geojson`: casos de teste sintéticos.
O modo demo só atende essa região; fora dela o erro é explícito.

## 5. Licenças e atribuição
| Dado | Licença / termos | O que fazer |
|---|---|---|
| Copernicus DEM GLO-30 | "disponível gratuitamente ao público sob os termos da Licença" (registro AWS) | citar: *Copernicus DEM © DLR e.V. 2010-2014 e © Airbus Defence and Space GmbH 2014-2018, fornecido sob COPERNICUS pela União Europeia e ESA; acessado via registry.opendata.aws/copernicus-dem* |
| SoilGrids 2.0 | **CC BY 4.0** (README do ISRIC) | citar o ISRIC e Poggio et al. (2021) *(referência de memória, conferir)* |
| OpenStreetMap | ODbL | atribuição exibida no mapa quando ativado |
| Código deste projeto | **não definida** | escolha uma licença conforme a política da organização |

**Redistribuição dos recortes em `sample_data/`:** a licença CC BY 4.0 do SoilGrids permite. Para o Copernicus DEM, **não revisamos juridicamente** os termos de redistribuição de recortes; antes de publicar o repositório fora da organização, confirme a Licença Copernicus. Veja `sample_data/ATTRIBUTION.md`.

## 6. Riscos de uso indevido
| Uso | Risco |
|---|---|
| Planejar trajetória/pulverização com o DSM | microdesníveis invisíveis; **inseguro** |
| "Talhão A tem solo melhor que B" | diferença dentro da incerteza |
| Recomendar adubação pelos mapas | sem base: SoilGrids ≠ análise de solo |
| Comparar declividades de DEMs de resoluções diferentes | números incomparáveis |
| Tratar curvas como levantamento | são interpolações |

## 7. Trabalhos futuros
1. Validar o DEM contra pontos GNSS/RTK de uma propriedade real.
2. Executar e testar PostGIS/Docker Compose; teste de carga.
3. Conversão de altura ortométrica ↔ elipsoidal com o MAPGEO/EGM2008.
4. Outras fontes de DEM (FABDEM, NASADEM, TOPODATA/INPE) para comparação.
5. Tiles dinâmicos (COG/TiTiler) para áreas muito grandes.
6. Autenticação e multiusuário.
