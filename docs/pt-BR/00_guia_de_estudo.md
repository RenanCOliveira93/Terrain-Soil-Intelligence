# 00 · Guia de estudo

Sugestão de ordem. Cada etapa diz o que você deve conseguir explicar ao final.

| # | Material | Você deve conseguir explicar… |
|---|---|---|
| 1 | `README.md` | o que o app faz, o que **não** faz e o que ficou sem testar |
| 2 | `05_dem_dsm_dtm.md` | por que o GLO-30 é um DSM e por que 30 m não serve para planejar trajetória de máquinas |
| 3 | `02_geodesia.md` | altura ortométrica × elipsoidal, EGM2008, tamanho real da célula |
| 4 | `03_crs_e_projecoes.md` | por que medir área em UTM e nunca em graus/Web Mercator |
| 5 | `04_raster_vetor.md` | quais pixels pertencem a um polígono e o que muda em talhões pequenos |
| 6 | `06_declividade_e_aspecto.md` + notebook 01 | Horn, convenção do aspecto, efeito da resolução |
| 7 | `07_interpolacao_e_curvas_de_nivel.md` | por que curvas são interpolação e como o intervalo é escolhido |
| 8 | `08_propriedades_do_solo.md` + notebook 03 | predição × medição, intervalo de predição × de confiança |
| 9 | `09_interpretacao_de_resultados.md` | como ler cada indicador e os erros comuns |
| 10 | `01_arquitetura.md`, `10_api.md` | fluxo do job assíncrono, rotas, formatos de exportação |
| 11 | `11_tutoriais.md` | operar a interface, importar, comparar, exportar |
| 12 | `12_testes_e_validacao.md`, `13_limitacoes_e_licencas.md` | o que foi validado, o que não foi e as licenças |

## Perguntas de revisão
1. Por que um ponto de GNSS com altura elipsoidal de 850 m não é "850 m" no DEM?
2. Por que a declividade média cai quando o DEM é agregado de 30 m para 150 m?
3. O que significa "intervalo de predição de 90%" e por que ele não é o intervalo de confiança da média da zona?
4. Por que o app recusa curvas de nível a cada 2 m?
5. Em que caso a aba Comparar diz "valores idênticos"?
6. Que informações o app se recusa a produzir e por quê?
