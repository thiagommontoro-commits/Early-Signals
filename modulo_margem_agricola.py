# -*- coding: utf-8 -*-
"""
modulo_margem_agricola.py  (v2 — com PROVENIÊNCIA de dados)
===========================================================
Aba "Margem do Produtor" do Early Signals.

Cada ponto (safra) carrega FLAGS de proveniência, permitindo o dashboard mostrar
EXPLICITAMENTE o que é dado oficial, o que é repetido de uma safra anterior
(carry-forward) e o que está indisponível.

    Margem (R$/ha)  = Receita (R$/ha) - Custo Total (R$/ha)
    Receita (R$/ha) = Produtividade (sc/ha) x Preço médio (R$/sc)

Fontes oficiais:
    - CUSTO ......... CONAB · soma de 'valor_ha' de conab.custo_producao()
    - PRODUTIVIDADE . CONAB · conab.safras()  [exige agrobr[browser] + playwright chromium]
    - PREÇO ......... CEPEA/ESALQ · cepea.indicador()  [truststore resolve SSL AGCO]

Proveniência por dado (custo/prod/preço) e consolidada (status_geral):
    "oficial"       -> veio direto da fonte para AQUELA safra
    "repetido"      -> igual à safra anterior (carry-forward)
    "indisponivel"  -> a fonte não retornou dado

status_geral do card/safra:
    "completo"  -> custo, prod e preço presentes E todos "oficial"
    "parcial"   -> tem margem, mas ALGUM insumo é "repetido"
    "incompleto"-> falta algum insumo (margem = None)

Robustez: nunca quebra o pipeline. Cache mensal: cache_margem_YYYY_MM.json.
Autoria: Global Reporting & Analytics — Thiago Montoro (AGCO)
"""

# SSL corporativo (AGCO): usar certificados do SO para o CEPEA
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import os
import json
import asyncio
import datetime
import traceback
from pathlib import Path

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

N_SAFRAS = 3
PRECO_FONTE = os.getenv("EARLY_SIGNALS_PRECO_FONTE", "cepea").lower()
SCRIPT_DIR = Path(__file__).parent


def safra_vigente(hoje=None):
    hoje = hoje or datetime.date.today()
    ini = hoje.year if hoje.month >= 8 else hoje.year - 1
    return f"{ini}/{str(ini + 1)[-2:]}"


def ultimas_safras(n=N_SAFRAS, hoje=None):
    ini = int(safra_vigente(hoje).split("/")[0])
    return [f"{ini - k}/{str(ini - k + 1)[-2:]}" for k in range(n - 1, -1, -1)]


async def _custo_total_ha(conab, cultura_conab, uf, safra):
    try:
        df = await conab.custo_producao(cultura_conab, uf=uf, safra=safra)
        if df is None or len(df) == 0 or "valor_ha" not in getattr(df, "columns", []):
            return None
        total = float(df["valor_ha"].dropna().sum())
        return round(total, 2) if total > 0 else None
    except Exception as e:
        print(f"      ⚠ custo indisponível ({cultura_conab}/{uf}/{safra}): {e}")
        return None


async def _produtividade_sc_ha(conab, cultura_conab, uf, safra, sc_por_t):
    try:
        df = await conab.safras(cultura_conab, safra=safra, uf=uf)
        if df is None or len(df) == 0 or "produtividade" not in getattr(df, "columns", []):
            return None
        return round(float(df.iloc[0]["produtividade"]) / 1000.0 * sc_por_t, 1)
    except Exception as e:
        print(f"      ⚠ produtividade indisponível ({cultura_conab}/{uf}/{safra}): {e}")
        return None


async def _preco_medio(cepea, produto, safra):
    ini_ano = int(safra.split("/")[0])
    inicio, fim = f"{ini_ano}-09-01", f"{ini_ano + 1}-08-31"
    try:
        df = await cepea.indicador(produto, inicio=inicio, fim=fim)
        if df is None or len(df) == 0:
            return None
        col = next((c for c in ("valor", "preco", "indicador", "value", "preco_medio")
                    if c in getattr(df, "columns", [])), None)
        return round(float(df[col].astype(float).mean()), 2) if col else None
    except Exception as e:
        print(f"      ⚠ preço indisponível ({produto}/{safra}): {e}")
        return None


def _tendencia(serie):
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


def _flag(valor, valor_anterior):
    """Classifica proveniência de um dado numérico comparando com a safra anterior."""
    if valor is None:
        return "indisponivel"
    if valor_anterior is not None and abs(valor - valor_anterior) < 0.01:
        return "repetido"
    return "oficial"


def _status_geral(ponto):
    if ponto["margem_ha"] is None:
        return "incompleto"
    flags = (ponto["custo_status"], ponto["produtividade_status"], ponto["preco_status"])
    if "repetido" in flags:
        return "parcial"
    return "completo"


async def _montar_base_async():
    from agrobr import conab, cepea

    safras = ultimas_safras()
    print(f"   📅 Safras comparadas: {safras}")

    cards = []
    for combo in COMBINACOES:
        print(f"   🌱 {combo['cultura']} · {combo['uf']}")
        serie = []
        prev_custo = prev_prod = prev_preco = None
        for safra in safras:
            custo = await _custo_total_ha(conab, combo["conab"], combo["uf"], safra)
            prod = await _produtividade_sc_ha(conab, combo["conab"], combo["uf"], safra, combo["sc_por_t"])
            preco = await _preco_medio(cepea, combo["cepea"], safra)

            custo_status = _flag(custo, prev_custo)
            prod_status = _flag(prod, prev_prod)
            preco_status = _flag(preco, prev_preco)

            receita = round(prod * preco, 2) if (prod is not None and preco is not None) else None
            margem = round(receita - custo, 2) if (receita is not None and custo is not None) else None

            ponto = {
                "safra": safra,
                "custo_total_ha": custo, "custo_status": custo_status,
                "produtividade": prod, "produtividade_status": prod_status,
                "preco_medio": preco, "preco_status": preco_status,
                "receita_ha": receita,
                "margem_ha": margem,
            }
            ponto["status_geral"] = _status_geral(ponto)
            serie.append(ponto)

            prev_custo, prev_prod, prev_preco = custo, prod, preco

        tendencia, delta_pct = _tendencia(serie)
        cards.append({
            "cultura": combo["cultura"], "uf": combo["uf"], "unidade": combo["unid"],
            "serie": serie, "tendencia": tendencia, "delta_pct": delta_pct,
        })

    return _empacotar(cards, safras)


def _empacotar(cards, safras):
    total = sum(len(c["serie"]) for c in cards)
    completos = sum(1 for c in cards for p in c["serie"] if p["status_geral"] == "completo")
    parciais = sum(1 for c in cards for p in c["serie"] if p["status_geral"] == "parcial")
    incompletos = sum(1 for c in cards for p in c["serie"] if p["status_geral"] == "incompleto")
    return {
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "safras": safras,
        "metodologia": "Margem (R$/ha) = Receita (Produtividade x Preço CEPEA) - Custo Total (CONAB).",
        "fontes": {
            "custo": "CONAB - Custos de Produção (soma valor_ha)",
            "produtividade": "CONAB - Série Histórica de Safra (GEASA)",
            "preco": "CEPEA/ESALQ",
        },
        "resumo_qualidade": {
            "total": total, "completos": completos,
            "parciais": parciais, "incompletos": incompletos,
        },
        "autoria": "Global Reporting & Analytics — Thiago Montoro (AGCO)",
        "cards": cards,
    }


def _estrutura_vazia(motivo=""):
    safras = ultimas_safras()
    cards = []
    for combo in COMBINACOES:
        serie = []
        for s in safras:
            serie.append({
                "safra": s,
                "custo_total_ha": None, "custo_status": "indisponivel",
                "produtividade": None, "produtividade_status": "indisponivel",
                "preco_medio": None, "preco_status": "indisponivel",
                "receita_ha": None, "margem_ha": None, "status_geral": "incompleto",
            })
        cards.append({"cultura": combo["cultura"], "uf": combo["uf"], "unidade": combo["unid"],
                      "serie": serie, "tendencia": "indisponivel", "delta_pct": None})
    base = _empacotar(cards, safras)
    if motivo:
        base["aviso"] = motivo
    return base


def processar_margem_agricola(usar_cache=True):
    now = datetime.datetime.now()
    cache_path = SCRIPT_DIR / f"cache_margem_{now.year}_{now.month:02d}.json"

    if usar_cache and cache_path.exists():
        try:
            print(f"   🧠 Usando cache de margem: {cache_path.name}")
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"   ⚠ Cache inválido ({e}). Recalculando...")

    try:
        import agrobr  # noqa
    except ImportError:
        print("   ❌ 'agrobr' não instalado — margem '—'. pip install \"agrobr[browser]\" pandas truststore")
        return _estrutura_vazia("Pacote agrobr indisponível.")

    try:
        base = asyncio.run(_montar_base_async())
        try:
            cache_path.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"   ✅ Cache salvo: {cache_path.name}")
        except Exception as e:
            print(f"   ⚠ Não foi possível salvar cache: {e}")
        return base
    except Exception:
        print("   ❌ Falha ao montar base de margens (retornando '—'):")
        traceback.print_exc()
        return _estrutura_vazia("Falha na coleta CONAB/CEPEA.")


if __name__ == "__main__":
    print("=" * 64)
    print("EARLY SIGNALS · modulo_margem_agricola v2 (teste standalone)")
    print("=" * 64)
    dados = processar_margem_agricola()
    r = dados["resumo_qualidade"]
    print(f"Qualidade: {r['completos']} completos | {r['parciais']} parciais | "
          f"{r['incompletos']} incompletos (de {r['total']} pontos).")
