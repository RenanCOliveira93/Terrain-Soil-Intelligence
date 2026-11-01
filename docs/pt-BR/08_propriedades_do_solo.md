# 08 · Propriedades do solo (SoilGrids 2.0)

## 1. O que é o SoilGrids
Mapas globais de propriedades do solo a **250 m**, produzidos pelo ISRIC com **Quantile Random Forest** sobre perfis do banco WoSIS e covariáveis ambientais (clima, relevo, imagens). Não são medições do seu solo: são **predições de um modelo**. Licença **CC BY 4.0** (atribuição). O ISRIC informa que a incerteza é dada pelo **intervalo de predição de 90%** (limites Q0.05 e Q0.95) por pixel. Uma fonte secundária cita que os modelos explicam entre 30% e 70% da variação (não confirmado na documentação oficial, que estava fora do ar).

## 2. O que o app expõe
| Atributo | Código | Unidade mapeada | Unidade exibida | Conversão |
|---|---|---|---|---|
| pH em água | `phh2o` | pH × 10 | pH | ÷ 10 |
| Carbono orgânico do solo | `soc` | dg/kg | g/kg | ÷ 10 |
| Argila | `clay` | g/kg | % (g/100 g) | ÷ 10 |
| Silte | `silt` | g/kg | % | ÷ 10 |
| Areia | `sand` | g/kg | % | ÷ 10 |

Profundidades (cm): 0–5, 5–15, 15–30, 30–60, 60–100, 100–200. A **amostra offline** traz as três primeiras. Estatísticas por camada: média, Q0.05, Q0.5 e Q0.95.

### Como verificamos as unidades (a tabela oficial estava indisponível)
A documentação oficial do ISRIC (`docs.isric.org`) respondeu HTTP 502 e a API REST respondeu 503 durante a construção. Por isso conferimos **nos dados**:
- areia + silte + argila (0–5 cm) somam **99,9–100,1** por pixel → fator ÷ 10 correto para a textura (notebook 03);
- pH médio ≈ 5,3 e carbono ≈ 30,8 g/kg (0–5 cm): valores plausíveis para solo tropical sob lavoura/pastagem;
- uma fonte secundária (pacote `soilDB`) aplica o mesmo divisor.
Isso é evidência forte, **não** a confirmação oficial: confirme na tabela do ISRIC antes de uso crítico.

## 3. Incerteza: o que ela diz e o que não diz
O intervalo de 90% é **por pixel** e é um intervalo de **predição**, não um intervalo de confiança da média da área. Ao agregar uma zona, o app mostra a média dos Q0.05 e Q0.95 dos pixels (`pi90_note` no JSON); isso **não** é o intervalo da média da zona.

Valores reais na propriedade de demonstração (0–5 cm):

| Atributo | Média predita | Intervalo 90% (média dos pixels) | Largura média |
|---|---|---|---|
| Argila (%) | 37,8 | 5,8–79,9 | 74 |
| Carbono (g/kg) | 29,5 | 5,3–73,6 | 68 |
| pH | 5,3 | 4,3–6,7 | 2,4 |

Ou seja: para argila, o modelo diz "entre ~6% e ~80%". **Esse intervalo cobre texturas muito diferentes.**

### Variação espacial × incerteza (notebook 03)
Dentro da propriedade, o desvio padrão espacial da **média** predita é de ≈ 2 pontos de argila, enquanto a largura do intervalo é ≈ 71. A razão (desvio ÷ largura) tem **mediana 0,036** nos 15 atributo×profundidade. Conclusão operacional: **as diferenças de cor entre pixels do mapa de solo estão muito abaixo da incerteza**, então o app não afirma que um talhão tem solo "diferente" de outro (a aba Comparar diz "diferença dentro da incerteza").

### A camada `uncertainty` do ISRIC (não usada)
Comparamos a camada com os quantis nos mesmos 68 pixels (argila 0–5 cm): ela vale ≈ **10 × (Q0.95 − Q0.05) / Q0.50** (razão mediana 9,98; correlação de Pearson 0,955; valores brutos 20–24, inteiros). Isso é **consistente** com a descrição de fonte secundária ((Q0.95−Q0.05)/Q0.50), mas **a definição e o fator 10 não estão confirmados** em documentação oficial. Como os quantis dão a mesma informação diretamente e sem fator, o app usa Q0.05/Q0.95.

## 4. Resolução e "talhão menor que o pixel"
Um pixel de 250 m cobre ≈ 6–7 ha. Na demonstração:

| Zona | Área (ha) | Pixels do SoilGrids |
|---|---|---|
| Propriedade | 332,9 | 40 |
| Talhão A | 108,0 | 11 |
| Talhão B | 90,4 | 12 |
| Talhão C | 117,4 | 14 |
| Talhão D | 1,8 | 1 |

O talhão D é menor que um pixel: o valor é **do pixel** e não uma estatística da zona. O app avisa. Reamostrar o SoilGrids para 30 m (bilinear/cúbico) daria um mapa "bonito" e **falso**; por isso só usamos vizinho mais próximo.

## 5. Textura: classe USDA
A partir das **médias preditas** de areia, silte e argila o app informa a classe textural USDA (12 classes). Na propriedade: *Franco argiloso* em 0–5, 5–15 e 15–30 cm (maioria dos pixels; também há *Franco argilo-arenoso* e *Argila arenosa*). Com os intervalos acima, a classe real pode ser outra; trate como **ilustração**.

## 6. O que **não** se deduz destes dados
- **Fertilidade, necessidade de calagem ou adubação**: exigem análise de solo da área, calibração e agrônomo.
- **Compactação, infiltração, drenagem**: não vêm do SoilGrids.
- **Diferença entre talhões**: dentro da incerteza, não é afirmável.
O app não calcula nenhum desses indicadores, e um teste automatizado garante que o resultado não contenha expressões como "recomendação de adubação".

## 7. Acesso
Lemos os VRT/COG em `files.isric.org/soilgrids/latest/data/` (servidor WebDAV do ISRIC) com `rasterio` + `WarpedVRT`. O acesso foi verificado em 31/10/2026; a REST (`rest.isric.org`) estava em 503, razão de não depender dela. A amostra offline (`sample_data/demo_soilgrids.tif`, 60 bandas) foi gerada pelo mesmo código e um teste (`-m network`) confere que a leitura ao vivo reproduz a amostra pixel a pixel.
