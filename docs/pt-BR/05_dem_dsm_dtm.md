# 05 · DEM, DSM e DTM

| Sigla | Significado | Contém vegetação e construções? |
|---|---|---|
| **DSM** | Modelo Digital de **Superfície** | **sim** (copas, telhados) |
| **DTM** | Modelo Digital de **Terreno** | não (chão nu) |
| **DEM** | termo genérico (pode ser DSM ou DTM) | depende do produto |

## O Copernicus DEM GLO-30 é um **DSM**
O registro do produto diz que ele representa "a superfície da Terra, incluindo edifícios, infraestrutura e vegetação". Em uma lavoura arbórea (café, citros, eucalipto) a altura medida inclui a **copa**. Num talhão com dossel de 3–4 m ao lado de um pasto, o DSM pode registrar um "degrau" que não existe no chão.

## O que o produto é (e não é)
| Item | Valor | Fonte |
|---|---|---|
| Resolução | 1 arco-segundo (~30 m; aqui ≈ 28,6 × 30,8 m) | registro AWS / medido |
| Horizontal | WGS 84 | EMD (secundária) |
| Vertical | EGM2008, ortométrica | catálogo GEE (secundária) |
| Exatidão vertical absoluta | **< 4 m (LE90)** — especificação | Copernicus Data Space |
| Exatidão horizontal absoluta | < 6 m (CE90) — especificação | Copernicus Data Space |
| Aquisição | 2010–2015 (TanDEM-X) | EMD (secundária) |
| Versão | Copernicus DEM 2021 (bucket AWS `copernicus-dem-30m`) | registro AWS |
| Licença | gratuita sob a Licença Copernicus; citar a fonte | registro AWS |

"Exatidão LE90" significa que 90% dos erros verticais são menores que 4 m **nas condições da especificação**; o erro local pode ser maior em encostas íngremes, floresta densa ou áreas urbanas, e **não medimos o erro desta região** (isso exigiria pontos GNSS/levantamento).

## O que um DSM de 30 m **não** serve para
- **Microdesníveis**, terraços, sulcos de erosão, estradas de 4 m de largura: abaixo da resolução.
- **Planejamento de trajetória de pulverizador/máquina**: exige levantamento topográfico/RTK de alta precisão.
- **Risco de tombamento ou tráfego seguro**: não é calculado pelo app, de propósito (ver `13_limitacoes_e_licencas.md`).
- **Obras de drenagem e terraceamento**: precisam de levantamento e projeto.

## O que ele serve para
Contexto regional: faixa de altitude, orientação dominante das encostas, distribuição de declividade em escala de **dezenas de metros**, comparação **relativa** entre talhões grandes e cobertura de grandes áreas sem custo.

## Água e oceano
Oceano não tem tiles (assume-se altura 0). Corpos d'água continentais podem ter tratamento específico no produto; **não verificamos isso** — evite interpretar áreas de lagos/represas.
