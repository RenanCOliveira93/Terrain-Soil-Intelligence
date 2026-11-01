# 09 · Como interpretar os resultados

Este capítulo usa a **propriedade de demonstração** (332,86 ha, polígono ilustrativo) como exemplo. Os números vêm da execução real do app sobre dados reais; a propriedade em si é fictícia.

## 1. Painel de indicadores
| Indicador | Valor na demonstração | Como ler |
|---|---|---|
| Área | 332,9 ha (UTM) · 332,8 ha (geodésica) | as duas concordam em 0,003% |
| Perímetro | 6,68 km | medido em UTM |
| Elevação | 794–874 m, média 834 m | **altura do DSM** (inclui copa), EGM2008 |
| Declividade média | 11,5% (P95 22,8%) | escala de **30 m**, subestima a local |
| Aspecto dominante | Leste (L), plano 2,1% | mas veja a dispersão abaixo |
| Pixels | 3775 | base estatística; poucos pixels → aviso |

### Declividade por classe
60,6% da área está na classe *Ondulado* (8–20%), 24,8% em *Suave ondulado*, 8,8% em *Forte ondulado*. Leitura correta: "**no DSM de 30 m**, a maior parte da propriedade tem declividade entre 8 e 20%". Leitura **incorreta**: "60,6% é mecanizável" ou "8,8% corre risco de tombamento" (não calculamos nem validamos isso).

### Aspecto
Dominante *L*, mas a rosa mostra todas as orientações (a propriedade é uma colina recortada por vales). Use o **comprimento resultante** (R) do JSON: R perto de 0 = orientações dispersas; perto de 1 = uma só. "Dominante" sem R pode enganar.

### Hipsometria
Curva da fração de área acima de cada cota. Uma curva reta indica distribuição uniforme de altitudes; curvas côncavas/convexas indicam platôs ou áreas baixas extensas.

## 2. Talhões
| Zona | Área (ha) | Elev. média | Decliv. média | Aspecto | Aviso |
|---|---|---|---|---|---|
| A (oeste) | 108,0 | 845 m | 13,3% | S | — |
| B (sul) | 90,4 | 828 m | 11,5% | L | — |
| C (norte) | 117,4 | 830 m | 10,0% | L | — |
| D (pequeno) | 1,8 | 826 m | 10,6% | SO | **16 pixels** |

"A é 16 m mais alto que B" é uma diferença de **médias de DSM**; o erro vertical especificado é < 4 m (LE90) por pixel e, na média de ~1000 pixels, erros aleatórios se reduzem, mas **erros sistemáticos** (vegetação, viés regional) não. Trate como diferença **relativa e aproximada**.

## 3. Comparação de zonas
A aba **Comparar** lista Δ de terreno e solo e uma "leitura":
- *diferença dentro da incerteza* → os intervalos de 90% se sobrepõem; não há evidência de diferença;
- *valores idênticos* → as duas zonas caem no mesmo pixel de 250 m; **não há informação para comparar**;
- *intervalos não se sobrepõem* → única situação em que o app sugere diferença (ainda é predição).
Na demonstração, **todas** as comparações de solo A×B caem em "dentro da incerteza".

## 4. Solo
Leia **sempre** a média **com** o intervalo. Argila 37,8% [5,8–79,9] não é "37,8%": é "37,8% como melhor palpite de um modelo cujo intervalo de 90% vai de 6 a 80%". Veja `08_propriedades_do_solo.md`.

## 5. Erros comuns de interpretação
| Erro | Por que está errado |
|---|---|
| "O DEM mostra o relevo do chão" | é DSM: inclui copas |
| "A curva de nível de 10 m é medida" | é interpolada de pixels de 30 m |
| "O talhão X tem 2 pontos a mais de argila" | diferença ≪ largura do intervalo |
| "O pixel é preciso a 30 m" | o erro horizontal especificado é < 6 m, mas a resolução efetiva é pior; e 1 pixel não é um ponto |
| "Declividade 12% → pode passar trator" | decisão operacional exige levantamento e validação |
| "Média de elevação da propriedade = altitude da sede" | média espacial de DSM ≠ ponto GNSS |
| "Mesmo valor de solo nos talhões → solo homogêneo" | é o mesmo pixel |

## 6. Conferência com a realidade
O app **não** foi validado contra levantamento de campo. Para uso decisório, confirme com topografia (RTK/drone), amostragem de solo e um profissional habilitado.
