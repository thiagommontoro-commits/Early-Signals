# ==========================================================================
# MÓDULO: MARGEM & CUSTO AGRÍCOLA — CONAB  (Early Signals - LATAM / Brasil)
# --------------------------------------------------------------------------
# Nova aba com dados OFICIAIS da CONAB (Companhia Nacional de Abastecimento)
# de custo de produção e rentabilidade agrícola, distinguindo:
#   • SAFRA   (ex.: 2024/25, 2025/26)
#   • CULTURA (soja, milho, algodão, trigo, arroz, feijão...)
#   • REGIÃO / UF (MT, PR, RS, GO, BA...)
#
# Extração via biblioteca open-source `agrobr` (camada sobre a CONAB).
#   requirements: agrobr    (ou agrobr[browser] se a CONAB exigir JS dinâmico)
#
# ENGENHARIA DEFENSIVA (nunca inventa número):
#   - Detecta automaticamente as colunas retornadas pela CONAB.
#   - Cenário A: a fonte traz MARGEM/RENTABILIDADE -> exibe direto.
#   - Cenário B: a fonte traz SÓ CUSTO por item     -> soma custo total/ha.
#   - Campo ausente = None -> renderizado como "—".
#   - Se a agrobr/CONAB falhar -> aba mostra "indisponível", sem quebrar nada.
#
# ATUALIZAÇÃO: roda a cada execução do GitHub Actions (push + cron mensal),
#   sempre buscando o dado mais recente publicado pela CONAB. Sem upload manual.
# ==========================================================================

# Culturas x UFs monitoradas (ajuste livre)
ALVOS = [
    {"cultura": "soja",    "uf": "MT", "icone": "🌱"},
    {"cultura": "soja",    "uf": "PR", "icone": "🌱"},
    {"cultura": "soja",    "uf": "RS", "icone": "🌱"},
    {"cultura": "soja",    "uf": "GO", "icone": "🌱"},
    {"cultura": "milho",   "uf": "MT", "icone": "🌽"},
    {"cultura": "milho",   "uf": "PR", "icone": "🌽"},
    {"cultura": "algodao", "uf": "MT", "icone": "🧵"},
    {"cultura": "trigo",   "uf": "PR", "icone": "🌾"},
    {"cultura": "trigo",   "uf": "RS", "icone": "🌾"},
]

NOMES_CULTURA = {
    "soja":    {"pt": "Soja", "en": "Soybean", "es": "Soja"},
    "milho":   {"pt": "Milho", "en": "Corn", "es": "Maíz"},
    "algodao": {"pt": "Algodão", "en": "Cotton", "es": "Algodón"},
    "trigo":   {"pt": "Trigo", "en": "Wheat", "es": "Trigo"},
    "arroz":   {"pt": "Arroz", "en": "Rice", "es": "Arroz"},
    "feijao":  {"pt": "Feijão", "en": "Beans", "es": "Frijol"},
}

# Possíveis nomes de coluna (a agrobr pode variar). O módulo tenta cada um.
COLS_MARGEM      = ["margem", "margem_liquida", "margem_bruta", "rentabilidade", "lucro", "resultado"]
COLS_RECEITA     = ["receita", "receita_bruta", "receita_total", "renda_bruta"]
COLS_CUSTO_TOTAL = ["custo_total", "custo_total_ha", "custo_producao", "ct", "cot", "coe", "custo"]
COLS_PRODUT      = ["produtividade", "rendimento", "prod"]
COLS_VALOR_HA    = ["valor_ha", "valor", "valor_reais_ha", "custo_ha"]
COLS_SAFRA       = ["safra", "ano_safra", "ano"]
COLS_PRECO       = ["preco", "preco_recebido", "preco_medio", "preco_venda"]


def _get_conab():
    """Importa a interface conab da agrobr, preferindo modo síncrono."""
    try:
        from agrobr.sync import conab
        return conab, "sync"
    except Exception:
        pass
    try:
        from agrobr import conab
        return conab, "async"
    except Exception as e:
        print(f"   agrobr indisponível: {e}")
        return None, None


def _chamar(fn, modo, *args, **kwargs):
    if modo == "sync":
        return fn(*args, **kwargs)
    import asyncio
    return asyncio.run(fn(*args, **kwargs))


def _col(df, candidatos):
    """Nome real da 1ª coluna do df que casar com a lista (case-insensitive)."""
    lower = {c.lower(): c for c in df.columns}
    for cand in candidatos:
        if cand in lower:
            return lower[cand]
    return None


def _num(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _extrair_indicadores(df):
    """
    Extrai de forma adaptativa (schema desconhecido a priori):
    safra, custo_total/ha, receita, margem, produtividade, preco.
    Cada um vira None se a coluna não existir.
    """
    import pandas as pd

    out = {"safra": None, "custo_total": None, "receita": None, "margem": None,
           "produtividade": None, "preco": None, "modo_dado": "indefinido"}

    if df is None or len(df) == 0:
        return out

    csafra = _col(df, COLS_SAFRA)
    if csafra:
        try:
            out["safra"] = str(sorted(df[csafra].dropna().astype(str).unique())[-1])
        except Exception:
            vals = df[csafra].dropna()
            out["safra"] = str(vals.iloc[-1]) if len(vals) else None

    def _ultimo_num(col):
        if not col:
            return None
        serie = pd.to_numeric(df[col], errors="coerce").dropna()
        return _num(serie.iloc[-1]) if len(serie) else None

    def _max_num(col):
        if not col:
            return None
        serie = pd.to_numeric(df[col], errors="coerce").dropna()
        return _num(serie.max()) if len(serie) else None

    # Cenário A: margem/receita já vêm prontas
    cmarg = _col(df, COLS_MARGEM)
    if cmarg:
        out["margem"] = _ultimo_num(cmarg)
        if out["margem"] is not None:
            out["modo_dado"] = "margem_oficial"
    out["receita"] = _ultimo_num(_col(df, COLS_RECEITA))
    out["produtividade"] = _ultimo_num(_col(df, COLS_PRODUT))
    out["preco"] = _ultimo_num(_col(df, COLS_PRECO))

    # Cenário B: custo total, ou soma de valor_ha por item
    cct = _col(df, COLS_CUSTO_TOTAL)
    cvalha = _col(df, COLS_VALOR_HA)
    if cct:
        out["custo_total"] = _max_num(cct)
    elif cvalha:
        serie = pd.to_numeric(df[cvalha], errors="coerce").dropna()
        out["custo_total"] = _num(serie.sum()) if len(serie) else None
    if out["modo_dado"] == "indefinido" and out["custo_total"] is not None:
        out["modo_dado"] = "custo_oficial"

    return out


def _tendencia(margem):
    if margem is None:
        return "incerto"
    if margem > 0:
        return "positivo"
    if margem < 0:
        return "negativo"
    return "incerto"


def processar_margem_agricola():
    """
    Retorna dict:
      { "disponivel": bool, "fonte": "CONAB", "modo_dado": str, "itens": [...] }
    """
    print("💰 Margem Agrícola (CONAB via agrobr): iniciando...")
    conab, modo = _get_conab()
    if conab is None:
        return {"disponivel": False, "fonte": "CONAB"}

    fn = getattr(conab, "custo_producao", None)
    if fn is None:
        disponiveis = [x for x in dir(conab) if not x.startswith("_")]
        print("   conab.custo_producao não encontrado. Disponíveis:", disponiveis)
        return {"disponivel": False, "fonte": "CONAB"}

    itens, modos = [], set()
    for alvo in ALVOS:
        cultura, uf = alvo["cultura"], alvo["uf"]
        try:
            df = _chamar(fn, modo, cultura, uf=uf)
            ind = _extrair_indicadores(df)
            modos.add(ind["modo_dado"])
            itens.append({
                "cultura": cultura, "uf": uf, "icone": alvo["icone"],
                "nome": NOMES_CULTURA.get(cultura, {"pt": cultura, "en": cultura, "es": cultura}),
                "safra": ind["safra"], "custo_total": ind["custo_total"],
                "receita": ind["receita"], "margem": ind["margem"],
                "produtividade": ind["produtividade"], "preco": ind["preco"],
                "tendencia": _tendencia(ind["margem"]),
            })
            print(f"   OK {cultura}/{uf}: safra={ind['safra']} margem={ind['margem']} "
                  f"custo={ind['custo_total']} modo={ind['modo_dado']}")
        except Exception as e:
            print(f"   Falha {cultura}/{uf}: {e}")

    if not itens:
        return {"disponivel": False, "fonte": "CONAB"}

    modos.discard("indefinido")
    modo_dado = list(modos)[0] if len(modos) == 1 else ("misto" if modos else "indefinido")
    return {"disponivel": True, "fonte": "CONAB", "modo_dado": modo_dado, "itens": itens}


if __name__ == "__main__":
    import json
    print(json.dumps(processar_margem_agricola(), ensure_ascii=False, indent=2))
