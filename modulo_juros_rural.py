# -*- coding: utf-8 -*-
"""
modulo_juros_rural.py   ←←← ARQUIVO NOVO (não existe hoje no seu repositório)
============================================================================
Early Signals · Taxas de Juros do Crédito Rural (Pessoa Física e Pessoa Jurídica)

>>> O QUE FAZER COM ESTE ARQUIVO:
    ADICIONAR na raiz do repositório, ao lado de 'modulo_inadimplencia.py'.
    É um arquivo NOVO — não substitui nada.

Busca as taxas médias de juros do crédito rural diretamente do Banco Central do
Brasil (BCB), pelo Sistema Gerenciador de Séries Temporais (SGS) — a MESMA
fonte já usada pelo módulo de inadimplência (série 21148).

Séries utilizadas:
    20771 -> Juros · Pessoa Física   · Crédito rural total (% a.a.)
    20760 -> Juros · Pessoa Jurídica · Crédito rural total (% a.a.)

>>> REGRA DE COMPARAÇÃO (corrigida): a comparação é SEMPRE entre os DOIS
    ÚLTIMOS PONTOS REAIS DA SÉRIE — nunca contra o mês do calendário.
    O BCB publica com defasagem: em setembro, o dado mais recente pode ser
    de julho. Nesse caso a comparação correta é JULHO vs JUNHO (e não
    "vs Agosto"). Quando sair agosto, passa a ser agosto vs julho, e assim
    por diante — automaticamente, sem precisar mexer no código.

    Para isso cada card devolve o campo extra 'mes_comparacao' (pt/en/es),
    que o gerador usa para escrever o selo "Piorando vs Junho".

Cada card segue o contrato usado em 'gerar_bloco_analises':
    { "titulo", "icone", "tendencia", "direcao", "descricao", "impactos",
      "fonte", "mes_comparacao" }

Direção julgada sob a ótica da demanda por máquinas agrícolas:
    juros caindo vs mês anterior da série  -> 'melhorando'
    juros subindo vs mês anterior da série -> 'piorando'
    variação < 0,05 p.p.                   -> 'estavel'

Robustez: nunca quebra o pipeline. Se a API não responder, o card é OMITIDO
(nada é inventado) e um aviso é impresso no log do Action.

Autoria: Global Reporting & Analytics — Thiago Montoro (AGCO)
"""
from __future__ import annotations

import datetime

import requests

BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}"
HEADERS = {"User-Agent": "AGCO-Early-Signals/1.0 (+juros-credito-rural)"}
TIMEOUT = 45

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


def _buscar_ultimos(codigo: int, n: int = 2):
    """Retorna os últimos N pontos da série SGS como lista de (data, valor).
    Devolve [] se a API falhar ou não houver dados (nunca levanta exceção)."""
    url = BASE_URL.format(codigo=codigo, n=n)
    try:
        r = requests.get(url, params={"formato": "json"}, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        dados = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠ Juros: série {codigo} indisponível no BCB ({e}).")
        return []

    pontos = []
    for item in dados or []:
        try:
            data = datetime.datetime.strptime(item["data"], "%d/%m/%Y").date()
            valor = float(str(item["valor"]).replace(",", "."))
            pontos.append((data, valor))
        except (KeyError, ValueError, TypeError):
            continue
    return pontos


def _fmt_pt(valor: float, casas: int = 2) -> str:
    """Formata número no padrão brasileiro (vírgula decimal)."""
    return f"{valor:,.{casas}f}".replace(",", "#").replace(".", ",").replace("#", ".")


def _nomes_mes(mes_1a12: int) -> dict:
    """Nome do mês nos 3 idiomas, para o selo 'vs <mês>'."""
    i = mes_1a12 - 1
    return {"pt": MESES["pt"][i], "en": MESES["en"][i], "es": MESES["es"][i]}


def _montar_card(serie: dict):
    """Monta o card de um indicador de juros. Retorna None se não houver dado."""
    pontos = _buscar_ultimos(serie["codigo"], n=2)
    if not pontos:
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
    # Campo extra: informa ao gerador qual mês usar no selo "vs <mês>".
    if mes_comparacao:
        card["mes_comparacao"] = mes_comparacao
    return card


def obter_juros_rural() -> list:
    """
    Ponto de entrada usado pelo gerador do dashboard.

    Retorna uma LISTA de cards (0 a 2 itens) prontos para serem inseridos em
    'fatores_economicos' do Brasil. Séries indisponíveis são simplesmente
    omitidas — nenhum valor é inventado.
    """
    print("Buscando Juros do Crédito Rural PF/PJ (BCB SGS 20771 e 20760)...")
    cards = []
    for serie in SERIES:
        card = _montar_card(serie)
        if card is not None:
            cards.append(card)
    if not cards:
        print("   ❌ Nenhuma série de juros retornou dados — cards omitidos nesta execução.")
    return cards


if __name__ == "__main__":
    print("=" * 64)
    print("EARLY SIGNALS · modulo_juros_rural (teste standalone)")
    print("=" * 64)
    for c in obter_juros_rural():
        print(f"\n{c['icone']} {c['titulo']}  [{c['tendencia']} / {c['direcao']}]")
        print(f"   Descrição: {c['descricao']}")
        print(f"   Impactos : {c['impactos']}")
        print(f"   Comparado a: {c.get('mes_comparacao', {}).get('pt', '—')}")
        print(f"   Fonte    : {c['fonte']}")
