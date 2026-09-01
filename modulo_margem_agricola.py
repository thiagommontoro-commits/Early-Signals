# -*- coding: utf-8 -*-
"""
modulo_margem_agricola.py  (v3.0 — COE/COT/CT + Margem Bruta & Econômica)
========================================================================
Aba "Margem do Produtor" do Early Signals, agora seguindo a metodologia
oficial de custos da CONAB (COE / COT / CT) e expondo TRÊS indicadores por
safra, alinhados à leitura executiva de demanda de máquinas AGCO:

    Receita Bruta (R$/ha)    = Produtividade (comercial) x Preço CEPEA
    Margem Bruta (R$/ha)     = Receita Bruta - COE   (gera caixa?)
    Margem Econômica (R$/ha) = Receita Bruta - CT    (remunera terra+capital?)

Hierarquia de custo CONAB (verificada empiricamente em 01/09/2026 contra o
próprio 'coe' calculado pelo agrobr, com casamento exato para soja, algodão
e trigo):

    COE (Custo Operacional Efetivo) = desembolso de caixa (insumos, operações,
        agrotóxicos, transporte, armazenagem, assistência, CESSR, juros,
        aluguel de máquinas, mão de obra, administrador, seguro da produção...)
    COT (Custo Operacional Total)   = COE + Depreciações + Outros Custos Fixos
        (manutenção periódica, seguro do capital fixo, encargos sociais,
         arrendamento)
    CT  (Custo Total)               = COT + Renda de Fatores
        (remuneração esperada sobre o capital fixo + terra própria)

    => CT  = soma de TODAS as linhas de DETALHE da CONAB (itens numerados).
    => COT = CT  - Renda de Fatores
    => COE = COT - (Depreciações + Outros Custos Fixos)

A classificação é feita por NOME do item (robusta à variação de numeração
entre culturas — ex.: o milho não traz linhas de subtotal). Foi validada
com casamento EXATO do COE contra o agrobr:
    soja 4347.41 | algodão 8508.69 | trigo 3096.11  (milho: agrobr subestima
    1246.00 porque ignora custos de caixa; nossa reconstrução dá 1956.90,
    coerente com a planilha).

FONTES:
    - CUSTO ......... CONAB · conab.custo_producao()  (série histórica)
    - PRODUTIVIDADE . CONAB · conab.safras()  [boletim: SÓ safra vigente +
                      anterior; safras mais antigas não existem na fonte]
    - PREÇO ......... CEPEA/ESALQ · cepea.indicador()

>>> LIMITAÇÃO DE HISTÓRICO (confirmada por diagnóstico com dado real em
    01/09/2026): o boletim de safra da CONAB só disponibiliza produtividade
    para a safra vigente e a imediatamente anterior. Por isso a série de
    MARGEM cobre 2 safras (comparação ano-a-ano). Custo e preço têm histórico
    longo, mas sem produtividade não há margem — logo N_SAFRAS = 2. Nada é
    inventado para preencher lacunas.

HISTÓRICO DE VERSÕES:
    v2.4 - guard de sanidade (faixa plausível por cultura).
    v2.5 - correção de custo: exclui linhas de SUBTOTAL da CONAB (que eram
           somadas junto com as de detalhe, inflando o custo).
    v2.6 - correção do algodão: fator caroço->pluma (~0.40), pois a CONAB
           reporta caroço e o CEPEA precifica pluma.
    v3.0 - metodologia CONAB COE/COT/CT + 3 indicadores (Receita Bruta,
           Margem Bruta, Margem Econômica); histórico ajustado a 2 safras
           (limite real da fonte de produtividade). SCHEMA incrementado.

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
import re
import json
import asyncio
import datetime
import traceback
from pathlib import Path

# >>> v3.0: nova estrutura de 'ponto' (coe/cot/ct + 3 margens) => novo schema.
SCHEMA_VERSION = "3.0"

# Faixas plausíveis de MARGEM ECONÔMICA (R$/ha) por cultura — para-choque
# contra erros grosseiros de unidade/conversão. NÃO são limites agronômicos.
FAIXAS_PLAUSIVEIS_MARGEM_HA = {
    "Soja":    (-6000, 9000),
    "Milho":   (-6000, 9000),
    "Algodão": (-10000, 22000),
    "Trigo":   (-5000, 7000),
    "Café":    (-12000, 32000),
}

# ---------------------------------------------------------------------------
# Classificação de itens de custo por NOME (metodologia CONAB), validada
# contra o coe do agrobr. Case-insensitive; ignora acentuação irrelevante.
# ---------------------------------------------------------------------------
_ITENS_RENDA_FATORES = ("remuneração esperada sobre o capital", "terra própria")
_ITENS_OUTROS_FIXOS = ("manutenção periódica", "seguro do capital fixo",
                        "encargos sociais", "arrendamento")
_MARCA_DEPRECIACAO = "depreciação"

# Linha de DETALHE começa com código numérico ("8 -", "3.1 -", "16.1 -").
# Linha de SUBTOTAL começa com texto ("TOTAL DE...", "CUSTO FIXO...").
_PADRAO_ITEM_DETALHE = re.compile(r"^\s*\d+(\.\d+)?\s*-")


def _eh_linha_de_detalhe(item_texto):
    if not item_texto:
        return False
    return bool(_PADRAO_ITEM_DETALHE.match(str(item_texto)))


def _classe_custo(item_texto):
    """Classifica um item de detalhe da CONAB em uma das camadas de custo:
    'RF' (renda de fatores) | 'DEP' (depreciação) | 'OCF' (outros custos
    fixos) | 'COE' (custo operacional efetivo / caixa)."""
    t = str(item_texto).lower()
    if any(k in t for k in _ITENS_RENDA_FATORES):
        return "RF"
    if _MARCA_DEPRECIACAO in t:
        return "DEP"
    if any(k in t for k in _ITENS_OUTROS_FIXOS):
        return "OCF"
    return "COE"


# Fator caroço->pluma do algodão (v2.6): a CONAB reporta algodão em caroço,
# o CEPEA precifica a pluma (~40% do peso). Grãos = 1.0.
_FATOR_PLUMA_ALGODAO = 0.40

# >>> COBERTURA MÁXIMA DE CULTURAS × UF.
# Estratégia: incluir o maior número de combinações plausíveis (grãos e fibras,
# nas principais UFs produtoras). Como a MARGEM exige as 3 fontes (custo CONAB +
# produtividade do boletim de grãos + preço CEPEA), combinações cuja fonte não
# responder serão AUTO-OCULTADAS (ver OCULTAR_CARDS_VAZIOS) — assim o painel
# nunca mostra cartão vazio/inventado, mas exibe tudo que tiver dado real.
#
# 'sc_por_t' converte t/ha -> unidade comercial: 16.667 para saca de 60 kg;
# 66.667 para arroba de 15 kg (algodão em pluma). 'fator_comercial' ajusta a
# base física->comercial (algodão caroço->pluma ≈ 0.40; grãos = 1.0).
_ALIASES_CAFE_MG = {"conab": ["cafe", "cafe_arabica", "arabica"], "cepea": ["cafe_arabica", "cafe", "arabica"]}
_ALIASES_CAFE_ES = {"conab": ["cafe", "cafe_conilon", "conilon", "robusta"], "cepea": ["cafe_conilon", "cafe", "conilon", "robusta"]}


def _combo(cultura, uf, conab, cepea, unid="sc60", sc_por_t=16.667, fator=1.0):
    return {"cultura": cultura, "uf": uf, "conab": conab, "cepea": cepea,
            "unid": unid, "sc_por_t": sc_por_t, "fator_comercial": fator}


COMBINACOES = [
    # ---- SOJA (principais UFs produtoras) ----
    _combo("Soja", "MT", "soja", "soja"),
    _combo("Soja", "PR", "soja", "soja"),
    _combo("Soja", "RS", "soja", "soja"),
    _combo("Soja", "GO", "soja", "soja"),
    _combo("Soja", "MS", "soja", "soja"),
    _combo("Soja", "BA", "soja", "soja"),
    # ---- MILHO ----
    _combo("Milho", "MT", "milho", "milho"),
    _combo("Milho", "PR", "milho", "milho"),
    _combo("Milho", "RS", "milho", "milho"),
    _combo("Milho", "GO", "milho", "milho"),
    _combo("Milho", "MS", "milho", "milho"),
    # ---- ALGODÃO (caroço->pluma) ----
    _combo("Algodão", "MT", "algodao", "algodao", unid="arroba", sc_por_t=66.667, fator=_FATOR_PLUMA_ALGODAO),
    _combo("Algodão", "BA", "algodao", "algodao", unid="arroba", sc_por_t=66.667, fator=_FATOR_PLUMA_ALGODAO),
    # ---- TRIGO ----
    _combo("Trigo", "PR", "trigo", "trigo"),
    _combo("Trigo", "RS", "trigo", "trigo"),
    # ---- ARROZ ----
    _combo("Arroz", "RS", "arroz", "arroz"),
    _combo("Arroz", "TO", "arroz", "arroz"),
    # ---- FEIJÃO ----
    _combo("Feijão", "PR", "feijao", "feijao"),
    _combo("Feijão", "GO", ["feijao", "feijao_cores"], ["feijao", "feijao_cores"]),
    # ---- SORGO (grão) ----
    _combo("Sorgo", "GO", "sorgo", ["sorgo", "milho"]),
    # ---- GIRASSOL ----
    _combo("Girassol", "MT", "girassol", ["girassol", "soja"]),
    # ---- AMENDOIM ----
    _combo("Amendoim", "SP", "amendoim", ["amendoim"]),
    # ---- CEVADA / AVEIA / CANOLA / TRITICALE (inverno, sul) ----
    _combo("Cevada", "PR", "cevada", ["cevada", "trigo"]),
    _combo("Aveia", "RS", "aveia", ["aveia", "trigo"]),
    _combo("Canola", "RS", "canola", ["canola", "soja"]),
    # ---- CAFÉ (candidato; produtividade pode não vir do boletim de grãos) ----
    _combo("Café", "MG", _ALIASES_CAFE_MG["conab"], _ALIASES_CAFE_MG["cepea"]),
    _combo("Café", "ES", _ALIASES_CAFE_ES["conab"], _ALIASES_CAFE_ES["cepea"]),
]

# Se True, cartões cuja série NÃO tem nenhuma margem econômica (todas as safras
# incompletas por falta de dado real) são REMOVIDOS do painel, evitando poluir
# com "—". Combinações com pelo menos 1 safra válida permanecem.
OCULTAR_CARDS_VAZIOS = True

# >>> Histórico limitado a 2 safras: a produtividade do boletim CONAB só
# existe para a safra vigente e a anterior (ver docstring). Não inventamos.
N_SAFRAS = 2
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
    return list(valor) if isinstance(valor, (list, tuple)) else [valor]


async def _custos_coe_cot_ct(conab, cultura_conab, uf, safra):
    """Retorna dict {'coe','cot','ct'} (R$/ha) seguindo a metodologia CONAB,
    ou None se a fonte não retornar dados. Usa cascata de aliases.

    CT  = soma das linhas de DETALHE (exclui subtotais duplicados da CONAB).
    COT = CT  - Renda de Fatores.
    COE = COT - (Depreciações + Outros Custos Fixos).
    """
    candidatos = _como_lista(cultura_conab)
    for i, nome in enumerate(candidatos):
        try:
            df = await conab.custo_producao(nome, uf=uf, safra=safra)
            if df is None or len(df) == 0 or "valor_ha" not in getattr(df, "columns", []):
                if len(candidatos) > 1:
                    print(f"      ↳ custo: alias '{nome}' sem dados, tentando próximo...")
                continue
            if "item" not in getattr(df, "columns", []):
                # Sem coluna 'item' não dá para classificar; usa soma bruta como CT.
                ct = float(df["valor_ha"].dropna().sum())
                if ct > 0:
                    return {"coe": None, "cot": None, "ct": round(ct, 2)}
                continue

            det = df[df["item"].apply(_eh_linha_de_detalhe)].copy()
            n_sub = len(df) - len(det)
            if len(det) == 0:
                print(f"      ⚠ custo: nenhuma linha de detalhe reconhecida "
                      f"('{nome}' {uf}/{safra}).")
                continue
            if n_sub > 0:
                print(f"      ℹ custo: {n_sub} subtotal(is) excluído(s) "
                      f"('{nome}' {uf}/{safra}).")

            det["_classe"] = det["item"].apply(_classe_custo)
            somas = det.groupby("_classe")["valor_ha"].sum().to_dict()
            coe = float(somas.get("COE", 0.0))
            dep = float(somas.get("DEP", 0.0))
            ocf = float(somas.get("OCF", 0.0))
            rf = float(somas.get("RF", 0.0))
            ct = coe + dep + ocf + rf
            cot = coe + dep + ocf
            if ct <= 0:
                continue
            if i > 0:
                print(f"      ✅ custo resolvido via alias '{nome}' ({uf}/{safra})")
            return {"coe": round(coe, 2), "cot": round(cot, 2), "ct": round(ct, 2)}
        except Exception as e:
            print(f"      ⚠ custo indisponível via alias '{nome}' ({uf}/{safra}): {e}")
            continue
    if len(candidatos) > 1:
        print(f"      ❌ custo indisponível para todos os aliases {candidatos} ({uf}/{safra})")
    return None


async def _produtividade_sc_ha(conab, cultura_conab, uf, safra, sc_por_t, fator_comercial=1.0):
    """Produtividade em unidade COMERCIAL (sc/ha ou @/ha). 'fator_comercial'
    converte a base física da CONAB para a base do preço CEPEA (grãos=1.0;
    algodão≈0.40 caroço->pluma). Cascata de aliases."""
    candidatos = _como_lista(cultura_conab)
    for i, nome in enumerate(candidatos):
        try:
            df = await conab.safras(nome, safra=safra, uf=uf)
            if df is None or len(df) == 0 or "produtividade" not in getattr(df, "columns", []):
                if len(candidatos) > 1:
                    print(f"      ↳ produtividade: alias '{nome}' sem dados, tentando próximo...")
                continue
            valor = round(float(df.iloc[0]["produtividade"]) / 1000.0 * sc_por_t * fator_comercial, 1)
            if fator_comercial != 1.0:
                print(f"      ℹ produtividade ajustada (fator {fator_comercial}, caroço->pluma) "
                      f"'{nome}' {uf}/{safra} -> {valor}")
            if i > 0:
                print(f"      ✅ produtividade resolvida via alias '{nome}' ({uf}/{safra})")
            return valor
        except Exception as e:
            print(f"      ⚠ produtividade indisponível via alias '{nome}' ({uf}/{safra}): {e}")
            continue
    if len(candidatos) > 1:
        print(f"      ❌ produtividade indisponível para todos os aliases {candidatos} ({uf}/{safra})")
    return None


async def _preco_medio(cepea, produto, safra):
    """Preço médio CEPEA na janela da safra (set->ago). Cascata de aliases."""
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
                print(f"      ✅ preço resolvido via alias '{nome}' (safra {safra})")
            return valor
        except Exception as e:
            print(f"      ⚠ preço indisponível via alias '{nome}' ({safra}): {e}")
            continue
    if len(candidatos) > 1:
        print(f"      ❌ preço indisponível para todos os aliases {candidatos} ({safra})")
    return None


def _tendencia(serie, chave="margem_economica_ha"):
    """Tendência ano-a-ano baseada na Margem Econômica (padrão)."""
    if len(serie) < 2:
        return "indisponivel", None
    atual, ant = serie[-1].get(chave), serie[-2].get(chave)
    if atual is None or ant is None or ant == 0:
        return "indisponivel", None
    delta = (atual - ant) / abs(ant) * 100.0
    if delta > 3:
        return "alta", round(delta, 1)
    if delta < -3:
        return "baixa", round(delta, 1)
    return "estavel", round(delta, 1)


def _flag(valor, valor_anterior):
    if valor is None:
        return "indisponivel"
    if valor_anterior is not None and abs(valor - valor_anterior) < 0.01:
        return "repetido"
    return "oficial"


def _status_geral(ponto):
    if ponto.get("margem_economica_ha") is None:
        return "incompleto"
    flags = (ponto["custo_status"], ponto["produtividade_status"], ponto["preco_status"])
    if "repetido" in flags:
        return "parcial"
    return "completo"


def _checar_sanidade(cultura, margem_ha):
    if margem_ha is None:
        return False, None
    faixa = FAIXAS_PLAUSIVEIS_MARGEM_HA.get(cultura)
    if faixa is None:
        return False, None
    minimo, maximo = faixa
    if margem_ha < minimo or margem_ha > maximo:
        return True, (f"Margem econômica R$ {margem_ha:,.0f}/ha fora da faixa plausível "
                      f"[{minimo:,.0f}, {maximo:,.0f}] para {cultura} "
                      f"— verificar coleta/conversão.").replace(",", ".")
    return False, None


async def _montar_base_async():
    from agrobr import conab, cepea

    safras = ultimas_safras()
    print(f"   📅 Safras comparadas: {safras}")

    cards = []
    for combo in COMBINACOES:
        print(f"   🌱 {combo['cultura']} · {combo['uf']}")
        serie = []
        prev_ct = prev_prod = prev_preco = None
        for safra in safras:
            custos = await _custos_coe_cot_ct(conab, combo["conab"], combo["uf"], safra)
            prod = await _produtividade_sc_ha(conab, combo["conab"], combo["uf"], safra,
                                              combo["sc_por_t"], combo.get("fator_comercial", 1.0))
            preco = await _preco_medio(cepea, combo["cepea"], safra)

            coe = custos["coe"] if custos else None
            cot = custos["cot"] if custos else None
            ct = custos["ct"] if custos else None

            custo_status = _flag(ct, prev_ct)
            prod_status = _flag(prod, prev_prod)
            preco_status = _flag(preco, prev_preco)

            receita = round(prod * preco, 2) if (prod is not None and preco is not None) else None
            margem_bruta = round(receita - coe, 2) if (receita is not None and coe is not None) else None
            margem_econ = round(receita - ct, 2) if (receita is not None and ct is not None) else None

            ponto = {
                "safra": safra,
                "coe_ha": coe, "cot_ha": cot, "ct_ha": ct, "custo_status": custo_status,
                "produtividade": prod, "produtividade_status": prod_status,
                "preco_medio": preco, "preco_status": preco_status,
                "receita_ha": receita,
                "margem_bruta_ha": margem_bruta,
                "margem_economica_ha": margem_econ,
            }
            ponto["status_geral"] = _status_geral(ponto)

            alerta, motivo = _checar_sanidade(combo["cultura"], margem_econ)
            ponto["alerta_valor"] = alerta
            ponto["alerta_motivo"] = motivo
            if alerta:
                print(f"      🚩 ALERTA ({combo['cultura']}/{combo['uf']}/{safra}): {motivo}")

            serie.append(ponto)
            prev_ct, prev_prod, prev_preco = ct, prod, preco

        tendencia, delta_pct = _tendencia(serie)
        cards.append({
            "cultura": combo["cultura"], "uf": combo["uf"], "unidade": combo["unid"],
            "serie": serie, "tendencia": tendencia, "delta_pct": delta_pct,
        })

    # Auto-ocultação: remove cartões sem NENHUMA margem econômica real (todas as
    # safras incompletas). Mantém no painel apenas culturas com dado verificável.
    if OCULTAR_CARDS_VAZIOS:
        antes = len(cards)
        cards_visiveis = [c for c in cards
                          if any(p.get("margem_economica_ha") is not None for p in c["serie"])]
        ocultos = antes - len(cards_visiveis)
        if ocultos:
            nomes = ", ".join(f"{c['cultura']}/{c['uf']}" for c in cards
                              if all(p.get("margem_economica_ha") is None for p in c["serie"]))
            print(f"   👁 {ocultos} cartão(ões) sem dado real ocultado(s): {nomes}")
        cards = cards_visiveis

    return _empacotar(cards, safras)


def _empacotar(cards, safras):
    total = sum(len(c["serie"]) for c in cards)
    completos = sum(1 for c in cards for p in c["serie"] if p["status_geral"] == "completo")
    parciais = sum(1 for c in cards for p in c["serie"] if p["status_geral"] == "parcial")
    incompletos = sum(1 for c in cards for p in c["serie"] if p["status_geral"] == "incompleto")
    suspeitos = sum(1 for c in cards for p in c["serie"] if p.get("alerta_valor"))
    return {
        "schema_version": SCHEMA_VERSION,
        "n_combinacoes": len(cards),
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "safras": safras,
        "metodologia": ("Receita Bruta = Produtividade x Preço CEPEA. "
                        "Margem Bruta = Receita - COE. Margem Econômica = Receita - CT. "
                        "COE/COT/CT conforme metodologia de custos da CONAB."),
        "fontes": {
            "custo": "CONAB - Custos de Produção (COE/COT/CT)",
            "produtividade": "CONAB - Boletim de Safra (GEASA) — vigente + anterior",
            "preco": "CEPEA/ESALQ",
        },
        "resumo_qualidade": {
            "total": total, "completos": completos,
            "parciais": parciais, "incompletos": incompletos,
            "suspeitos": suspeitos,
        },
        "autoria": "Global Reporting & Analytics — Thiago Montoro (AGCO)",
        "cards": cards,
    }


def _cache_valido(dados):
    if not isinstance(dados, dict):
        return False
    if dados.get("schema_version") != SCHEMA_VERSION:
        return False
    cards = dados.get("cards")
    if not isinstance(cards, list) or not cards:
        return False
    chaves = {"status_geral", "custo_status", "produtividade_status",
              "preco_status", "alerta_valor", "coe_ha", "ct_ha",
              "margem_bruta_ha", "margem_economica_ha"}
    for c in cards:
        for p in c.get("serie", []):
            if not chaves.issubset(p.keys()):
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
                "coe_ha": None, "cot_ha": None, "ct_ha": None, "custo_status": "indisponivel",
                "produtividade": None, "produtividade_status": "indisponivel",
                "preco_medio": None, "preco_status": "indisponivel",
                "receita_ha": None, "margem_bruta_ha": None, "margem_economica_ha": None,
                "status_geral": "incompleto", "alerta_valor": False, "alerta_motivo": None,
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
    print("EARLY SIGNALS · modulo_margem_agricola v3.0 (teste standalone)")
    print("=" * 64)
    dados = processar_margem_agricola()
    r = dados["resumo_qualidade"]
    print(f"Qualidade: {r['completos']} completos | {r['parciais']} parciais | "
          f"{r['incompletos']} incompletos | {r.get('suspeitos',0)} suspeitos "
          f"(de {r['total']} pontos).")
