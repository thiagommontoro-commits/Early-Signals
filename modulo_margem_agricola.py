# -*- coding: utf-8 -*-
"""
modulo_margem_agricola.py
=========================
Módulo do projeto Early Signals — Aba "Margem do Produtor".

Interface (contrato usado por gerador_dashboard_early_signals.py):
    from modulo_margem_agricola import processar_margem_agricola
    dados_margem = processar_margem_agricola()   # -> dict

Objetivo
--------
Montar a base comparativa de MARGEM (R$/ha) por Cultura x UF para as
ÚLTIMAS 3 SAFRAS, usando exclusivamente dados oficiais:

    Margem (R$/ha)  = Receita (R$/ha) - Custo Total (R$/ha)
    Receita (R$/ha) = Produtividade (sc/ha) x Preço médio (R$/sc)

Fontes (100% oficiais, sem nada inventado):
    - CUSTO TOTAL ....... CONAB · Custos de Produção        (agrobr.conab.custo_producao_total)
    - PRODUTIVIDADE ..... CONAB · Série Histórica de Safra   (agrobr.conab.safras)
    - PREÇO ............. CONAB · Preço recebido produtor (PADRÃO) OU CEPEA/ESALQ

Transparência de dados
----------------------
A doc do agrobr (mar/2026) registra que planilhas de custo de GRÃOS no gov.br
às vezes carregam via JavaScript e podem não expor .xlsx para scraping. Quando
QUALQUER insumo (custo, produtividade ou preço) faltar para uma safra, o campo
correspondente fica None e o dashboard exibe "—". NUNCA estimamos.

Robustez
--------
Este módulo NUNCA quebra o pipeline: se o agrobr não estiver instalado ou uma
fonte estiver fora do ar, ele retorna a estrutura com os cards e valores None
(o dashboard renderiza os cards com "—").

Cache mensal (mesmo padrão dos outros módulos):
    cache_margem_YYYY_MM.json  — evita rebaixar a mesma fonte várias vezes no mês.

Autoria: Global Reporting & Analytics — Thiago Montoro (AGCO)
"""

import os
import json
import asyncio
import datetime
import traceback
from pathlib import Path

# --------------------------------------------------------------------------
# CONFIGURAÇÃO
# --------------------------------------------------------------------------
# Combinações Cultura x UF que viram cards na aba.
#   sc_por_t: soja/milho/trigo = 16,667 sc(60kg)/t ; algodão em @ = 66,667 @(15kg)/t
COMBINACOES = [
    {"cultura": "Soja",    "uf": "MT", "conab": "soja",    "cepea": "soja",    "unid": "sc60",   "sc_por_t": 16.667},
    {"cultura": "Soja",    "uf": "PR", "conab": "soja",    "cepea": "soja",    "unid": "sc60",   "sc_por_t": 16.667},
    {"cultura": "Soja",    "uf": "RS", "conab": "soja",    "cepea": "soja",    "unid": "sc60",   "sc_por_t": 16.667},
    {"cultura": "Soja",    "uf": "GO", "conab": "soja",    "cepea": "soja",    "unid": "sc60",   "sc_por_t": 16.667},
    {"cultura": "Milho",   "uf": "MT", "conab": "milho",   "cepea": "milho",   "unid": "sc60",   "sc_por_t": 16.667},
    {"cultura": "Milho",   "uf": "PR", "conab": "milho",   "cepea": "milho",   "unid": "sc60",   "sc_por_t": 16.667},
    {"cultura": "Algodão", "uf": "MT", "conab": "algodao", "cepea": "algodao", "unid": "arroba", "sc_por_t": 66.667},
    {"cultura": "Trigo",   "uf": "PR", "conab": "trigo",   "cepea": "trigo",   "unid": "sc60",   "sc_por_t": 16.667},
]

N_SAFRAS = 3  # pedido do usuário: comparar as últimas 3 safras

# Fonte de preço configurável (sem editar código):
#   EARLY_SIGNALS_PRECO_FONTE=conab_prod  -> CONAB · Preço recebido produtor (PADRÃO)
#   EARLY_SIGNALS_PRECO_FONTE=cepea       -> CEPEA/ESALQ
# Padrão = conab_prod para manter COERÊNCIA metodológica com o custo CONAB
# (mesma lógica "porteira", já embute o deságio regional -> margem real por UF).
PRECO_FONTE = os.getenv("EARLY_SIGNALS_PRECO_FONTE", "conab_prod").lower()

SCRIPT_DIR = Path(__file__).parent


# --------------------------------------------------------------------------
# HELPERS DE SAFRA
# --------------------------------------------------------------------------
def safra_vigente(hoje=None):
    """
    Safra de referência 'AAAA/AA' (a próxima/em planejamento).
    A partir de agosto já consideramos a safra AAAA/AA+1, pois é quando a CONAB
    começa a publicar os custos do novo ciclo e o foco do dashboard é a próxima safra.
    """
    hoje = hoje or datetime.date.today()
    ini = hoje.year if hoje.month >= 8 else hoje.year - 1
    return f"{ini}/{str(ini + 1)[-2:]}"


def ultimas_safras(n=N_SAFRAS, hoje=None):
    """Ex.: ['2024/25','2025/26','2026/27']."""
    ini = int(safra_vigente(hoje).split("/")[0])
    return [f"{ini - k}/{str(ini - k + 1)[-2:]}" for k in range(n - 1, -1, -1)]


# --------------------------------------------------------------------------
# EXTRAÇÃO (agrobr) — cada função devolve None em vez de estimar
# --------------------------------------------------------------------------
async def _custo_total_ha(conab, cultura_conab, uf, safra):
    try:
        totais = await conab.custo_producao_total(cultura_conab, uf=uf, safra=safra)
        if totais is None or len(totais) == 0:
            return None
        row = totais.iloc[0]
        for chave in ("CT", "ct", "custo_total", "COT", "cot"):
            if chave in totais.columns and row.get(chave) not in (None, ""):
                return float(row[chave])
        return None
    except Exception as e:
        print(f"      ⚠ custo indisponível ({cultura_conab}/{uf}/{safra}): {e}")
        return None


async def _produtividade_sc_ha(conab, cultura_conab, uf, safra, sc_por_t):
    try:
        df = await conab.safras(cultura_conab, safra=safra, uf=uf)
        if df is None or len(df) == 0:
            return None
        kg_ha = float(df.iloc[0]["produtividade"])   # kg/ha
        return (kg_ha / 1000.0) * sc_por_t            # sc/ha (ou @/ha)
    except Exception as e:
        print(f"      ⚠ produtividade indisponível ({cultura_conab}/{uf}/{safra}): {e}")
        return None


async def _preco_medio(cepea, conab, produto, safra):
    ini_ano = int(safra.split("/")[0])
    inicio, fim = f"{ini_ano}-09-01", f"{ini_ano + 1}-08-31"
    try:
        if PRECO_FONTE == "conab_prod":
            df = await conab.preco_produtor(produto, inicio=inicio, fim=fim)
        else:
            df = await cepea.indicador(produto, inicio=inicio, fim=fim)
        if df is None or len(df) == 0:
            return None
        col = next((c for c in ("valor", "preco", "indicador", "value", "preco_medio") if c in df.columns), None)
        return float(df[col].astype(float).mean()) if col else None
    except Exception as e:
        print(f"      ⚠ preço indisponível ({produto}/{safra}/{PRECO_FONTE}): {e}")
        return None


def _tendencia(serie):
    """Compara margem da última safra vs a anterior."""
    if len(serie) < 2:
        return "indisponivel", None
    atual, ant = serie[-1]["margem_ha"], serie[-2]["margem_ha"]
    if atual is None or ant is None or ant == 0:
        return "indisponivel", None
    delta = (atual - ant) / abs(ant) * 100.0
    if delta > 3:
        return "alta", round(delta, 1)
    if delta < -3:
        return "baixa", round(delta, 1)
    return "estavel", round(delta, 1)


# --------------------------------------------------------------------------
# MONTAGEM (async)
# --------------------------------------------------------------------------
async def _montar_base_async():
    from agrobr import conab, cepea  # import tardio (só quando for buscar)

    safras = ultimas_safras()
    print(f"   📅 Safras comparadas: {safras}")

    cards = []
    for combo in COMBINACOES:
        print(f"   🌱 {combo['cultura']} · {combo['uf']}")
        serie = []
        for safra in safras:
            custo = await _custo_total_ha(conab, combo["conab"], combo["uf"], safra)
            prod = await _produtividade_sc_ha(conab, combo["conab"], combo["uf"], safra, combo["sc_por_t"])
            produto_preco = combo["conab"] if PRECO_FONTE == "conab_prod" else combo["cepea"]
            preco = await _preco_medio(cepea, conab, produto_preco, safra)

            receita = round(prod * preco, 2) if (prod is not None and preco is not None) else None
            margem = round(receita - custo, 2) if (receita is not None and custo is not None) else None

            serie.append({
                "safra": safra,
                "custo_total_ha": None if custo is None else round(custo, 2),
                "produtividade": None if prod is None else round(prod, 1),
                "preco_medio": None if preco is None else round(preco, 2),
                "receita_ha": receita,
                "margem_ha": margem,
            })

        tendencia, delta_pct = _tendencia(serie)
        cards.append({
            "cultura": combo["cultura"], "uf": combo["uf"], "unidade": combo["unid"],
            "serie": serie, "tendencia": tendencia, "delta_pct": delta_pct,
        })

    return _empacotar(cards, safras)


def _empacotar(cards, safras):
    return {
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "safras": safras,
        "metodologia": "Margem (R$/ha) = Receita (Produtividade x Preço) - Custo Total.",
        "fontes": {
            "custo": "CONAB - Custos de Produção (GECUP)",
            "produtividade": "CONAB - Série Histórica de Safra (GEASA)",
            "preco": "CONAB - Preço recebido produtor" if PRECO_FONTE == "conab_prod" else "CEPEA/ESALQ",
        },
        "autoria": "Global Reporting & Analytics — Thiago Montoro (AGCO)",
        "cards": cards,
    }


def _estrutura_vazia(motivo=""):
    """Fallback: cards com valores None (dashboard mostra '—')."""
    safras = ultimas_safras()
    cards = []
    for combo in COMBINACOES:
        serie = [{"safra": s, "custo_total_ha": None, "produtividade": None,
                  "preco_medio": None, "receita_ha": None, "margem_ha": None} for s in safras]
        cards.append({"cultura": combo["cultura"], "uf": combo["uf"], "unidade": combo["unid"],
                      "serie": serie, "tendencia": "indisponivel", "delta_pct": None})
    base = _empacotar(cards, safras)
    if motivo:
        base["aviso"] = motivo
    return base


# --------------------------------------------------------------------------
# INTERFACE PÚBLICA (chamada pelo gerador)
# --------------------------------------------------------------------------
def processar_margem_agricola(usar_cache=True):
    """
    Retorna o dict com a base de margens das últimas 3 safras (CONAB + CEPEA).
    Nunca lança exceção: em caso de falha, devolve estrutura com valores None.
    """
    now = datetime.datetime.now()
    cache_path = SCRIPT_DIR / f"cache_margem_{now.year}_{now.month:02d}.json"

    # 1) cache mensal
    if usar_cache and cache_path.exists():
        try:
            print(f"   🧠 Usando cache de margem: {cache_path.name}")
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"   ⚠ Cache de margem inválido ({e}). Recalculando...")

    # 2) tenta importar o agrobr
    try:
        import agrobr  # noqa: F401
    except ImportError:
        print("   ❌ Pacote 'agrobr' não instalado — margem exibida como '—'. "
              "(adicione 'agrobr' e 'pandas' ao requirements.txt)")
        return _estrutura_vazia("Pacote agrobr indisponível.")

    # 3) busca oficial
    try:
        base = asyncio.run(_montar_base_async())
        try:
            cache_path.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"   ✅ Cache de margem salvo: {cache_path.name}")
        except Exception as e:
            print(f"   ⚠ Não foi possível salvar o cache de margem: {e}")
        return base
    except Exception:
        print("   ❌ Falha ao montar base de margens (retornando '—'):")
        traceback.print_exc()
        return _estrutura_vazia("Falha na coleta CONAB/CEPEA.")


if __name__ == "__main__":
    print("=" * 64)
    print("EARLY SIGNALS · modulo_margem_agricola (teste standalone)")
    print("=" * 64)
    dados = processar_margem_agricola()
    ok = sum(1 for c in dados["cards"] if c["serie"][-1]["margem_ha"] is not None)
    print(f"Resultado: {ok}/{len(dados['cards'])} cards com margem na safra vigente.")
