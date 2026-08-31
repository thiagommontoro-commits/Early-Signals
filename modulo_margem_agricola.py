# -*- coding: utf-8 -*-
"""
modulo_margem_agricola.py  (v2.1 — PROVENIÊNCIA de dados + cache com SCHEMA_VERSION)
====================================================================================
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

Robustez (v2.1): nunca quebra o pipeline. Cache mensal: cache_margem_YYYY_MM.json.
    >>> NOVO: o cache carrega um SCHEMA_VERSION. Se o cache existente foi gravado
    por uma versão anterior do módulo (schema diferente ou sem 'status_geral'),
    ele é AUTOMATICAMENTE invalidado e os dados são recalculados. Isso evita o
    KeyError: 'status_geral' causado por cache legado, sem intervenção manual.

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

# >>> NOVO: versão do schema de dados. Incremente sempre que a estrutura de
# cada "ponto"/"card" mudar OU quando o conjunto de COMBINACOES mudar (para que
# caches antigos, gerados sem as novas culturas, sejam invalidados e recalculados).
# 2.2: inclusão da cultura CAFÉ (Arábica-MG e Conilon-ES).
# 2.3: cascata de aliases (fallback automático) para CONAB/CEPEA do café — se o
#      nome do produto não for reconhecido pela fonte, tenta o próximo da lista.
SCHEMA_VERSION = "2.3"

COMBINACOES = [
    {"cultura": "Soja",    "uf": "MT", "conab": "soja",    "cepea": "soja",          "unid": "sc60",   "sc_por_t": 16.667},
    {"cultura": "Soja",    "uf": "PR", "conab": "soja",    "cepea": "soja",          "unid": "sc60",   "sc_por_t": 16.667},
    {"cultura": "Soja",    "uf": "RS", "conab": "soja",    "cepea": "soja",          "unid": "sc60",   "sc_por_t": 16.667},
    {"cultura": "Soja",    "uf": "GO", "conab": "soja",    "cepea": "soja",          "unid": "sc60",   "sc_por_t": 16.667},
    {"cultura": "Milho",   "uf": "MT", "conab": "milho",   "cepea": "milho",         "unid": "sc60",   "sc_por_t": 16.667},
    {"cultura": "Milho",   "uf": "PR", "conab": "milho",   "cepea": "milho",         "unid": "sc60",   "sc_por_t": 16.667},
    {"cultura": "Algodão", "uf": "MT", "conab": "algodao", "cepea": "algodao",       "unid": "arroba", "sc_por_t": 66.667},
    {"cultura": "Trigo",   "uf": "PR", "conab": "trigo",   "cepea": "trigo",         "unid": "sc60",   "sc_por_t": 16.667},
    # --- NOVO (v2.3): Café (saca de 60 kg beneficiado), com CASCATA de aliases.
    # Tanto 'conab' quanto 'cepea' aceitam uma lista de nomes candidatos: o
    # módulo tenta cada um, em ordem, e usa o primeiro que retornar dado válido.
    # Isso evita depender de acertar o nome exato do produto na fonte de antemão
    # — se "cafe_arabica" não for reconhecido, tenta "cafe", depois "arabica" etc.
    {"cultura": "Café", "uf": "MG",
     "conab": ["cafe", "cafe_arabica", "arabica"],
     "cepea": ["cafe_arabica", "cafe", "arabica"],
     "unid": "sc60", "sc_por_t": 16.667},
    {"cultura": "Café", "uf": "ES",
     "conab": ["cafe", "cafe_conilon", "conilon", "robusta"],
     "cepea": ["cafe_conilon", "cafe", "conilon", "robusta"],
     "unid": "sc60", "sc_por_t": 16.667},
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


def _como_lista(valor):
    """Normaliza 'valor' para lista: aceita string única ou lista/tupla de aliases."""
    return list(valor) if isinstance(valor, (list, tuple)) else [valor]


async def _custo_total_ha(conab, cultura_conab, uf, safra):
    """
    >>> v2.3: 'cultura_conab' pode ser uma lista de aliases (cascata). Tenta cada
    nome em ordem e usa o primeiro que retornar dado válido, sem quebrar caso
    algum alias não seja reconhecido pela fonte.
    """
    candidatos = _como_lista(cultura_conab)
    for i, nome in enumerate(candidatos):
        try:
            df = await conab.custo_producao(nome, uf=uf, safra=safra)
            if df is None or len(df) == 0 or "valor_ha" not in getattr(df, "columns", []):
                if len(candidatos) > 1:
                    print(f"      ↳ custo: alias '{nome}' sem dados, tentando próximo...")
                continue
            total = float(df["valor_ha"].dropna().sum())
            if total > 0:
                if i > 0:
                    print(f"      ✅ custo resolvido via alias alternativo '{nome}' ({uf}/{safra})")
                return round(total, 2)
        except Exception as e:
            print(f"      ⚠ custo indisponível via alias '{nome}' ({uf}/{safra}): {e}")
            continue
    if len(candidatos) > 1:
        print(f"      ❌ custo indisponível para todos os aliases {candidatos} ({uf}/{safra})")
    return None


async def _produtividade_sc_ha(conab, cultura_conab, uf, safra, sc_por_t):
    """
    >>> v2.3: mesma lógica de cascata de aliases descrita em '_custo_total_ha'.
    """
    candidatos = _como_lista(cultura_conab)
    for i, nome in enumerate(candidatos):
        try:
            df = await conab.safras(nome, safra=safra, uf=uf)
            if df is None or len(df) == 0 or "produtividade" not in getattr(df, "columns", []):
                if len(candidatos) > 1:
                    print(f"      ↳ produtividade: alias '{nome}' sem dados, tentando próximo...")
                continue
            valor = round(float(df.iloc[0]["produtividade"]) / 1000.0 * sc_por_t, 1)
            if i > 0:
                print(f"      ✅ produtividade resolvida via alias alternativo '{nome}' ({uf}/{safra})")
            return valor
        except Exception as e:
            print(f"      ⚠ produtividade indisponível via alias '{nome}' ({uf}/{safra}): {e}")
            continue
    if len(candidatos) > 1:
        print(f"      ❌ produtividade indisponível para todos os aliases {candidatos} ({uf}/{safra})")
    return None


async def _preco_medio(cepea, produto, safra):
    """
    >>> v2.3: 'produto' pode ser uma lista de aliases (cascata). Tenta cada nome
    do indicador CEPEA em ordem e usa o primeiro que retornar dado válido.
    Isso resolve casos como o café, que tem indicadores distintos por variedade
    (ex.: 'cafe_arabica', 'cafe', 'arabica') sem exigir acerto de antemão.
    """
    candidatos = _como_lista(produto)
    ini_ano = int(safra.split("/")[0])
    inicio, fim = f"{ini_ano}-09-01", f"{ini_ano + 1}-08-31"
    for i, nome in enumerate(candidatos):
        try:
            df = await cepea.indicador(nome, inicio=inicio, fim=fim)
            if df is None or len(df) == 0:
                if len(candidatos) > 1:
                    print(f"      ↳ preço: alias '{nome}' sem dados, tentando próximo...")
                continue
            col = next((c for c in ("valor", "preco", "indicador", "value", "preco_medio")
                        if c in getattr(df, "columns", [])), None)
            if not col:
                if len(candidatos) > 1:
                    print(f"      ↳ preço: alias '{nome}' sem coluna reconhecida, tentando próximo...")
                continue
            valor = round(float(df[col].astype(float).mean()), 2)
            if i > 0:
                print(f"      ✅ preço resolvido via alias alternativo '{nome}' (safra {safra})")
            return valor
        except Exception as e:
            print(f"      ⚠ preço indisponível via alias '{nome}' ({safra}): {e}")
            continue
    if len(candidatos) > 1:
        print(f"      ❌ preço indisponível para todos os aliases {candidatos} ({safra})")
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
        "schema_version": SCHEMA_VERSION,  # >>> NOVO: carimbo de versão do schema
        "n_combinacoes": len(cards),       # >>> NOVO: nº de combinações (cultura × UF)
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


def _cache_valido(dados):
    """
    >>> NOVO: valida se um cache carregado é compatível com o schema atual.
    Rejeita caches de versões anteriores (sem 'schema_version', versão diferente,
    ou pontos sem a chave 'status_geral'), forçando o recálculo.
    """
    if not isinstance(dados, dict):
        return False
    if dados.get("schema_version") != SCHEMA_VERSION:
        return False
    cards = dados.get("cards")
    if not isinstance(cards, list) or not cards:
        return False
    # Amostra estrutural: cada ponto precisa das chaves de proveniência
    chaves_obrigatorias = {"status_geral", "custo_status", "produtividade_status", "preco_status"}
    for c in cards:
        for p in c.get("serie", []):
            if not chaves_obrigatorias.issubset(p.keys()):
                return False
    return True


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
            dados_cache = json.loads(cache_path.read_text(encoding="utf-8"))
            # >>> NOVO: só usa o cache se ele for compatível com o schema atual
            if _cache_valido(dados_cache):
                print(f"   🧠 Usando cache de margem: {cache_path.name} (schema {SCHEMA_VERSION})")
                return dados_cache
            print(f"   ♻ Cache '{cache_path.name}' é de schema antigo/incompatível "
                  f"(esperado {SCHEMA_VERSION}). Recalculando...")
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
            print(f"   ✅ Cache salvo: {cache_path.name} (schema {SCHEMA_VERSION})")
        except Exception as e:
            print(f"   ⚠ Não foi possível salvar cache: {e}")
        return base
    except Exception:
        print("   ❌ Falha ao montar base de margens (retornando '—'):")
        traceback.print_exc()
        return _estrutura_vazia("Falha na coleta CONAB/CEPEA.")


if __name__ == "__main__":
    print("=" * 64)
    print("EARLY SIGNALS · modulo_margem_agricola v2.1 (teste standalone)")
    print("=" * 64)
    dados = processar_margem_agricola()
    r = dados["resumo_qualidade"]
    print(f"Qualidade: {r['completos']} completos | {r['parciais']} parciais | "
          f"{r['incompletos']} incompletos (de {r['total']} pontos).")
