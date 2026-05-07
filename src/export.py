import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime

DB_PATH = "data/ads.db"
OUTPUT_PATH = "data/data.json"

TOP_ADV = 10
TOP_ADV_TIMELINE = 10

# Atores políticos não-oficiais: mídia política, movimentos, fã-clubes, etc.
# Pagam anúncios sobre política mas não são candidatos nem partidos registrados.
# São excluídos do gráfico "Gasto mensal — candidatos e partidos" mas continuam
# visíveis na aba Análise com o label "não oficial".
NAO_OFICIAIS = {
    "Revista Oeste",           # veículo de mídia conservador
    "Bárbara - Te Atualizei",  # criadora de conteúdo político
    "Revista Valete",          # veículo de mídia
    "Corrida Acorda Brasil #ForaLula",  # movimento político
    "FÃO do Bolsonaro",        # fã-clube
    "Frente LIVRE",            # movimento político
    "O Contra-Fluxo",          # mídia/conteúdo
    "Blog do Lúcio Sorge",     # blog político
    "Diário do Comércio",      # veículo de mídia
    "Ativa Notícia",           # veículo de mídia
    "Leonel De Esquerda - Você É De Esquerda E Não Sabe",  # criador de conteúdo
    "Grupo Pró-Guapé",         # movimento local
}

# Perfis genéricos ou técnicos — excluídos por não serem atores políticos
NAO_POLITICOS = {
    "Eleja.se",                # plataforma eleitoral
    "Brasil",                  # perfil genérico, provável erro de classificação
    "Doutoraraissasoaresoficial",  # não identificado
}

# União dos dois para filtrar o gráfico mensal
PROPRIO_BLOCKLIST = NAO_OFICIAIS | NAO_POLITICOS

STATE_NORM = {
    "são paulo (state)": "São Paulo", "são paulo": "São Paulo",
    "minas gerais": "Minas Gerais", "rio de janeiro": "Rio de Janeiro",
    "rio de janeiro (state)": "Rio de Janeiro",
    "bahia": "Bahia", "paraná": "Paraná", "rio grande do sul": "Rio Grande do Sul",
    "pernambuco": "Pernambuco", "ceará": "Ceará", "pará": "Pará",
    "santa catarina": "Santa Catarina", "goiás": "Goiás", "maranhão": "Maranhão",
    "amazonas": "Amazonas", "espírito santo": "Espírito Santo",
    "mato grosso": "Mato Grosso", "mato grosso do sul": "Mato Grosso do Sul",
    "rio grande do norte": "Rio Grande do Norte", "alagoas": "Alagoas",
    "piauí": "Piauí", "distrito federal": "Distrito Federal",
    "federal district": "Distrito Federal",
    "paraíba": "Paraíba", "sergipe": "Sergipe", "rondônia": "Rondônia",
    "tocantins": "Tocantins", "acre": "Acre", "amapá": "Amapá",
    "roraima": "Roraima",
}


def parse_regions(raw):
    if not raw:
        return []
    try:
        items = json.loads("[" + raw.replace("}{", "},{") + "]")
        result = []
        for item in items:
            name = item.get("region", "").lower()
            norm = STATE_NORM.get(name, item.get("region", ""))
            result.append({"region": norm, "percentage": item.get("percentage", 0)})
        return result
    except Exception:
        return []


def export():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT source, ad_id, advertiser_name, ad_text,
               spend_min, spend_max, impressions_min, impressions_max,
               currency, start_date, end_date,
               publisher_platforms, demographic_distribution, delivery_by_region,
               collected_at, tema, tom, tipo_anuncio
        FROM ads
        ORDER BY spend_max DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    adv_spend    = defaultdict(float)
    adv_count    = defaultdict(int)
    adv_platform = defaultdict(lambda: defaultdict(float))
    adv_timeline = defaultdict(lambda: defaultdict(float))
    timeline_all = defaultdict(float)
    state_spend  = defaultdict(float)
    state_count  = defaultdict(int)
    state_adv    = defaultdict(lambda: defaultdict(float))  # state -> adv -> spend
    demo_weighted = defaultdict(lambda: defaultdict(float))
    tema_count   = defaultdict(int)
    tom_count    = defaultdict(int)
    tipo_count   = defaultdict(int)
    adv_tema     = defaultdict(lambda: defaultdict(int))   # adv -> tema -> count
    monthly_proprio     = defaultdict(lambda: defaultdict(float))  # adv -> month -> spend
    monthly_all_proprio = defaultdict(float)                       # month -> total spend
    # detalhe por anunciante próprio
    proprio_spend   = defaultdict(float)
    proprio_count   = defaultdict(int)
    proprio_monthly = defaultdict(lambda: defaultdict(float))   # adv -> month -> spend
    proprio_regions = defaultdict(lambda: defaultdict(float))   # adv -> region -> spend
    proprio_temas   = defaultdict(lambda: defaultdict(int))     # adv -> tema -> count

    for row in rows:
        adv   = row["advertiser_name"] or "Desconhecido"
        spend = row["spend_max"] or 0.0

        adv_spend[adv]  += spend
        adv_count[adv]  += 1

        platforms = [p.strip() for p in (row["publisher_platforms"] or "").split(",") if p.strip()]
        for p in platforms:
            adv_platform[adv][p] += spend / max(len(platforms), 1)

        for reg in parse_regions(row["delivery_by_region"]):
            st = reg["region"]
            w  = spend * reg["percentage"]
            state_spend[st] += w
            state_count[st] += 1
            state_adv[st][adv] += w

        demo_raw = row.get("demographic_distribution") or ""
        if demo_raw:
            try:
                items = json.loads("[" + demo_raw.replace("}{", "},{") + "]")
                for item in items:
                    age    = item.get("age", "").strip()
                    gender = item.get("gender", "").strip()
                    pct    = float(item.get("percentage", 0))
                    if age and gender:
                        demo_weighted[age][gender] += spend * pct
            except Exception:
                pass

        date_str = (row["start_date"] or "")[:10]
        if date_str and len(date_str) == 10:
            try:
                from datetime import date
                d = date.fromisoformat(date_str)
                week = d.strftime("%Y-W%V")
                adv_timeline[adv][week] += spend
                timeline_all[week]      += spend
            except Exception:
                pass

        if row["tema"]:
            tema_count[row["tema"]] += 1
            adv_tema[adv][row["tema"]] += 1
        if row["tom"]:
            tom_count[row["tom"]] += 1
        if row["tipo_anuncio"]:
            tipo_count[row["tipo_anuncio"]] += 1

        # Gasto mensal e detalhe — apenas anúncios classificados como próprios
        if row["tipo_anuncio"] == "proprio":
            proprio_spend[adv] += spend
            proprio_count[adv] += 1

            date_str2 = (row["start_date"] or "")[:10]
            if date_str2 and len(date_str2) == 10:
                try:
                    from datetime import date as _date
                    d2 = _date.fromisoformat(date_str2)
                    month = d2.strftime("%Y-%m")
                    # timeline mensal só conta perfis políticos confirmados
                    if adv not in PROPRIO_BLOCKLIST:
                        monthly_proprio[adv][month] += spend
                        monthly_all_proprio[month]  += spend
                    proprio_monthly[adv][month] += spend
                except Exception:
                    pass

            for reg in parse_regions(row["delivery_by_region"]):
                proprio_regions[adv][reg["region"]] += spend * reg["percentage"]

            if row["tema"]:
                proprio_temas[adv][row["tema"]] += 1

    # Timeline mensal — apenas próprios, top 10 por gasto proprio
    proprio_spend_total = {
        adv: sum(monthly_proprio[adv].values())
        for adv in monthly_proprio
    }
    top_proprio_advs = sorted(proprio_spend_total, key=lambda x: -proprio_spend_total[x])[:TOP_ADV]
    all_months = sorted(set(m for adv in monthly_proprio for m in monthly_proprio[adv]))
    monthly_timeline_out = []
    for m in all_months:
        entry = {"month": m}
        covered = 0.0
        for adv in top_proprio_advs:
            v = round(monthly_proprio[adv].get(m, 0), 2)
            entry[adv] = v
            covered += v
        entry["Outros"] = round(monthly_all_proprio.get(m, 0) - covered, 2)
        monthly_timeline_out.append(entry)

    # Timeline top 10 + Outros
    top_advs    = sorted(adv_spend, key=lambda x: -adv_spend[x])[:TOP_ADV]
    top_adv_tl  = sorted(adv_spend, key=lambda x: -adv_spend[x])[:TOP_ADV_TIMELINE]
    all_weeks   = sorted(set(wk for adv in adv_timeline for wk in adv_timeline[adv]))
    adv_timeline_out = []
    for wk in all_weeks:
        entry = {"week": wk}
        covered = 0.0
        for adv in top_adv_tl:
            v = round(adv_timeline[adv].get(wk, 0), 2)
            entry[adv] = v
            covered += v
        entry["Outros"] = round(timeline_all.get(wk, 0) - covered, 2)
        adv_timeline_out.append(entry)

    # Demográfico (só female/male, ponderado por gasto)
    age_order = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
    total_demo = sum(
        v for age in demo_weighted.values()
        for g, v in age.items() if g in ("female", "male")
    )
    demographics_out = {}
    if total_demo > 0:
        for age in age_order:
            if age in demo_weighted:
                demographics_out[age] = {
                    g: round(demo_weighted[age].get(g, 0) / total_demo * 100, 2)
                    for g in ("female", "male")
                }

    stats_total = sum(adv_spend.values())

    output = {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "stats": {
            "total_ads": len(rows),
            "total_spend_max_brl": round(stats_total, 2),
            "by_platform": {},
        },
        "charts": {
            "by_state": {
                st: {
                    "spend": round(state_spend[st], 2),
                    "count": state_count[st],
                    "top_advertiser": max(state_adv[st], key=state_adv[st].get) if state_adv[st] else "",
                }
                for st in sorted(state_spend, key=lambda x: -state_spend[x])
            },
            "by_advertiser": {
                adv: {
                    "spend": round(adv_spend[adv], 2),
                    "count": adv_count[adv],
                    "platforms": {k: round(v, 2) for k, v in adv_platform[adv].items()},
                    "temas": dict(adv_tema[adv]),
                }
                for adv in top_advs
            },
            "by_tema": dict(sorted(tema_count.items(), key=lambda x: -x[1])),
            "by_tom":  dict(sorted(tom_count.items(),  key=lambda x: -x[1])),
            "by_tipo": dict(sorted(tipo_count.items(), key=lambda x: -x[1])),
            "adv_timeline": adv_timeline_out,
            "timeline_advertisers": top_adv_tl + ["Outros"],
            "monthly_timeline_proprio": monthly_timeline_out,
            "monthly_timeline_advertisers": top_proprio_advs + ["Outros"],
            "proprio_advertisers": {
                adv: {
                    "spend": round(proprio_spend[adv], 2),
                    "count": proprio_count[adv],
                    "tipo_perfil": (
                        "nao_oficial" if adv in NAO_OFICIAIS else
                        "nao_politico" if adv in NAO_POLITICOS else
                        "oficial"
                    ),
                    "monthly": {
                        m: round(v, 2)
                        for m, v in sorted(proprio_monthly[adv].items())
                    },
                    "top_regions": sorted(
                        [{"region": r, "spend": round(v, 2)}
                         for r, v in proprio_regions[adv].items()],
                        key=lambda x: -x["spend"]
                    )[:8],
                    "temas": dict(
                        sorted(proprio_temas[adv].items(), key=lambda x: -x[1])
                    ),
                }
                for adv in sorted(proprio_spend, key=lambda x: -proprio_spend[x])
            },
            "demographics": demographics_out,
        },
        "top_advertisers": [
            {"advertiser_name": adv, "total_spend": round(adv_spend[adv], 2), "ad_count": adv_count[adv]}
            for adv in sorted(adv_spend, key=lambda x: -adv_spend[x])[:20]
        ],
        "ads": rows[:500],
    }

    plat_spend = defaultdict(float)
    plat_count = defaultdict(int)
    for row in rows:
        for p in [x.strip() for x in (row["publisher_platforms"] or "").split(",") if x.strip()]:
            plat_spend[p] += row["spend_max"] or 0
            plat_count[p] += 1
    output["stats"]["by_platform"] = {
        p: {"count": plat_count[p], "spend": round(plat_spend[p], 2)}
        for p in sorted(plat_spend, key=lambda x: -plat_spend[x])
    }

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"[Export] {len(rows)} ads → {OUTPUT_PATH}")


if __name__ == "__main__":
    export()
