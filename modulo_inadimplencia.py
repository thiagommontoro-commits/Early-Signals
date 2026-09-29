# -*- coding: utf-8 -*-
# ==========================================================================
# MÓDULO: INADIMPLÊNCIA RURAL - BRASIL  (Early Signals - LATAM)
# VERSÃO: v2 (com campo 'direcao')  ← confira esta linha no GitHub
# --------------------------------------------------------------------------
# >>> SUBSTITUI a versão anterior deste arquivo.
#
# Série SGS 21148 do Banco Central do Brasil:
#   "Inadimplência da carteira de crédito - Recursos direcionados -
#    Pessoas físicas - Crédito rural total (%)"
#
# Endpoint "/dados/ultimos/{N}" é limitado a 20 registros (N=20).
#
# CORREÇÕES DESTA VERSÃO:
# 1) Retries (3x) + endpoint alternativo por período -> o card não some
#    por instabilidade momentânea da API.
# 2) Com 1 única leitura, o card é exibido (sem comparação) em vez de sumir.
# 3) Devolve 'direcao' ('piorando' quando a inadimplência SOBE, 'melhorando'
#    quando CAI) e 'mes_comparacao' (mês real do ponto anterior da série).
#    Sem esse campo o dashboard mostrava sempre "Estável".
#
# A comparação é sempre último ponto vs penúltimo ponto da série:
#   dado de Ago -> "vs Julho"; dado de Set -> "vs Agosto" (automático).
# ==========================================================================
import json
import time
import datetime
import urllib.request
import urllib.parse

SERIE_SGS = 21148
N_MESES = 20
URL_ULTIMOS = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{SERIE_SGS}"
               f"/dados/ultimos/{N_MESES}?formato=json")
URL_PERIODO = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{SERIE_SGS}/dados"

TENTATIVAS = 3
TIMEOUT = 30
LIMIAR_PP = 0.05

MESES_PT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
            'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
MESES_FULL = {
    "pt": ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
           "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"],
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
    "es": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
           "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
}


def _http_get_json(url, rotulo):
    """GET com retries e backoff exponencial. Retorna o JSON ou None."""
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "EarlySignals/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            if tentativa < TENTATIVAS:
                espera = 2 ** tentativa
                print(f"      ⚠ {rotulo}: tentativa {tentativa}/{TENTATIVAS} falhou "
                      f"({e}). Nova tentativa em {espera}s...")
                time.sleep(espera)
    print(f"      ❌ {rotulo}: falhou após {TENTATIVAS} tentativas ({ultimo_erro}).")
    return None


def _buscar_serie_bcb():
    """Caminho A: /ultimos/20. Caminho B (fallback): consulta por período."""
    dados = _http_get_json(URL_ULTIMOS, f"SGS {SERIE_SGS} (ultimos/{N_MESES})")
    if dados and len(dados) >= 2:
        return dados

    print(f"      ↻ SGS {SERIE_SGS}: usando consulta por período (fallback)...")
    hoje = datetime.date.today()
    qs = urllib.parse.urlencode({
        "formato": "json",
        "dataInicial": (hoje - datetime.timedelta(days=550)).strftime("%d/%m/%Y"),
        "dataFinal": hoje.strftime("%d/%m/%Y"),
    })
    dados_fb = _http_get_json(f"{URL_PERIODO}?{qs}", f"SGS {SERIE_SGS} (período)")
    if dados_fb:
        return dados_fb[-N_MESES:]
    return dados or []


def _valor(item):
    return float(str(item["valor"]).replace(",", "."))


def _nomes_mes(mes_1a12):
    i = mes_1a12 - 1
    return {"pt": MESES_FULL["pt"][i], "en": MESES_FULL["en"][i], "es": MESES_FULL["es"][i]}


def obter_inadimplencia_rural():
    """Retorna o card para dados_paises['br']['fatores_economicos'], ou None
    apenas se a série não devolver nenhum dado (nunca inventa número)."""
    dados = _buscar_serie_bcb()
    if not dados:
        print("   ❌ Inadimplência: série indisponível no BCB — card omitido.")
        return None

    try:
        atual = _valor(dados[-1])
    except (KeyError, ValueError, TypeError) as e:
        print(f"   ❌ Inadimplência: formato inesperado na resposta do BCB: {e}")
        return None

    # Mês de referência do dado mais recente
    try:
        _, m, a = str(dados[-1]["data"]).split("/")
        mes_ref = f"{MESES_PT[int(m) - 1]}/{a}"
    except Exception:
        mes_ref = str(dados[-1].get("data", ""))

    # Ponto anterior REAL da série (não o mês do calendário)
    anterior, mes_comparacao = None, None
    if len(dados) >= 2:
        try:
            anterior = _valor(dados[-2])
            _, m_ant, _ = str(dados[-2]["data"]).split("/")
            mes_comparacao = _nomes_mes(int(m_ant))
        except Exception:
            anterior, mes_comparacao = None, None

    delta_pp = round(atual - anterior, 2) if anterior is not None else None

    # Média da janela disponível
    valores = []
    for x in dados:
        try:
            valores.append(_valor(x))
        except Exception:
            continue
    media = round(sum(valores) / len(valores), 2) if valores else atual
    desvio = atual - media
    pos_pt = ("acima da média" if desvio > LIMIAR_PP
              else "abaixo da média" if desvio < -LIMIAR_PP else "na média")

    # Inadimplência: SUBIR = pior para a demanda de máquinas
    if delta_pp is None:
        tendencia, direcao, seta = "estavel", "estavel", "▬"
    elif delta_pp > LIMIAR_PP:
        tendencia, direcao, seta = "alta", "piorando", "▲"
    elif delta_pp < -LIMIAR_PP:
        tendencia, direcao, seta = "baixa", "melhorando", "▼"
    else:
        tendencia, direcao, seta = "estavel", "estavel", "▬"

    fmt = lambda v: f"{v:.2f}".replace(".", ",")
    if delta_pp is not None:
        mes_ant_pt = mes_comparacao["pt"] if mes_comparacao else "o mês anterior"
        descricao = (f"Crédito rural (PF): {fmt(atual)}% em {mes_ref}. "
                     f"{seta} {'+' if delta_pp >= 0 else '−'}{fmt(abs(delta_pp))} p.p. "
                     f"ante {mes_ant_pt} · {pos_pt} {len(valores)}m ({fmt(media)}%).")
    else:
        descricao = (f"Crédito rural (PF): {fmt(atual)}% em {mes_ref}. "
                     f"{pos_pt} {len(valores)}m ({fmt(media)}%).")

    if tendencia == "alta":
        impactos = ("Alta restringe crédito agro e adia financiamento de tratores alta "
                    "potência e colheitadeiras Classes 7+.")
    elif tendencia == "baixa":
        impactos = ("Queda favorece oferta de crédito agro e acelera financiamento de "
                    "tratores e colheitadeiras.")
    else:
        impactos = ("Estabilidade mantém condições de crédito; decisão de compra de "
                    "tratores e colheitadeiras segue neutra.")

    print(f"   ✅ Inadimplência Crédito Rural BR (v2): {fmt(atual)}% ({mes_ref}) | "
          f"Δ {delta_pp if delta_pp is not None else 's/ base'} p.p. vs "
          f"{mes_comparacao['pt'] if mes_comparacao else 's/ base'} | direção: {direcao}")

    item = {
        "titulo": "Inadimplência Crédito Rural",
        "icone": "⚠️",
        "tendencia": tendencia,
        "direcao": direcao,
        "descricao": descricao,
        "impactos": impactos,
        "fonte": f"Banco Central do Brasil — SGS {SERIE_SGS}",
    }
    if mes_comparacao:
        item["mes_comparacao"] = mes_comparacao
    return item


if __name__ == "__main__":
    item = obter_inadimplencia_rural()
    print(json.dumps(item, ensure_ascii=False, indent=2) if item else "Indisponível.")
