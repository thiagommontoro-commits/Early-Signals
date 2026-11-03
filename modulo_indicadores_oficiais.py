# -*- coding: utf-8 -*-
"""
modulo_indicadores_oficiais.py   ←←← ARQUIVO NOVO (adicionar na raiz)
=====================================================================
Early Signals · Selic e Dólar com DADO OFICIAL do Banco Central (BCB/SGS)

Os cards "Juros (Selic)" e "Câmbio (Dólar)" eram escritos pela IA de memória
e traziam números errados. Agora vêm direto do BCB, e os mesmos números são
repassados à IA no prompt.

Séries (API pública, sem autenticação):
    432 -> Meta Selic definida pelo Copom (% a.a.)
    1   -> Dólar comercial PTAX venda (R$/US$)

Comparação: valor mais recente vs último valor do MÊS ANTERIOR ao dado.

Ótica da demanda por máquinas agrícolas:
    Selic subindo -> 'piorando'   | caindo -> 'melhorando'
    Dólar subindo -> 'melhorando' (receita do exportador sobe) | caindo -> 'piorando'

Robustez: 3 tentativas com backoff. Se a série não responder, o card é
omitido (nunca inventa número).

Autoria: Global Reporting & Analytics — Thiago Montoro (AGCO)
"""
from __future__ import annotations

import datetime
import json
import time
import urllib.parse
import urllib.request

URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
TENTATIVAS = 3
TIMEOUT = 30
JANELA_DIAS = 75

MESES = {
    "pt": ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
           "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"],
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
    "es": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
           "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
}


def _fmt(v, casas=2):
    return f"{v:,.{casas}f}".replace(",", "#").replace(".", ",").replace("#", ".")


def _nomes_mes(m):
    return {k: MESES[k][m - 1] for k in MESES}


def _get_serie(codigo):
    """Lista ordenada de (date, valor) dos últimos JANELA_DIAS. [] se falhar."""
    hoje = datetime.date.today()
    qs = urllib.parse.urlencode({
        "formato": "json",
        "dataInicial": (hoje - datetime.timedelta(days=JANELA_DIAS)).strftime("%d/%m/%Y"),
        "dataFinal": hoje.strftime("%d/%m/%Y"),
    })
    url = f"{URL.format(codigo=codigo)}?{qs}"
    for t in range(1, TENTATIVAS + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "EarlySignals/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                dados = json.loads(r.read().decode("utf-8"))
            pontos = []
            for it in dados or []:
                try:
                    d = datetime.datetime.strptime(it["data"], "%d/%m/%Y").date()
                    pontos.append((d, float(str(it["valor"]).replace(",", "."))))
                except (KeyError, ValueError, TypeError):
                    continue
            pontos.sort()
            return pontos
        except Exception as e:  # noqa: BLE001
            if t < TENTATIVAS:
                print(f"      ⚠ SGS {codigo}: tentativa {t}/{TENTATIVAS} falhou ({e}).")
                time.sleep(2 ** t)
            else:
                print(f"      ❌ SGS {codigo}: indisponível ({e}).")
    return []


def _atual_e_mes_anterior(pontos):
    if not pontos:
        return None
    d_at, v_at = pontos[-1]
    ini_mes = d_at.replace(day=1)
    anteriores = [p for p in pontos if p[0] < ini_mes]
    if not anteriores:
        return d_at, v_at, None, None
    d_ant, v_ant = anteriores[-1]
    return d_at, v_at, d_ant, v_ant


def _card_selic():
    r = _atual_e_mes_anterior(_get_serie(432))
    if not r:
        return None, None
    d_at, v_at, d_ant, v_ant = r
    mes_cmp = _nomes_mes(d_ant.month) if d_ant else None
    delta = round(v_at - v_ant, 2) if v_ant is not None else None

    if delta is None or abs(delta) < 0.01:
        direcao, tendencia = "estavel", ("alta" if v_at >= 12 else "estavel")
        var = f", mantida ante {mes_cmp['pt']}" if mes_cmp else ""
        impactos = ("Selic inalterada mantém custo do capital elevado; compra de tratores "
                    "alta potência e colheitadeiras segue dependente de linhas subsidiadas."
                    if v_at >= 12 else
                    "Selic inalterada; decisão de compra de tratores e colheitadeiras segue neutra.")
    elif delta > 0:
        direcao, tendencia = "piorando", "alta"
        var = f", alta de {_fmt(delta)} p.p. ante {mes_cmp['pt']}"
        impactos = ("Alta da Selic encarece crédito livre e adia compra de tratores alta "
                    "potência e colheitadeiras Classes 7+.")
    else:
        direcao, tendencia = "melhorando", "baixa"
        var = f", corte de {_fmt(abs(delta))} p.p. ante {mes_cmp['pt']}"
        impactos = ("Corte da Selic barateia crédito livre e tende a acelerar compra de "
                    "tratores e colheitadeiras.")

    ref = d_at.strftime("%d/%m/%Y")
    card = {
        "titulo": "Juros (Selic)", "icone": "💰",
        "tendencia": tendencia, "direcao": direcao,
        "descricao": f"Meta Selic em {_fmt(v_at)}% a.a. (vigente em {ref}){var}.",
        "impactos": impactos,
        "fonte": "BCB/SGS série 432 (Meta Selic — Copom)",
    }
    if mes_cmp:
        card["mes_comparacao"] = mes_cmp
    ctx = f"Meta Selic: {_fmt(v_at)}% a.a. em {ref}" + (
        f" (fim de {mes_cmp['pt']}: {_fmt(v_ant)}% a.a.)" if v_ant is not None else "")
    print(f"   ✅ Selic: {_fmt(v_at)}% ({ref}) | direção {direcao}")
    return card, ctx


def _card_dolar():
    r = _atual_e_mes_anterior(_get_serie(1))
    if not r:
        return None, None
    d_at, v_at, d_ant, v_ant = r
    mes_cmp = _nomes_mes(d_ant.month) if d_ant else None
    pct = round((v_at / v_ant - 1) * 100, 1) if v_ant else None

    if pct is None or abs(pct) < 1.0:
        direcao, tendencia = "estavel", "estavel"
        var = (f", estável ({'+' if (pct or 0) >= 0 else ''}{_fmt(pct or 0, 1)}%) ante {mes_cmp['pt']}"
               if mes_cmp else "")
        impactos = ("Câmbio estável preserva receita do exportador e preço de máquinas "
                    "importadas; demanda por tratores e colheitadeiras segue neutra.")
    elif pct > 0:
        direcao, tendencia = "melhorando", "positivo"
        var = f", alta de {_fmt(pct, 1)}% ante {mes_cmp['pt']}"
        impactos = ("Dólar mais alto eleva receita em R$ do produtor de grãos e favorece "
                    "compra de colheitadeiras e tratores; encarece componentes importados.")
    else:
        direcao, tendencia = "piorando", "negativo"
        var = f", queda de {_fmt(abs(pct), 1)}% ante {mes_cmp['pt']}"
        impactos = ("Dólar mais baixo reduz receita em R$ do exportador de grãos e tende a "
                    "adiar compra de colheitadeiras e tratores alta potência.")

    ref = d_at.strftime("%d/%m/%Y")
    card = {
        "titulo": "Câmbio (Dólar)", "icone": "💵",
        "tendencia": tendencia, "direcao": direcao,
        "descricao": f"Dólar PTAX em R$ {_fmt(v_at, 4)} ({ref}){var}.",
        "impactos": impactos,
        "fonte": "BCB/SGS série 1 (PTAX venda)",
    }
    if mes_cmp:
        card["mes_comparacao"] = mes_cmp
    ctx = f"Dólar PTAX venda: R$ {_fmt(v_at, 4)} em {ref}" + (
        f" (fim de {mes_cmp['pt']}: R$ {_fmt(v_ant, 4)})" if v_ant is not None else "")
    print(f"   ✅ Dólar: R$ {_fmt(v_at, 4)} ({ref}) | direção {direcao}")
    return card, ctx


def obter_indicadores_oficiais():
    """Retorna (cards, contexto_para_prompt)."""
    print("Buscando indicadores oficiais BCB (Selic SGS 432, Dólar SGS 1)...")
    cards, ctx = [], []
    for fn in (_card_selic, _card_dolar):
        c, t = fn()
        if c:
            cards.append(c)
        if t:
            ctx.append(t)
    return cards, ctx


if __name__ == "__main__":
    cards, ctx = obter_indicadores_oficiais()
    print(json.dumps(cards, ensure_ascii=False, indent=2))
