"""
Coleta anúncios políticos pela Meta Ad Library API (endpoint ads_archive) e
grava CSVs no MESMO schema do download manual do site — compatíveis, sem
alteração, com src/import_csv.py e src/export.py.

Dois modos:
  --candidates "Lula" "Flavio Bolsonaro" ...   (busca por TERMO no texto do anúncio;
                                                traz também anúncios de terceiros — ALTO volume)
  --page-ids 123 456 ...                        (busca por PÁGINA; só anúncios pagos por
                                                aquelas páginas — "quem paga" — baixo volume)

Estratégia anti-limite:
  - Paginação por cursor + fatiamento por data (ad_delivery_date_min/max) para não
    estourar o teto de ~2.000 do download manual.
  - Gravação INCREMENTAL: o CSV de cada alvo é reescrito ao fim de CADA fatia, então
    uma falha (token expirado / rate limit) NÃO perde o que já foi baixado.
  - Backoff exponencial no rate limit (#613/#4/#17/429); em token expirado (#190)
    salva o parcial e encerra com dica de retomada.

Token: lido de META_ADLIBRARY_TOKEN (ou META_ACCESS_TOKEN) no .env — nunca impresso.

Depois:
  python3 src/import_csv.py raw/<pasta>/*.csv
  python3 src/analyze.py
  python3 src/export.py
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import date, datetime, timedelta

import requests

GRAPH_VERSION = "v21.0"
ENDPOINT = f"https://graph.facebook.com/{GRAPH_VERSION}/ads_archive"

API_FIELDS = (
    "id,page_id,page_name,ad_creation_time,ad_delivery_start_time,"
    "ad_delivery_stop_time,bylines,ad_creative_bodies,ad_creative_link_titles,"
    "ad_creative_link_captions,ad_creative_link_descriptions,impressions,spend,"
    "currency,demographic_distribution,delivery_by_region,publisher_platforms,"
    "estimated_audience_size,languages"
)

CSV_HEADER = [
    "ad_archive_id", "page_id", "page_name", "ad_creation_time",
    "ad_delivery_start_time", "ad_delivery_stop_time", "byline",
    "ad_creative_bodies", "ad_creative_link_titles", "ad_creative_link_captions",
    "ad_creative_link_descriptions", "impressions", "spend", "currency",
    "demographic_distribution", "delivery_by_region", "publisher_platforms",
    "estimated_audience_size", "languages",
]

CANDIDATOS_PADRAO = [
    "Lula", "Flavio Bolsonaro", "Ronaldo Caiado", "Romeu Zema",
    "Renan Santos", "Aldo Rebelo", "Cabo Daciolo", "Augusto Cury",
    "Hertz Dias", "Samara Martins", "Rui Costa Pimenta", "Edmilson Costa",
]


class TokenExpired(Exception):
    pass


class RateLimitExceeded(Exception):
    pass


def ettra_minutes(resp):
    """Lê o header x-business-use-case-usage e devolve estimated_time_to_regain_access
    (minutos até liberar), ou None. É o sinal real de cooldown da Meta."""
    raw = resp.headers.get("x-business-use-case-usage") or resp.headers.get("x-app-usage")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        vals = []
        for entries in (data.values() if isinstance(data, dict) else []):
            for e in (entries if isinstance(entries, list) else [entries]):
                v = e.get("estimated_time_to_regain_access") if isinstance(e, dict) else None
                if v:
                    vals.append(int(v))
        return max(vals) if vals else None
    except Exception:
        return None


# ---------- .env / token ----------

def load_env():
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in [".env", os.path.join(here, "..", ".env")]:
        if os.path.exists(candidate):
            with open(candidate) as f:
                for line in f:
                    line = line.strip()
                    if line and "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            break


def get_token():
    load_env()
    for name in ("META_ADLIBRARY_TOKEN", "META_ACCESS_TOKEN"):
        tok = os.environ.get(name, "").strip().strip('"').strip("'")
        if tok and tok != "COLE_SEU_TOKEN_AQUI":
            return tok
    print("[Erro] token não encontrado/placeholder. Defina META_ADLIBRARY_TOKEN no .env.")
    sys.exit(1)


# ---------- serialização p/ o formato do CSV do site ----------

def bound_str(obj):
    if not isinstance(obj, dict):
        return ""
    lo, hi = obj.get("lower_bound", ""), obj.get("upper_bound", "")
    return "" if lo == "" and hi == "" else f"lower_bound: {lo}, upper_bound: {hi}"


def join_list(v, sep=","):
    return sep.join(str(x) for x in v) if isinstance(v, list) else (v or "")


def join_text(v):
    return "\n".join(str(x) for x in v) if isinstance(v, list) else (v or "")


def _pct(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def serialize_demo(lst):
    if not isinstance(lst, list) or not lst:
        return ""
    return ",".join(
        json.dumps({"age": d.get("age", ""), "gender": d.get("gender", ""),
                    "percentage": _pct(d.get("percentage", 0))}, ensure_ascii=True)
        for d in lst
    )


def serialize_region(lst):
    if not isinstance(lst, list) or not lst:
        return ""
    return ",".join(
        json.dumps({"region": d.get("region", ""),
                    "percentage": _pct(d.get("percentage", 0))}, ensure_ascii=True)
        for d in lst
    )


def row_to_csv(ad):
    return {
        "ad_archive_id": ad.get("id", ""),
        "page_id": ad.get("page_id", ""),
        "page_name": ad.get("page_name", ""),
        "ad_creation_time": ad.get("ad_creation_time", ""),
        "ad_delivery_start_time": ad.get("ad_delivery_start_time", ""),
        "ad_delivery_stop_time": ad.get("ad_delivery_stop_time", ""),
        "byline": join_text(ad.get("bylines", "")),
        "ad_creative_bodies": join_text(ad.get("ad_creative_bodies", "")),
        "ad_creative_link_titles": join_text(ad.get("ad_creative_link_titles", "")),
        "ad_creative_link_captions": join_text(ad.get("ad_creative_link_captions", "")),
        "ad_creative_link_descriptions": join_text(ad.get("ad_creative_link_descriptions", "")),
        "impressions": bound_str(ad.get("impressions")),
        "spend": bound_str(ad.get("spend")),
        "currency": ad.get("currency", "BRL"),
        "demographic_distribution": serialize_demo(ad.get("demographic_distribution")),
        "delivery_by_region": serialize_region(ad.get("delivery_by_region")),
        "publisher_platforms": join_list(ad.get("publisher_platforms", "")),
        "estimated_audience_size": bound_str(ad.get("estimated_audience_size")),
        "languages": join_list(ad.get("languages", "")),
    }


def write_csv(path, rows_by_id):
    """Reescreve o CSV com todas as linhas acumuladas (gravação incremental)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        for row in rows_by_id.values():
            w.writerow(row)
    os.replace(tmp, path)


def load_csv_ids(path):
    """Carrega um CSV já existente (retomada) -> {ad_id: row}."""
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            aid = row.get("ad_archive_id")
            if aid:
                out[aid] = row
    return out


def load_progress(outdir):
    p = os.path.join(outdir, "_progress.json")
    if os.path.exists(p):
        try:
            return json.load(open(p))
        except Exception:
            return {}
    return {}


def save_progress(outdir, prog):
    p = os.path.join(outdir, "_progress.json")
    tmp = p + ".tmp"
    json.dump(prog, open(tmp, "w"))
    os.replace(tmp, p)


# ---------- coleta ----------

def daterange_slices(dmin, dmax, slice_days):
    cur = dmin
    while cur <= dmax:
        end = min(cur + timedelta(days=slice_days - 1), dmax)
        yield cur, end
        cur = end + timedelta(days=1)


def fetch_slice(session, token, mode_key, term, dmin, dmax, limit, pause):
    """Pagina uma fatia (alvo + janela). Levanta TokenExpired/RateLimitExceeded."""
    params = {
        mode_key: term if mode_key == "search_terms" else f"['{term}']",
        "ad_reached_countries": "['BR']",
        "ad_type": "POLITICAL_AND_ISSUE_ADS",
        "ad_active_status": "ALL",
        "ad_delivery_date_min": dmin.isoformat(),
        "ad_delivery_date_max": dmax.isoformat(),
        "fields": API_FIELDS,
        "limit": limit,
        "access_token": token,
    }
    ads, url, first = [], ENDPOINT, True
    backoff, max_backoff, strikes, max_strikes = 30, 600, 0, 12
    while True:
        try:
            r = session.get(url, params=params if first else None, timeout=60)
        except requests.RequestException as e:
            # não imprime `e` inteiro: a mensagem inclui a URL com o access_token
            print(f"      [rede] {type(e).__name__} — retry em 5s")
            time.sleep(5)
            continue

        if r.status_code == 200:
            payload = r.json()
            batch = payload.get("data", [])
            ads.extend(batch)
            nxt = payload.get("paging", {}).get("next")
            if not nxt or not batch:
                return ads
            url, first = nxt, False
            backoff, strikes = 30, 0
            time.sleep(pause)
            continue

        # erro
        try:
            err = r.json().get("error", {})
        except Exception:
            err = {"message": r.text[:150]}
        code, msg = err.get("code"), err.get("message", "")
        if code == 190:
            raise TokenExpired(msg)
        if code in (4, 17, 613, 32) or r.status_code == 429:
            wait_min = ettra_minutes(r)
            # Espera throttles curtos (até 30 min); só desiste se a Meta estimar
            # uma espera LONGA (cooldown de verdade), pra não martelar nesse caso.
            if wait_min and wait_min > 30:
                raise RateLimitExceeded(
                    f"cota bloqueada — Meta estima ~{wait_min} min "
                    f"(estimated_time_to_regain_access) até liberar. Re-rode depois disso.")
            strikes += 1
            if strikes > max_strikes:
                raise RateLimitExceeded(f"{msg} (após {strikes} tentativas)")
            if wait_min is not None:
                # usa a estimativa da Meta (limite de ritmo curto) em vez de backoff cego
                wait = max(wait_min * 60 + 15, 30)
                print(f"      [rate limit] regain~{wait_min}min — aguardando {wait}s ({strikes}/{max_strikes})")
            else:
                wait = backoff
                print(f"      [rate limit] {msg} — aguardando {wait}s ({strikes}/{max_strikes})")
                backoff = min(backoff * 2, max_backoff)
            time.sleep(wait)
            continue
        print(f"      [API erro {r.status_code}] code={code} {msg} — pulando fatia")
        return ads


def main():
    ap = argparse.ArgumentParser(description="Coleta Meta Ad Library -> CSVs do pipeline")
    ap.add_argument("--date-min", required=True)
    ap.add_argument("--date-max", required=True)
    ap.add_argument("--slice-days", type=int, default=3)
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--pause", type=float, default=1.5)
    ap.add_argument("--candidates", nargs="*", default=None, help="termos de busca (texto)")
    ap.add_argument("--page-ids", nargs="*", default=None, help="IDs de páginas (só anúncios da página)")
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    try:
        dmin, dmax = date.fromisoformat(args.date_min), date.fromisoformat(args.date_max)
    except ValueError:
        print("[Erro] datas devem ser AAAA-MM-DD"); sys.exit(1)
    if dmin > dmax:
        print("[Erro] date-min depois de date-max"); sys.exit(1)

    token = get_token()
    if args.page_ids:
        mode_key, targets = "search_page_ids", args.page_ids
    else:
        mode_key = "search_terms"
        targets = args.candidates if args.candidates else CANDIDATOS_PADRAO
    outdir = args.outdir or os.path.join("raw", datetime.now().strftime("%Y%m%d-%H%M"))
    os.makedirs(outdir, exist_ok=True)

    slices = list(daterange_slices(dmin, dmax, args.slice_days))
    print(f"[Coleta] modo={mode_key} · {len(targets)} alvo(s) × {len(slices)} fatia(s) "
          f"de {args.slice_days}d ({dmin}…{dmax}) → {outdir}")

    session = requests.Session()
    prog = load_progress(outdir)  # retomada: fatias já concluídas por alvo
    total = 0
    for term in targets:
        safe = str(term).lower().replace(" ", "_").replace("/", "-")
        path = os.path.join(outdir, f"{safe}.csv")
        seen = load_csv_ids(path)          # recarrega o que já foi salvo
        done = set(prog.get(safe, []))     # fatias já concluídas
        if seen:
            print(f"  {str(term)[:22]:22} (retomando: {len(seen)} já no CSV, "
                  f"{len(done)}/{len(slices)} fatias prontas)")
        try:
            for (s, e) in slices:
                skey = f"{s.isoformat()}_{e.isoformat()}"
                if skey in done:
                    continue
                ads = fetch_slice(session, token, mode_key, term, s, e, args.limit, args.pause)
                for ad in ads:
                    aid = ad.get("id")
                    if aid and aid not in seen:
                        seen[aid] = row_to_csv(ad)
                write_csv(path, seen)  # grava incrementalmente
                done.add(skey)
                prog[safe] = sorted(done)
                save_progress(outdir, prog)
                print(f"  {str(term)[:22]:22} {s}..{e}: +{len(ads):6} (únicos: {len(seen)})")
                time.sleep(args.pause)
        except TokenExpired as ex:
            write_csv(path, seen)
            print(f"\n[PARADO] token expirou: {ex}")
            print(f"  Parcial salvo: {path} ({len(seen)} anúncios). Gere token longo e re-rode "
                  f"(use --candidates/--page-ids só dos alvos restantes).")
            sys.exit(2)
        except RateLimitExceeded as ex:
            write_csv(path, seen)
            print(f"\n[PARADO] rate limit persistente: {ex}")
            print(f"  Parcial salvo: {path} ({len(seen)} anúncios). Espere e re-rode dos restantes.")
            sys.exit(3)
        total += len(seen)
        print(f"  → {path} ({len(seen)} anúncios)")

    print(f"\n[Coleta] concluída: {total} linhas em {outdir}")
    print("Próximos passos:")
    print(f"  python3 src/import_csv.py {outdir}/*.csv")
    print("  python3 src/analyze.py && python3 src/export.py")


if __name__ == "__main__":
    main()
