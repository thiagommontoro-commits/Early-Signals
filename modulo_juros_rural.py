# -*- coding: utf-8 -*-
"""
modulo_juros_rural.py   ←←← SUBSTITUI a versão anterior deste arquivo
======================================================================
Early Signals · Taxas de Juros do Crédito Rural (Pessoa Física e Pessoa Jurídica)

Fonte: Banco Central do Brasil (BCB) — Sistema Gerenciador de Séries Temporais
(SGS), a MESMA usada pelo módulo de inadimplência.
    20771 -> Juros · Pessoa Física   · Crédito rural total (% a.a.)
    20760 -> Juros · Pessoa Jurídica · Crédito rural total (% a.a.)

>>> POR QUE ESTA VERSÃO (correção de "card sumiu"):
    Na versão anterior, se a chamada à API falhasse (timeout, 429, 500) ou
    devolvesse menos de 2 pontos, o card era simplesmente OMITIDO — foi o que
    fez o card de Juros PJ desaparecer do dashboard. Agora:

    1. RETRIES com backoff exponencial (3 tentativas por série).
    2. ENDPOINT ALTERNATIVO: se '/dados/ultimos/N' falhar, tenta a consulta
       por intervalo de datas (últimos ~18 meses) e usa os 2 últimos pontos.
    3. TOLERÂNCIA A 1 PONTO: se só houver 1 leitura, o card AINDA é exibido
       (sem o selo de comparação) em vez de sumir da tela.
    4. LOGS EXPLÍCITOS no Action, mostrando qual tentativa funcionou.

    O card só é omitido no caso extremo de a série não devolver NENHUM dado —
    e, mesmo assim, com aviso claro no log (nunca inventa número).

>>> COMPARAÇÃO MÊS A MÊS: sempre entre os DOIS ÚLTIMOS PONTOS REAIS da série,
    nunca contra o mês do calendário. O BCB publica com defasagem: em setembro
    o dado mais recente pode ser de julho — nesse caso a comparação correta é
    JULHO vs JUNHO ("vs Junho"). Quando sair agosto, vira "vs Julho", e assim
    por diante, automaticamente. O campo 'mes_comparacao' informa isso ao
    gerador, que escreve o selo.

Contrato do card (igual ao usado em 'gerar_bloco_analises'):
    { "titulo", "icone", "tendencia", "direcao", "descricao", "impactos",
      "fonte", "mes_comparacao" }

Direção julgada sob a ótica da demanda por máquinas agrícolas:
    juros caindo  -> 'melhorando'   |  juros subindo -> 'piorando'
    variação < 0,05 p.p.            -> 'estavel'

Autoria: Global Reporting & Analytics — Thiago Montoro (AGCO)
"""
from __future__ import annotations

import datetime
import time

import requests

URL_ULTIMOS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}"
URL_PERIODO = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
HEADERS = {"User-Agent": "AGCO-Early-Signals/1.0 (+juros-credito-rural)"}
TIMEOUT = 60
TENTATIVAS = 3

# Limiar (p.p.) abaixo do qual a variação mensal é considerada irrelevante.
LIMIAR_ESTAVEL_PP = 0.05

MESES = {
    "pt": ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
           "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"],
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
    "es": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
           "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
}

SERIES = [
    {
        "codigo": 20771,
        "titulo": "Juros Crédito Rural (PF)",
        "icone": "🏦",
        "tomador": "produtor pessoa física",
        "impacto_alta": ("Encarece financiamento do produtor PF e adia compra de "
                         "tratores média/alta potência e colheitadeiras."),
        "impacto_baixa": ("Barateia financiamento do produtor PF e acelera decisão de "
                          "compra de tratores média/alta potência e colheitadeiras."),
        "impacto_estavel": ("Custo de financiamento PF sem mudança relevante; decisão de "
                            "compra de tratores e colheitadeiras segue neutra."),
    },
    {
        "codigo": 20760,
        "titulo": "Juros Crédito Rural (PJ)",
        "icone": "🏛️",
        "tomador": "empresas e cooperativas",
        "impacto_alta": ("Encarece crédito de empresas/cooperativas e adia investimento em "
                         "colheitadeiras Classes 7+ e pulverizadores autopropelidos."),
        "impacto_baixa": ("Barateia crédito de empresas/cooperativas e acelera investimento em "
                          "colheitadeiras Classes 7+ e pulverizadores autopropelidos."),
        "impacto_estavel": ("Custo de crédito PJ estável; investimento em colheitadeiras Classes 7+ "
                            "e autopropelidos segue neutro."),
    },
]


def _parse_pontos(dados) -> list:
    """Converte o JSON do BCB em lista ordenada de (date, float)."""
    pontos = []
    for item in dados or []:
        try:
            data = datetime.datetime.strptime(item["data"], "%d/%m/%Y").date()
            valor = float(str(item["valor"]).replace(",", "."))
            pontos.append((data, valor))
        except (KeyError, ValueError, TypeError):
            continue
    pontos.sort(key=lambda p: p[0])
    return pontos


def _get_json(url, params, rotulo):
    """GET com retries e backoff. Retorna o JSON ou None."""
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            if tentativa < TENTATIVAS:
                espera = 2 ** tentativa
                print(f"      ⚠ {rotulo}: tentativa {tentativa}/{TENTATIVAS} falhou "
                      f"({e}). Nova tentativa em {espera}s...")
                time.sleep(espera)
    print(f"      ❌ {rotulo}: falhou após {TENTATIVAS} tentativas ({ultimo_erro}).")
    return None


def _buscar_pontos(codigo: int) -> list:
    """
    Busca os 2 últimos pontos da série, com 2 caminhos independentes:
      A) endpoint '/dados/ultimos/2' (mais leve);
      B) fallback por intervalo de datas (últimos ~18 meses).
    Retorna lista de (date, valor) — pode ter 0, 1 ou 2 itens.
    """
    # --- Caminho A ---
    dados = _get_json(URL_ULTIMOS.format(codigo=codigo, n=2),
                      {"formato": "json"}, f"série {codigo} (ultimos/2)")
    pontos = _parse_pontos(dados)
    if len(pontos) >= 2:
        return pontos[-2:]

    # --- Caminho B (fallback) ---
    print(f"      ↻ série {codigo}: usando consulta por período (fallback)...")
    hoje = datetime.date.today()
    inicio = (hoje - datetime.timedelta(days=550)).strftime("%d/%m/%Y")
    dados = _get_json(URL_PERIODO.format(codigo=codigo),
                      {"formato": "json", "dataInicial": inicio,
                       "dataFinal": hoje.strftime("%d/%m/%Y")},
                      f"série {codigo} (período)")
    pontos_fb = _parse_pontos(dados)
    if len(pontos_fb) >= 2:
        return pontos_fb[-2:]

    # Retorna o que houver (0 ou 1 ponto) — o card ainda será exibido se houver 1.
    return pontos_fb or pontos


def _fmt_pt(valor: float, casas: int = 2) -> str:
    """Formata número no padrão brasileiro (vírgula decimal)."""
    return f"{valor:,.{casas}f}".replace(",", "#").replace(".", ",").replace("#", ".")


def _nomes_mes(mes_1a12: int) -> dict:
    """Nome do mês nos 3 idiomas, para o selo 'vs <mês>'."""
    i = mes_1a12 - 1
    return {"pt": MESES["pt"][i], "en": MESES["en"][i], "es": MESES["es"][i]}


def _montar_card(serie: dict):
    """Monta o card de um indicador de juros. Retorna None só se NÃO houver
    nenhum dado (com 1 ponto o card ainda é exibido, sem comparação)."""
    pontos = _buscar_pontos(serie["codigo"])
    if not pontos:
        print(f"   ❌ {serie['titulo']}: sem dados no BCB — card omitido "
              f"(nenhum valor é inventado).")
        return None

    data_atual, valor_atual = pontos[-1]
    ref_atual = f"{MESES['pt'][data_atual.month - 1][:3]}/{data_atual.year}"

    # Comparação contra o PONTO ANTERIOR REAL DA SÉRIE (não o mês do calendário).
    if len(pontos) >= 2:
        data_ant, valor_ant = pontos[-2]
        delta = round(valor_atual - valor_ant, 2)
        mes_comparacao = _nomes_mes(data_ant.month)
    else:
        delta = None
        mes_comparacao = None
        print(f"      ⚠ {serie['titulo']}: apenas 1 leitura disponível — card exibido "
              f"sem comparação mensal.")

    mes_ant_pt = mes_comparacao["pt"] if mes_comparacao else None

    # Direção sob a ótica da demanda por máquinas: juros menores = melhor.
    if delta is None:
        direcao, tendencia, variacao_txt = "estavel", "estavel", ""
    elif delta > LIMIAR_ESTAVEL_PP:
        direcao, tendencia = "piorando", "alta"
        variacao_txt = f", alta de {_fmt_pt(abs(delta))} p.p. ante {mes_ant_pt}"
    elif delta < -LIMIAR_ESTAVEL_PP:
        direcao, tendencia = "melhorando", "baixa"
        variacao_txt = f", queda de {_fmt_pt(abs(delta))} p.p. ante {mes_ant_pt}"
    else:
        direcao, tendencia = "estavel", "estavel"
        variacao_txt = f", estável ante {mes_ant_pt}"

    descricao = (f"Taxa média de {_fmt_pt(valor_atual)}% a.a. para {serie['tomador']} "
                 f"({ref_atual}){variacao_txt}.")

    if direcao == "piorando":
        impactos = serie["impacto_alta"]
    elif direcao == "melhorando":
        impactos = serie["impacto_baixa"]
    else:
        impactos = serie["impacto_estavel"]

    seta = {"melhorando": "↓", "piorando": "↑", "estavel": "→"}[direcao]
    delta_txt = ("%+.2f p.p." % delta) if delta is not None else "s/ comparativo"
    print(f"   ✅ {serie['titulo']}: {_fmt_pt(valor_atual)}% a.a. ({ref_atual}) "
          f"{seta} {delta_txt} vs {mes_ant_pt or 's/ base'} | direção: {direcao}")

    card = {
        "titulo": serie["titulo"],
        "icone": serie["icone"],
        "tendencia": tendencia,
        "direcao": direcao,
        "descricao": descricao,
        "impactos": impactos,
        "fonte": f"BCB/SGS série {serie['codigo']}",
    }
    if mes_comparacao:
        card["mes_comparacao"] = mes_comparacao
    return card


def obter_juros_rural() -> list:
    """
    Ponto de entrada usado pelo gerador do dashboard.
    Retorna uma LISTA de cards (0 a 2 itens) para 'fatores_economicos' do Brasil.
    """
    print("Buscando Juros do Crédito Rural PF/PJ (BCB SGS 20771 e 20760)...")
    cards = []
    for serie in SERIES:
        card = _montar_card(serie)
        if card is not None:
            cards.append(card)

    if len(cards) == 2:
        print("   ✅ Ambos os cards de juros (PF e PJ) foram gerados.")
    elif len(cards) == 1:
        print(f"   ⚠ Apenas 1 card de juros gerado ({cards[0]['titulo']}). "
              f"A outra série não respondeu nesta execução.")
    else:
        print("   ❌ Nenhuma série de juros retornou dados — cards omitidos nesta execução.")
    return cards


if __name__ == "__main__":
    print("=" * 64)
    print("EARLY SIGNALS · modulo_juros_rural (teste standalone)")
    print("=" * 64)
    for c in obter_juros_rural():
        print(f"\n{c['icone']} {c['titulo']}  [{c['tendencia']} / {c['direcao']}]")
        print(f"   Descrição  : {c['descricao']}")
        print(f"   Impactos   : {c['impactos']}")
        print(f"   Comparado a: {c.get('mes_comparacao', {}).get('pt', '—')}")
        print(f"   Fonte      : {c['fonte']}")
