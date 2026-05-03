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

Candidatos com maior intenção de voto segundo a **Pesquisa Quaest de 15 de abril de 2026**:

- Lula
- Flávio Bolsonaro
- Romeu Zema
- Ronaldo Caiado
- Augusto Cury
- Renan Santos

## Cobertura temporal

Janeiro de 2026 — atualizado mensalmente.

## Estrutura dos dados

### `data/data.json`
JSON agregado que alimenta o dashboard. Contém:
- `stats` — totais gerais (número de anúncios, gasto estimado, plataformas)
- `charts.by_advertiser` — gasto, contagem e plataformas por anunciante (top 10)
- `charts.by_state` — gasto estimado e anunciante principal por estado
- `charts.demographics` — distribuição por faixa etária e gênero, ponderada por gasto
- `charts.adv_timeline` — evolução semanal de gasto por anunciante
- `top_advertisers` — ranking dos 20 maiores anunciantes
- `ads` — lista dos 500 anúncios de maior gasto estimado

### Campos dos anúncios (`ads`)
| Campo | Descrição |
|---|---|
| `ad_id` | ID do anúncio na Meta Ad Library |
| `advertiser_name` | Nome da página anunciante |
| `ad_text` | Texto do anúncio |
| `publisher_platforms` | Plataformas (facebook, instagram) |
| `spend_min` / `spend_max` | Intervalo de gasto estimado em BRL |
| `impressions_min` / `impressions_max` | Intervalo de impressões estimado |
| `start_date` / `end_date` | Período de veiculação |
| `demographic_distribution` | Distribuição por idade e gênero |
| `delivery_by_region` | Distribuição por estado |

## Limitações

- Gasto e impressões são **estimativas em intervalo** (mínimo–máximo) fornecidas pela Meta, não valores exatos.
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
