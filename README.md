# Quem paga o anúncio? — Monitor de propaganda política nas plataformas da Meta

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20006998.svg)](https://doi.org/10.5281/zenodo.20006998)

**Site:** https://quempagaoanuncio.github.io  
**Dataset:** https://doi.org/10.5281/zenodo.20006998  
**Licença dos dados:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)  
**Autor:** Pedro Maia · [pedrodsmaia.github.io](https://pedrodsmaia.github.io)  
**Atualização:** mensal (primeira semana de cada mês)

---

## Sobre

Monitor independente de anúncios políticos veiculados nas plataformas Facebook e Instagram (Meta). Os dados são coletados manualmente via [Meta Ad Library](https://www.facebook.com/ads/library/) e organizados para permitir análise de gastos, alcance e distribuição demográfica e regional dos anúncios.

## Candidatos monitorados

Pré-candidatos à Presidência da República com maior intenção de voto segundo a **Pesquisa Quaest de 15 de abril de 2026**, mais candidatos de outros partidos com presença relevante na disputa:

| Candidato | Partido |
|---|---|
| Lula | PT |
| Flávio Bolsonaro | PL |
| Ronaldo Caiado | PSD |
| Romeu Zema | Novo |
| Renan Santos | Missão |
| Aldo Rebelo | Democracia Cristã |
| Cabo Daciolo | Mobiliza |
| Augusto Cury | Avante |
| Hertz Dias | PSTU |
| Samara Martins | UP |
| Rui Costa Pimenta | PCO |
| Edmilson Costa | PCB |

**Coleta:** 3 downloads/dia via Meta Ad Library — ciclo mensal de 4 dias (3 candidatos/dia). Os resultados incluem tanto anúncios pagos pelo próprio candidato quanto anúncios de terceiros que mencionam o nome dele na Meta Ad Library.

## Cobertura temporal

Período de campanha: 16 de agosto a 20 de outubro de 2026 (1º e 2º turno).

## Estrutura dos dados

### `data/data.json`
JSON agregado que alimenta o dashboard. Contém:
- `stats` — totais gerais (nº de anúncios, gasto no teto e no ponto médio, impressões, plataformas)
- `charts.by_advertiser` — gasto, contagem e plataformas por anunciante (top 10)
- `charts.by_state` — gasto estimado e anunciante principal por estado
- `charts.demographics` — distribuição por faixa etária e gênero, ponderada por gasto
- `charts.adv_timeline` — evolução semanal de gasto por anunciante
- `top_advertisers` — ranking dos 20 maiores anunciantes
- `criativos_repetidos` — top 30 textos repetidos: quantos anúncios distintos carregam o mesmo texto, por página (proxy de repetição/impulsionamento do mesmo conteúdo)
- `ads` — lista dos 500 anúncios de maior gasto estimado

### Campos dos anúncios (`ads`)
| Campo | Descrição |
|---|---|
| `ad_id` | ID do anúncio na Meta Ad Library |
| `advertiser_name` | Nome da página anunciante |
| `ad_text` | Texto do anúncio |
| `publisher_platforms` | Plataformas (facebook, instagram) |
| `spend_min` / `spend_max` / `spend_mid` | Faixa de gasto estimado em BRL e seu **ponto médio** |
| `impressions_min` / `impressions_max` / `impressions_mid` | Faixa de impressões estimadas e seu **ponto médio** |
| `estimated_audience_min` / `estimated_audience_max` / `estimated_audience_mid` | Faixa do **público-alvo estimado** (potencial de segmentação) e seu ponto médio |
| `start_date` / `end_date` | Período de veiculação |
| `demographic_distribution` | Distribuição por idade e gênero |
| `delivery_by_region` | Distribuição por estado |

> **Nota metodológica.** Gasto, impressões e público-alvo vêm da Meta em **faixas** (mín.–máx.), não valores exatos. O campo `*_max` (teto) **superestima** sistematicamente; o `*_mid` (ponto médio da faixa) é a estimativa mais defensável. **Impressões não são alcance**: contam exibições (com repetição), não pessoas únicas — a Ad Library não publica alcance único nem frequência por pessoa. `estimated_audience_size` é o público-alvo *potencial* da segmentação, não o efetivamente atingido.

## Limitações

- Gasto, impressões e público-alvo são **estimativas em intervalo** (mínimo–máximo) fornecidas pela Meta, não valores exatos; use `*_mid` para a estimativa central.
- A coleta é manual, limitada a 3 downloads por dia por conta no Meta Ad Library.
- Os dados cobrem apenas anúncios **ativos ou encerrados** nas plataformas Facebook e Instagram.
- Anúncios sem texto ou sem dados de gasto estão incluídos no banco mas podem aparecer com campos vazios.

## Como citar

> Maia, Pedro. *Quem paga o anúncio? Monitor de propaganda política nas plataformas da Meta*. 2026. Disponível em: https://quempagaoanuncio.github.io

## Reprodução

```bash
# importar CSVs do Meta Ad Library
python3 src/import_csv.py arquivo1.csv arquivo2.csv

# gerar data.json atualizado
python3 src/export.py
```

## Fonte primária

Meta Ad Library — https://www.facebook.com/ads/library/
