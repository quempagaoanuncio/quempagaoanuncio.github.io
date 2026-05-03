"""
Uso:
    python3 src/import_csv.py arquivo1.csv arquivo2.csv ...

Só insere anúncios novos (ad_id ainda não existente no banco).
Ao final, exibe quantos foram adicionados e quantos já existiam.
"""

import csv
import sqlite3
import os
import re
import sys
from datetime import datetime

DB_PATH = "data/ads.db"


def parse_spend(s):
    if not s:
        return 0.0, 0.0
    nums = re.findall(r"\d+", str(s).replace(",", "").replace(".", ""))
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    if len(nums) == 1:
        v = float(nums[0])
        return v, v
    return 0.0, 0.0


def parse_impressions(s):
    if not s:
        return 0, 0
    nums = re.findall(r"\d+", str(s).replace(",", ""))
    if len(nums) >= 2:
        return int(nums[0]), int(nums[1])
    if len(nums) == 1:
        v = int(nums[0])
        return v, v
    return 0, 0


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source          TEXT NOT NULL,
            ad_id           TEXT NOT NULL,
            advertiser_name TEXT,
            advertiser_id   TEXT,
            ad_text         TEXT DEFAULT '',
            spend_min       REAL DEFAULT 0,
            spend_max       REAL DEFAULT 0,
            impressions_min INTEGER DEFAULT 0,
            impressions_max INTEGER DEFAULT 0,
            currency        TEXT DEFAULT 'BRL',
            start_date      TEXT,
            end_date        TEXT,
            region          TEXT DEFAULT 'BR',
            search_term     TEXT,
            collected_at    TEXT NOT NULL,
            publisher_platforms       TEXT DEFAULT '',
            demographic_distribution  TEXT DEFAULT '',
            delivery_by_region        TEXT DEFAULT '',
            UNIQUE(source, ad_id)
        )
    """)
    conn.commit()


def import_file(conn, path, now):
    inserted = 0
    skipped  = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ad_id = row.get("ad_archive_id", "").strip()
            if not ad_id:
                continue

            advertiser    = row.get("page_name", "").strip()
            advertiser_id = row.get("page_id", "").strip()
            ad_text       = row.get("ad_creative_bodies", "").strip()
            currency      = row.get("currency", "BRL").strip() or "BRL"
            start_date    = row.get("ad_delivery_start_time", "").strip()
            end_date      = row.get("ad_delivery_stop_time", "").strip()
            platforms     = row.get("publisher_platforms", "").strip()
            demo          = row.get("demographic_distribution", "").strip()
            regions       = row.get("delivery_by_region", "").strip()

            spend_min, spend_max = parse_spend(row.get("spend", ""))
            imp_min, imp_max     = parse_impressions(row.get("impressions", ""))

            cur = conn.execute("""
                INSERT OR IGNORE INTO ads
                (source, ad_id, advertiser_name, advertiser_id, ad_text,
                 spend_min, spend_max, impressions_min, impressions_max,
                 currency, start_date, end_date, publisher_platforms,
                 demographic_distribution, delivery_by_region, collected_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                "meta", ad_id, advertiser, advertiser_id, ad_text,
                spend_min, spend_max, imp_min, imp_max,
                currency, start_date, end_date, platforms,
                demo, regions, now,
            ))
            if cur.rowcount:
                inserted += 1
            else:
                skipped += 1

    conn.commit()
    return inserted, skipped


if __name__ == "__main__":
    files = sys.argv[1:]
    if not files:
        print("Uso: python3 src/import_csv.py arquivo1.csv arquivo2.csv ...")
        sys.exit(1)

    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    now = datetime.utcnow().isoformat()

    total_inserted = 0
    total_skipped  = 0

    for path in files:
        if not os.path.exists(path):
            print(f"[Aviso] Arquivo não encontrado: {path}")
            continue
        inserted, skipped = import_file(conn, path, now)
        print(f"  {os.path.basename(path)}: +{inserted} novos, {skipped} já existiam")
        total_inserted += inserted
        total_skipped  += skipped

    conn.close()
    print(f"\nTotal: +{total_inserted} anúncios novos adicionados, {total_skipped} ignorados (duplicatas)")
    if total_inserted > 0:
        print("Próximo passo: python3 src/export.py")
