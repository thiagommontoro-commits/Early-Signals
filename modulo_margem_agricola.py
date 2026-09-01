# -*- coding: utf-8 -*-
"""
modulo_margem_agricola.py  (v3.4 — safra anterior no dash + comparativo a/a)
===========================================================================
Aba "Margem do Produtor" do Early Signals (metodologia CONAB COE/COT/CT):

    Receita Bruta (R$/ha)    = Produtividade (comercial) x Preço CEPEA
    Margem Bruta (R$/ha)     = Receita Bruta - COE
    Margem Econômica (R$/ha) = Receita Bruta - CT

>>> CORREÇÃO v3.4 (causa raiz do comparativo ausente):
    A v3.3 alimentava o comparativo ano-a-ano a partir de _pontos_confiaveis(),
    que EXCLUÍA qualquer ponto marcado com alerta. Resultado: quando 2024/25
    recebia um alerta intermediário (ou quando a decisão de remover a cultura
    dependia só do ponto vigente), o ponto de 2024/25 era descartado e o
    comparativo "25/26 vs 24/25" sumia — mesmo com o dado existindo na CONAB.

    Agora a lógica é separada em DUAS decisões independentes:
      (A) MANTER OU REMOVER O CARTÃO INTEIRO: decidido SÓ pelo ponto vigente
          (safra mais recente). Se a margem/COE/CT vigente for irreal, a
          cultura inteira sai do relatório (ex.: Algodão MT, Trigo PR, Milho PR).
      (B) COMPARATIVO ANO-A-ANO: dentro de um cartão MANTIDO, usa os DOIS
          últimos pontos COM MARGEM REAL (não exige "sem alerta"), trazendo o
          2024/25 de volta ao dash. Se o 2024/25 tiver dado, o comparativo
          aparece; se não tiver, o cartão mostra "sem comparativo" — nada é
          inventado.

Fontes: CUSTO/PRODUTIVIDADE = CONAB · PREÇO = CEPEA/ESALQ.
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

SCHEMA_VERSION = "3.4"

# --- Configurações de exibição ---
REMOVER_ALERTAS = True          # remove cartão cujo ponto VIGENTE é irreal
OCULTAR_CARDS_VAZIOS = True     # remove cartão totalmente sem dado

FAIXAS_PLAUSIVEIS_MARGEM_HA = {
    "Soja":    (-6000, 9000),
    "Milho":   (-6000, 9000),
    "Algodão": (-10000, 22000),
    "Trigo":   (-5000, 7000),
    "Arroz":   (-6000, 10000),
    "Feijão":  (-6000, 12000),
    "Sorgo":   (-4000, 6000),
    "Café":    (-12000, 32000),
}

# COE fora da faixa -> quase sempre erro de parse da CONAB.
FAIXAS_PLAUSIVEIS_COE_HA = {
    "Soja":    (2000, 7000),
    "Milho":   (800, 5000),
    "Algodão": (4000, 18000),
    "Trigo":   (1200, 5500),
    "Arroz":   (2500, 12000),
    "Feijão":  (1500, 9000),
    "Sorgo":   (600, 4500),
    "Café":    (3000, 26000),
}

_ITENS_RENDA_FATORES = ("remuneração esperada sobre o capital", "terra própria")
_ITENS_OUTROS_FIXOS = ("manutenção periódica", "seguro do capital fixo",
                       "encargos sociais", "arrendamento")
_MARCA_DEPRECIACAO = "depreciação"
_PADRAO_ITEM_DETALHE = re.compile(r"^\s*\d+(\.\d+)?\s*-")


def _eh_linha_de_detalhe(item_texto):
    if not item_texto:
        return False
    return bool(_PADRAO_ITEM_DETALHE.match(str(item_texto)))


def _classe_custo(item_texto):
    t = str(item_texto).lower()
    if any(k in t for k in _ITENS_RENDA_FATORES):
        return "RF"
    if _MARCA_DEPRECIACAO in t:
        return "DEP"
    if any(k in t for k in _ITENS_OUTROS_FIXOS):
        return "OCF"
    return "COE"


_FATOR_PLUMA_ALGODAO = 0.40

_ALIASES_CAFE_MG = {"conab": ["cafe", "cafe_arabica", "arabica"],
                    "cepea": ["cafe_arabica", "cafe", "arabica"]}
_ALIASES_CAFE_ES = {"conab": ["cafe", "cafe_conilon", "conilon", "robusta"],
                    "cepea": ["cafe_conilon", "cafe", "conilon", "robusta"]}


def _combo(cultura, uf, conab, cepea, unid="sc60", sc_por_t=16.667, fator=1.0):
    return {"cultura": cultura, "uf": uf, "conab": conab, "cepea": cepea,
            "unid": unid, "sc_por_t": sc_por_t, "fator_comercial": fator}


COMBINACOES = [
    _combo("Soja", "MT", "soja", "soja"),
    _combo("Soja", "PR", "soja", "soja"),
    _combo("Soja", "GO", "soja", "soja"),
    _combo("Milho", "MT", "milho", "milho"),
    _combo("Milho", "PR", "milho", "milho"),
    _combo("Algodão", "MT", "algodao", "algodao", unid="arroba", sc_por_t=66.667, fator=_FATOR_PLUMA_ALGODAO),
    _combo("Trigo", "PR", "trigo", "trigo"),
    _combo("Arroz", "RS", "arroz", "arroz"),
    _combo("Feijão", "PR", "feijao", "feijao"),
    _combo("Sorgo", "GO", "sorgo", ["sorgo", "milho"]),
    _combo("Café", "MG", _ALIASES_CAFE_MG["conab"], _ALIASES_CAFE_MG["cepea"]),
]

COMBINACOES_EXTRAS = [
    _combo("Soja", "RS", "soja", "soja"),
    _combo("Soja", "MS", "soja", "soja"),
    _combo("Soja", "BA", "soja", "soja"),
    _combo("Milho", "GO", "milho", "milho"),
    _combo("Milho", "MS", "milho", "milho"),
    _combo("Algodão", "BA", "algodao", "algodao", unid="arroba", sc_por_t=66.667, fator=_FATOR_PLUMA_ALGODAO),
    _combo("Arroz", "TO", "arroz", "arroz"),
    _combo("Feijão", "GO", ["feijao", "feijao_cores"], ["feijao", "feijao_cores"]),
    _combo("Café", "ES", _ALIASES_CAFE_ES["conab"], _ALIASES_CAFE_ES["cepea"]),
]

N_SAFRAS = 2
PRECO_FONTE = os.getenv("EARLY_SIGNALS_PRECO_FONTE", "cepea").lower()
SCRIPT_DIR = Path(__file__).parent


def safra_vigente(hoje=None):
    """Só avança o ano-safra a partir de OUTUBRO (mês >= 10). Ex.: ago/2026 -> '2025/26'."""
    hoje = hoje or datetime.date.today()
    ini = hoje.year if hoje.month >= 10 else hoje.year - 1
    return f"{ini}/{str(ini + 1)[-2:]}"


def ultimas_safras(n=N_SAFRAS, hoje=None):
    ini = int(safra_vigente(hoje).split("/")[0])
    return [f"{ini - k}/{str(ini - k + 1)[-2:]}" for k in range(n - 1, -1, -1)]


def _como_lista(valor):
    return list(valor) if isinstance(valor, (list, tuple)) else [valor]


async def _custos_coe_cot_ct(conab, cultura_conab, uf, safra):
    candidatos = _como_lista(cultura_conab)
    for i, nome in enumerate(candidatos):
        try:
            df = await conab.custo_producao(nome, uf=uf, safra=safra)
            if df is None or len(df) == 0 or "valor_ha" not in getattr(df, "columns", []):
                if len(candidatos) > 1:
                    print(f"      ↳ custo: alias '{nome}' sem dados, tentando próximo...")
                continue
            if "item" not in getattr(df, "columns", []):
                ct = float(df["valor_ha"].dropna().sum())
                if ct > 0:
                    return {"coe": None, "cot": None, "ct": round(ct, 2)}
                continue

            det = df[df["item"].apply(_eh_linha_de_detalhe)].copy()
            n_sub = len(df) - len(det)
            if len(det) == 0:
                print(f"      ⚠ custo: nenhuma linha de detalhe reconhecida ('{nome}' {uf}/{safra}).")
                continue
            if n_sub > 0:
                print(f"      ℹ custo: {n_sub} subtotal(is) excluído(s) ('{nome}' {uf}/{safra}).")

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


def _pontos_com_margem(serie, chave="margem_economica_ha"):
    """Pontos que têm margem REAL (independe de alerta) — base do comparativo."""
    return [p for p in serie if p.get(chave) is not None]


def _tendencia(serie, chave="margem_economica_ha"):
    """v3.4: comparativo entre os DOIS últimos pontos COM MARGEM REAL (não
    exige 'sem alerta'), para não perder o 2024/25."""
    validos = _pontos_com_margem(serie, chave)
    if len(validos) < 2:
        return "indisponivel", None
    atual, ant = validos[-1].get(chave), validos[-2].get(chave)
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


def _checar_sanidade(cultura, margem_ha, coe_ha=None, ct_ha=None):
    faixa_coe = FAIXAS_PLAUSIVEIS_COE_HA.get(cultura)
    if coe_ha is not None and faixa_coe:
        mn, mx = faixa_coe
        if coe_ha < mn or coe_ha > mx:
            return True, (f"COE R$ {coe_ha:,.0f}/ha fora da faixa plausível "
                          f"[{mn:,.0f}, {mx:,.0f}] para {cultura} — provável erro de "
                          f"coleta/parse do custo.").replace(",", ".")
    if margem_ha is None:
        return False, None
    faixa = FAIXAS_PLAUSIVEIS_MARGEM_HA.get(cultura)
    if faixa is None:
        return False, None
    mn, mx = faixa
    if margem_ha < mn or margem_ha > mx:
        return True, (f"Margem econômica R$ {margem_ha:,.0f}/ha fora da faixa plausível "
                      f"[{mn:,.0f}, {mx:,.0f}] para {cultura} — provável erro de "
                      f"coleta/conversão (preço/produtividade).").replace(",", ".")
    return False, None


async def _montar_base_async():
    from agrobr import conab, cepea

    safras = ultimas_safras()
    print(f"   📅 Safras comparadas: {safras}")
    print(f"   ⏱ Processando {len(COMBINACOES)} combinações (tempo estimado ~{len(COMBINACOES)*2.5:.0f} min)")

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

            alerta, motivo = _checar_sanidade(combo["cultura"], margem_econ, coe, ct)
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

    cards = _filtrar_cards(cards)
    return _empacotar(cards, safras)


def _ponto_vigente(serie):
    """Último ponto COM margem real (a safra mais recente exibível)."""
    validos = _pontos_com_margem(serie)
    return validos[-1] if validos else None


def _filtrar_cards(cards):
    """Regras de exibição (v3.4):
       - remove cartões totalmente vazios;
       - remove um cartão APENAS se o ponto VIGENTE for irreal (alerta).
         O comparativo com 2024/25 é preservado em todos os cartões mantidos.
    """
    antes = len(cards)

    if OCULTAR_CARDS_VAZIOS:
        cards = [c for c in cards if _pontos_com_margem(c["serie"])]

    if REMOVER_ALERTAS:
        limpos, removidos = [], []
        for c in cards:
            vig = _ponto_vigente(c["serie"])
            if vig is not None and vig.get("alerta_valor"):
                removidos.append(f"{c['cultura']}/{c['uf']}")
            else:
                limpos.append(c)
        if removidos:
            print(f"   🗑 {len(removidos)} cartão(ões) removido(s) por valor irreal (safra vigente): "
                  f"{', '.join(removidos)}")
        cards = limpos

    n_comp = sum(1 for c in cards if len(_pontos_com_margem(c["serie"])) >= 2)
    print(f"   ✅ Cartões finais: {len(cards)} (de {antes}) · {n_comp} com comparativo 24/25 vs 25/26")
    return cards


def _empacotar(cards, safras):
    total = sum(len(c["serie"]) for c in cards)
    completos = sum(1 for c in cards for p in c["serie"] if p["status_geral"] == "completo")
    parciais = sum(1 for c in cards for p in c["serie"] if p["status_geral"] == "parcial")
    incompletos = sum(1 for c in cards for p in c["serie"] if p["status_geral"] == "incompleto")
    com_comparativo = sum(1 for c in cards if len(_pontos_com_margem(c["serie"])) >= 2)
    return {
        "schema_version": SCHEMA_VERSION,
        "n_combinacoes": len(cards),
        "n_com_comparativo": com_comparativo,
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
    base = _empacotar([], safras)
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
    print("EARLY SIGNALS · modulo_margem_agricola v3.4 (teste standalone)")
    print("=" * 64)
    dados = processar_margem_agricola()
    print(f"Cartões: {dados['n_combinacoes']} | Com comparativo 24/25 vs 25/26: "
          f"{dados.get('n_com_comparativo', 0)}")
