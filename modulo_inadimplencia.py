# ==========================================================================
# MÓDULO: INADIMPLÊNCIA RURAL - BRASIL  (Early Signals - LATAM)
# --------------------------------------------------------------------------
# Busca a série SGS 21148 do Banco Central do Brasil:
#   "Inadimplência da carteira de crédito - Recursos direcionados -
#    Pessoas físicas - Crédito rural total (%)" - mensal desde 03/2011.
#
# API pública, SEM autenticação:
#   https://api.bcb.gov.br/dados/serie/bcdata.sgs.21148/dados/ultimos/{N}?formato=json
#
# ⚠️ IMPORTANTE: o endpoint "/dados/ultimos/{N}" do BCB é LIMITADO A NO
# MÁXIMO 20 REGISTROS. Pedir mais que isso (ex.: 24) retorna erro
# "HTTP Error 400: Bad Request". Por isso usamos N=20 abaixo.
#
# Retorna um dicionário no MESMO formato dos itens de 'fatores_economicos'
# do dashboard atual (titulo/icone/tendencia/descricao/impactos/fonte),
# para ser injetado diretamente em dados_paises['br']['fatores_economicos'].
#
# Semântica do farol (inadimplência: MENOR = melhor para o produtor):
#   - caindo  -> 'baixa'  -> farol verde
#   - subindo -> 'alta'   -> farol vermelho
#   - estável -> 'estavel'-> farol amarelo
# ==========================================================================

import json

try:
    import urllib.request
    import urllib.error
    _HTTP_OK = True
except ImportError:
    _HTTP_OK = False

SERIE_SGS = 21148
N_MESES = 20  # máximo permitido pelo endpoint /dados/ultimos/{N} do BCB
URL = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{SERIE_SGS}/dados/ultimos/{N_MESES}?formato=json"

MESES_PT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
            'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']


def _buscar_serie_bcb(timeout=20):
    """Consulta a API do BCB e devolve lista de {'data':'dd/MM/yyyy','valor':'x.xx'}."""
    if not _HTTP_OK:
        return None
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "EarlySignals/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"❌ Falha ao consultar BCB SGS {SERIE_SGS}: {e}")
        return None


def _multi(pt, en, es):
    """Monta dict multilíngue no padrão usado pelo dashboard."""
    return {"pt": pt, "en": en, "es": es}


def obter_inadimplencia_rural():
    """
    Retorna o item de fator econômico pronto para injetar em
    dados_paises['br']['fatores_economicos'], ou None em caso de falha
    (nesse caso o Brasil segue com os fatores gerados pela IA, sem quebrar).
    """
    dados = _buscar_serie_bcb()
    if not dados or len(dados) < 2:
        print("⚠️ Série de inadimplência indisponível; item não será adicionado.")
        return None

    try:
        atual = float(dados[-1]["valor"].replace(",", "."))
        anterior = float(dados[-2]["valor"].replace(",", "."))
    except (KeyError, ValueError, TypeError) as e:
        print(f"⚠️ Formato inesperado na resposta do BCB: {e}")
        return None

    # data de referência (dd/MM/yyyy -> Mês/AAAA)
    data_ref = dados[-1].get("data", "")
    mes_ref = ""
    try:
        d, m, a = data_ref.split("/")
        mes_ref = f"{MESES_PT[int(m)-1]}/{a}"
    except Exception:
        mes_ref = data_ref

    delta_pp = round(atual - anterior, 2)  # variação em pontos percentuais

    # média histórica da janela disponível (até 20 meses)
    todos = [float(x["valor"].replace(",", ".")) for x in dados]
    media_hist = round(sum(todos) / len(todos), 2)
    desvio = round(atual - media_hist, 2)  # atual vs média (+ = acima / pior)

    # posição vs média (executivo: "acima" = pior, "abaixo" = melhor)
    if desvio > 0.05:
        pos_pt, pos_en, pos_es = "acima da média", "above average", "sobre la media"
    elif desvio < -0.05:
        pos_pt, pos_en, pos_es = "abaixo da média", "below average", "bajo la media"
    else:
        pos_pt, pos_en, pos_es = "na média", "at average", "en la media"

    # tendência (menor = melhor)
    if delta_pp < -0.05:
        tendencia = "baixa"          # farol verde
        seta_pt = seta_en = seta_es = "▼"
    elif delta_pp > 0.05:
        tendencia = "alta"           # farol vermelho
        seta_pt = seta_en = seta_es = "▲"
    else:
        tendencia = "estavel"        # farol amarelo
        seta_pt = seta_en = seta_es = "▬"

    janela_meses = len(todos)

    # DESCRIÇÃO — executiva/enxuta: valor + variação mês + posição vs média
    descricao = _multi(
        pt=(f"Crédito rural (PF): {atual:.2f}% em {mes_ref}. "
            f"{seta_pt} {delta_pp:+.2f} p.p. no mês · {pos_pt} {janela_meses}m ({media_hist:.2f}%)."),
        en=(f"Rural credit (individuals): {atual:.2f}% in {mes_ref}. "
            f"{seta_en} {delta_pp:+.2f} p.p. MoM · {pos_en} {janela_meses}m ({media_hist:.2f}%)."),
        es=(f"Crédito rural (PF): {atual:.2f}% en {mes_ref}. "
            f"{seta_es} {delta_pp:+.2f} p.p. mes · {pos_es} {janela_meses}m ({media_hist:.2f}%)."),
    )

    # IMPACTOS — executivo, 1 linha
    impactos = _multi(
        pt=("Queda favorece oferta de crédito agro e financiamento de máquinas."
            if tendencia == "baixa" else
            "Alta pode restringir crédito agro e pressionar financiamento de máquinas."
            if tendencia == "alta" else
            "Estabilidade mantém as condições de crédito para máquinas."),
        en=("Decline supports agri credit supply and machinery financing."
            if tendencia == "baixa" else
            "Rise may restrict agri credit and pressure machinery financing."
            if tendencia == "alta" else
            "Stability keeps credit conditions for machinery."),
        es=("Caída favorece la oferta de crédito agro y financiación de máquinas."
            if tendencia == "baixa" else
            "Alza puede restringir el crédito agro y presionar la financiación."
            if tendencia == "alta" else
            "Estabilidad mantiene las condiciones de crédito para máquinas."),
    )

    print(f"   ✅ Inadimplência Crédito Rural BR: {atual:.2f}% ({mes_ref}) | "
          f"Δ mês {delta_pp:+.2f} p.p. | {pos_pt} ({media_hist:.2f}%) | tendência {tendencia}")

    return {
        "titulo": "Inadimplência Crédito Rural",
        "icone": "⚠️",
        "tendencia": tendencia,
        "descricao": descricao,
        "impactos": impactos,
        "fonte": f"Banco Central do Brasil — SGS {SERIE_SGS}",
    }


if __name__ == "__main__":
    item = obter_inadimplencia_rural()
    print("\n=== ITEM GERADO ===")
    print(json.dumps(item, ensure_ascii=False, indent=2) if item else "Indisponível.")
