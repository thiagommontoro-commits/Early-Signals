# ==========================================================================
# MÓDULO: CRÉDITO RURAL — DEEP DIVE  (Early Signals - LATAM / Brasil)
# --------------------------------------------------------------------------
# Aba dedicada, exclusiva do Brasil, para aprofundar na saúde do crédito
# rural. Busca 8 séries do Banco Central (SGS), todas MENSAIS e específicas
# do crédito rural, distinguindo Pessoa Física (PF) e Pessoa Jurídica (PJ),
# em duas dimensões: INADIMPLÊNCIA e JUROS.
#
# Fonte: API pública do BCB (sem autenticação). Cada série é uma chamada.
# Endpoint /dados/ultimos/{N} é limitado a 20 registros -> usamos N=20.
#
# NÃO depende de IA (Gemini) nem de planilha. Atualiza sozinho a cada
# execução do workflow: se o BCB publicou mês novo, o dado atualiza; senão,
# mantém o último valor. Fallback seguro: série que falhar é omitida, sem
# quebrar as demais.
# ==========================================================================

import json

try:
    import urllib.request
    import urllib.error
    _HTTP_OK = True
except ImportError:
    _HTTP_OK = False

MESES_PT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
            'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

# Buscamos ~40 meses (por intervalo de datas) para ter folga suficiente
# para calcular: valor atual, M/M, A/A, fechamentos anuais (Dez) e média R12.
ANOS_HISTORICO = 4

# --------------------------------------------------------------------------
# CATÁLOGO DE SÉRIES (todas rurais, BCB SGS)
#   grupo: "inadimplencia" | "juros"
#   pessoa: "PF" | "PJ"
#   tipo: rótulo curto (Total / Reguladas / Mercado)
#   unidade: como exibir
# --------------------------------------------------------------------------
SERIES = [
    # ---- INADIMPLÊNCIA (%) ----
    {"sgs": 21148, "grupo": "inadimplencia", "pessoa": "PF", "tipo": "Total",     "unidade": "%"},
    {"sgs": 21147, "grupo": "inadimplencia", "pessoa": "PF", "tipo": "Reguladas", "unidade": "%"},
    {"sgs": 21146, "grupo": "inadimplencia", "pessoa": "PF", "tipo": "Mercado",   "unidade": "%"},
    {"sgs": 21136, "grupo": "inadimplencia", "pessoa": "PJ", "tipo": "Total",     "unidade": "%"},
    {"sgs": 21135, "grupo": "inadimplencia", "pessoa": "PJ", "tipo": "Reguladas", "unidade": "%"},
    # ---- JUROS (% a.a.) ----
    # Todas em % a.a. para comparação correta. (Obs: 20760 é a versão anual da
    # série de juros PJ; a 25485 seria a mesma em % a.m. — não usar aqui.)
    {"sgs": 20771, "grupo": "juros", "pessoa": "PF", "tipo": "Total",     "unidade": "% a.a."},
    {"sgs": 20770, "grupo": "juros", "pessoa": "PF", "tipo": "Reguladas", "unidade": "% a.a."},
    {"sgs": 20760, "grupo": "juros", "pessoa": "PJ", "tipo": "Total",     "unidade": "% a.a."},
]


def _buscar_sgs(codigo, timeout=20):
    """
    Busca a série SGS por intervalo de datas (últimos ANOS_HISTORICO anos).
    Usar dataInicial/dataFinal permite trazer mais que 20 pontos, necessário
    para calcular fechamentos anuais e média R12. Retorna lista ou None.
    """
    if not _HTTP_OK:
        return None
    import datetime
    hoje = datetime.date.today()
    ini = hoje.replace(year=hoje.year - ANOS_HISTORICO)
    di = ini.strftime("%d/%m/%Y")
    df = hoje.strftime("%d/%m/%Y")
    url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
           f"?formato=json&dataInicial={di}&dataFinal={df}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EarlySignals/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"   Falha SGS {codigo}: {e}")
        return None


def _mes_ref(data_str):
    """Converte 'dd/MM/yyyy' -> 'Mês/AAAA'."""
    try:
        d, m, a = data_str.split("/")
        return f"{MESES_PT[int(m)-1]}/{a}"
    except Exception:
        return data_str


def _calcular(serie_cfg):
    """Busca a série e calcula métricas. Retorna dict ou None."""
    dados = _buscar_sgs(serie_cfg["sgs"])
    if not dados or len(dados) < 2:
        return None
    try:
        # lista de (ano, mes, valor)
        pontos = []
        for x in dados:
            v = float(x["valor"].replace(",", "."))
            d, m, a = x["data"].split("/")
            pontos.append((int(a), int(m), v))
    except (KeyError, ValueError, TypeError):
        return None

    if len(pontos) < 2:
        return None

    valores = [p[2] for p in pontos]
    ano_atual, mes_atual, atual = pontos[-1]
    anterior = pontos[-2][2]
    delta_pp = round(atual - anterior, 2)  # variação Mês/Mês (p.p.)

    # variação Ano/Ano (mesmo mês, 12 meses atrás)
    delta_aa = None
    val_12m = None
    for (a, m, v) in pontos:
        if a == ano_atual - 1 and m == mes_atual:
            val_12m = v
            delta_aa = round(atual - v, 2)
            break

    # Fechamentos anuais (Dezembro) dos 2 últimos anos fechados
    def _fechamento(ano):
        for (a, m, v) in pontos:
            if a == ano and m == 12:
                return round(v, 2)
        return None
    fech_ano1 = _fechamento(ano_atual - 1)  # ex.: Dez/2025
    fech_ano2 = _fechamento(ano_atual - 2)  # ex.: Dez/2024

    # Média móvel R12 (últimos 12 meses)
    ult12 = valores[-12:]
    media_r12 = round(sum(ult12) / len(ult12), 2) if ult12 else None

    minimo = round(min(valores), 2)
    maximo = round(max(valores), 2)
    perc = round(100.0 * sum(1 for v in valores if v <= atual) / len(valores), 0)

    # tendência baseada na variação ANUAL (estrutural). Menor = melhor.
    base_delta = delta_aa if delta_aa is not None else delta_pp
    if base_delta < -0.05:
        tendencia = "baixa"
    elif base_delta > 0.05:
        tendencia = "alta"
    else:
        tendencia = "estavel"

    return {
        "sgs": serie_cfg["sgs"],
        "grupo": serie_cfg["grupo"],
        "pessoa": serie_cfg["pessoa"],
        "tipo": serie_cfg["tipo"],
        "unidade": serie_cfg["unidade"],
        "atual": round(atual, 2),
        "mes_ref": _mes_ref(dados[-1].get("data", "")),
        "delta_pp": delta_pp,
        "delta_aa": delta_aa,
        "val_12m": round(val_12m, 2) if val_12m is not None else None,
        "fech_ano1": fech_ano1, "fech_ano1_label": f"Dez/{ano_atual-1}",
        "fech_ano2": fech_ano2, "fech_ano2_label": f"Dez/{ano_atual-2}",
        "media_r12": media_r12,
        "minimo": minimo,
        "maximo": maximo,
        "percentil": perc,
        "tendencia": tendencia,
        "historico": valores,
    }


def _gerar_insight(resultados):
    """Insight automático comparando PF vs PJ na inadimplência Total."""
    pf = next((r for r in resultados if r["grupo"] == "inadimplencia"
               and r["pessoa"] == "PF" and r["tipo"] == "Total"), None)
    pj = next((r for r in resultados if r["grupo"] == "inadimplencia"
               and r["pessoa"] == "PJ" and r["tipo"] == "Total"), None)
    if not pf or not pj or not pj["atual"]:
        return None
    razao = pf["atual"] / pj["atual"] if pj["atual"] > 0 else None
    if razao and razao >= 1.5:
        return {
            "pt": (f"Inadimplência do produtor Pessoa Física ({pf['atual']:.2f}%) é "
                   f"~{razao:.0f}x maior que a de Pessoa Jurídica ({pj['atual']:.2f}%) — "
                   f"o pequeno/médio produtor está mais pressionado."),
            "en": (f"Individual (PF) rural delinquency ({pf['atual']:.2f}%) is "
                   f"~{razao:.0f}x higher than corporate (PJ) ({pj['atual']:.2f}%) — "
                   f"small/medium farmers are under more pressure."),
            "es": (f"La morosidad de Persona Física ({pf['atual']:.2f}%) es "
                   f"~{razao:.0f}x mayor que la de Persona Jurídica ({pj['atual']:.2f}%)."),
        }
    return {
        "pt": (f"Inadimplência PF em {pf['atual']:.2f}% e PJ em {pj['atual']:.2f}% "
               f"({pf['mes_ref']})."),
        "en": (f"PF delinquency at {pf['atual']:.2f}% and PJ at {pj['atual']:.2f}% "
               f"({pf['mes_ref']})."),
        "es": (f"Morosidad PF en {pf['atual']:.2f}% y PJ en {pj['atual']:.2f}%."),
    }


def processar_credito_rural():
    """
    Função principal do módulo. Busca todas as séries e organiza o resultado.
    Retorna dict:
      {
        "inadimplencia": {"PF": [...], "PJ": [...]},
        "juros":         {"PF": [...], "PJ": [...]},
        "insight": {"pt":..., "en":..., "es":...} | None,
        "mes_ref": "Jun/2026" | None,
        "disponivel": True/False
      }
    """
    print("💳 Crédito Rural Deep Dive: buscando séries do BCB...")
    resultados = []
    for cfg in SERIES:
        m = _calcular(cfg)
        if m:
            resultados.append(m)
            print(f"   OK SGS {m['sgs']} [{m['grupo']}/{m['pessoa']}/{m['tipo']}]: "
                  f"{m['atual']}{m['unidade']} ({m['mes_ref']}) delta {m['delta_pp']:+.2f}")

    if not resultados:
        print("   Nenhuma série disponível — aba mostrará indisponível.")
        return {"disponivel": False}

    def _sel(grupo, pessoa):
        return [r for r in resultados if r["grupo"] == grupo and r["pessoa"] == pessoa]

    mes_ref = None
    for r in resultados:
        if r["grupo"] == "inadimplencia" and r["pessoa"] == "PF" and r["tipo"] == "Total":
            mes_ref = r["mes_ref"]
            break

    return {
        "disponivel": True,
        "mes_ref": mes_ref,
        "inadimplencia": {"PF": _sel("inadimplencia", "PF"),
                          "PJ": _sel("inadimplencia", "PJ")},
        "juros": {"PF": _sel("juros", "PF"),
                  "PJ": _sel("juros", "PJ")},
        "insight": _gerar_insight(resultados),
    }


if __name__ == "__main__":
    dados = processar_credito_rural()
    print(json.dumps(dados, ensure_ascii=False, indent=2))
