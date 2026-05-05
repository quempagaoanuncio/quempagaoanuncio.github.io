"""
Uso:
    python3 src/analyze.py

Analisa o texto dos anúncios usando Claude (Haiku) e armazena:
- tema principal
- tom
- tipo (próprio / terceiro)

Só processa anúncios ainda não analisados.
"""

import os
import sqlite3
import json
import time
import anthropic

# carrega .env — procura a partir do diretório onde o script é chamado
for _candidate in ['.env', 'src/../.env', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')]:
    if os.path.exists(_candidate):
        with open(_candidate) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and '=' in _line and not _line.startswith('#'):
                    _k, _v = _line.split('=', 1)
                    # sempre sobrescreve se o valor atual estiver vazio
                    _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
                    if not os.environ.get(_k):
                        os.environ[_k] = _v
        break

DB_PATH = "data/ads.db"
MODEL   = "claude-haiku-4-5"

TEMAS = [
    "saúde", "educação", "segurança", "economia", "agropecuária",
    "infraestrutura", "meio ambiente", "direitos sociais", "soberania/defesa",
    "política/institucional", "ataque a adversário", "promoção pessoal",
    "outro"
]

TONS = ["propositivo", "emocional", "informativo", "alarmista", "neutro"]

PROMPT = """Você é um analista de propaganda política. Analise o texto do anúncio abaixo e responda APENAS com um JSON válido, sem texto adicional.

Texto do anúncio:
{texto}

Responda com este JSON exato:
{{
  "tema": "<um dos temas: {temas}>",
  "tom": "<um dos tons: {tons}>",
  "tipo": "<'proprio' se o anúncio foi claramente pago pelo próprio candidato, 'terceiro' se é de outro anunciante que menciona o candidato>"
}}"""


def init_columns(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(ads)").fetchall()]
    for col, tipo in [("tema", "TEXT"), ("tom", "TEXT"), ("tipo_anuncio", "TEXT"), ("analyzed_at", "TEXT")]:
        if col not in cols:
            conn.execute(f"ALTER TABLE ads ADD COLUMN {col} {tipo}")
    conn.commit()


def analyze_ad(client, text):
    if not text or len(text.strip()) < 20:
        return None
    prompt = PROMPT.format(
        texto=text[:1500],
        temas=", ".join(TEMAS),
        tons=", ".join(TONS)
    )
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = msg.content[0].text.strip()
        # remove markdown code blocks se presentes
        import re as _re
        raw = _re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=_re.DOTALL).strip()
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        print(f"  [erro] {e}")
        return None


def run():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    init_columns(conn)

    rows = conn.execute("""
        SELECT id, ad_text, advertiser_name FROM ads
        WHERE analyzed_at IS NULL AND ad_text IS NOT NULL AND ad_text != ''
        ORDER BY spend_max DESC
    """).fetchall()

    print(f"[Analyze] {len(rows)} anúncios para analisar")
    if not rows:
        print("Nada a fazer.")
        conn.close()
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip().strip('"').strip("'")
    if not api_key.startswith("sk-"):
        print(f"[Erro] ANTHROPIC_API_KEY inválida ou não encontrada (valor: '{api_key[:10]}...')")
        conn.close()
        return
    client = anthropic.Anthropic(api_key=api_key)
    from datetime import datetime
    now = datetime.utcnow().isoformat()

    ok = erro = 0
    for i, row in enumerate(rows, 1):
        result = analyze_ad(client, row["ad_text"])
        if result:
            conn.execute("""
                UPDATE ads SET tema=?, tom=?, tipo_anuncio=?, analyzed_at=?
                WHERE id=?
            """, (
                result.get("tema"), result.get("tom"),
                result.get("tipo"), now, row["id"]
            ))
            ok += 1
        else:
            erro += 1

        if i % 50 == 0:
            conn.commit()
            print(f"  {i}/{len(rows)} processados…")
        time.sleep(1.5)  # respeita rate limit de 50 req/min

    conn.commit()
    conn.close()
    print(f"\n[Analyze] OK: {ok} | Sem texto/erro: {erro}")
    print("Próximo passo: python3 src/export.py")


if __name__ == "__main__":
    run()
