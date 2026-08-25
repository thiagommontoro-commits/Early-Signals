# ==========================================================================
# RENDERIZADOR HTML — CRÉDITO RURAL DEEP DIVE
# Usa o MESMO padrão visual do Early Signals (analysis-card + farol), com:
#   - comparação Mês/Mês E Ano/Ano
#   - glossário/legenda explicando cada conceito (credibilidade)
#   - agrupamento PF vs PJ por seção (Inadimplência e Juros)
# ==========================================================================

TR = {  # textos multilíngues
    "subtitle": {"pt": "Análise aprofundada da inadimplência e do custo do crédito rural no Brasil, comparando Pessoa Física e Pessoa Jurídica. Fonte oficial: Banco Central do Brasil (SGS).",
                 "en": "In-depth analysis of Brazilian rural credit delinquency and cost, comparing individuals and corporates. Official source: Central Bank of Brazil (SGS).",
                 "es": "Análisis del crédito rural en Brasil, PF vs PJ. Fuente: Banco Central de Brasil (SGS)."},
    "inad": {"pt": "Inadimplência", "en": "Delinquency", "es": "Morosidad"},
    "juros": {"pt": "Custo do Crédito (Juros)", "en": "Credit Cost (Interest)", "es": "Costo del Crédito"},
    "insight": {"pt": "Leitura executiva", "en": "Executive reading", "es": "Lectura ejecutiva"},
    "mm": {"pt": "vs mês anterior", "en": "vs prev. month", "es": "vs mes anterior"},
    "aa": {"pt": "vs ano anterior", "en": "vs prev. year", "es": "vs año anterior"},
    "avg": {"pt": "Média R12", "en": "12M avg", "es": "Prom R12"},
    "fechamentos": {"pt": "Fechamento anual", "en": "Year-end close", "es": "Cierre anual"},
    "range": {"pt": "Faixa histórica", "en": "Historical range", "es": "Rango histórico"},
    "source": {"pt": "Fonte", "en": "Source", "es": "Fuente"},
    "glossary": {"pt": "Glossário — o que significa cada indicador",
                 "en": "Glossary — what each indicator means",
                 "es": "Glosario"},
    "pf": {"pt": "Pessoa Física (produtor individual)", "en": "Individuals (individual farmer)", "es": "Persona Física"},
    "pj": {"pt": "Pessoa Jurídica (empresas e cooperativas)", "en": "Corporate (companies & co-ops)", "es": "Persona Jurídica"},
    # nota que explica a estrutura Total = Reguladas + Mercado, e a diferença PF/PJ
    "nota_estrutura": {
        "pt": "Como ler: o <b>Total</b> é a visão consolidada; abaixo dele, a composição por origem do recurso — <b>Reguladas</b> (crédito subsidiado, ex. Plano Safra) e <b>Mercado</b> (crédito livre). Para Pessoa Jurídica, o Banco Central não publica a série separada de \\\"Mercado\\\", pois o crédito rural PJ é majoritariamente regulado — por isso a coluna PJ mostra apenas Total e Reguladas.",
        "en": "How to read: <b>Total</b> is the consolidated view; below it, the split by funding source — <b>Regulated</b> (subsidized, e.g. Plano Safra) and <b>Market</b> (free credit). For corporates, the Central Bank does not publish a separate \\\"Market\\\" series, as corporate rural credit is mostly regulated — hence the PJ column shows only Total and Regulated.",
        "es": "Cómo leer: el <b>Total</b> es la vista consolidada; debajo, la composición por origen — <b>Reguladas</b> (subsidiado) y <b>Mercado</b> (libre). Para PJ el Banco Central no publica \\\"Mercado\\\" por separado.",
    },
}

# Glossário: conceito por trás de cada rótulo (para dar credibilidade)
GLOSSARIO = [
    {"termo": {"pt": "Inadimplência", "en": "Delinquency", "es": "Morosidad"},
     "def": {"pt": "% da carteira de crédito rural com parcelas em atraso superior a 90 dias. Quanto menor, mais saudável a situação financeira do produtor.",
             "en": "% of the rural credit portfolio overdue by more than 90 days. Lower is healthier.",
             "es": "% de la cartera con atraso superior a 90 días."}},
    {"termo": {"pt": "Juros (% a.a.)", "en": "Interest (% p.a.)", "es": "Interés (% a.a.)"},
     "def": {"pt": "Taxa média anual cobrada nas novas operações de crédito rural, ponderada pelo valor das concessões. Quanto menor, mais barato o crédito.",
             "en": "Average annual rate on new rural credit operations, weighted by loan value. Lower means cheaper credit.",
             "es": "Tasa media anual de las nuevas operaciones de crédito rural."}},
    {"termo": {"pt": "Taxas Reguladas", "en": "Regulated rates", "es": "Tasas reguladas"},
     "def": {"pt": "Crédito com taxas definidas pelo governo (ex.: Plano Safra, Pronaf). Subsidiado, geralmente mais barato e com menor inadimplência.",
             "en": "Credit with government-set rates (e.g. Plano Safra, Pronaf). Subsidized, usually cheaper and less delinquent.",
             "es": "Crédito con tasas definidas por el gobierno (Plan Safra, Pronaf)."}},
    {"termo": {"pt": "Taxas de Mercado", "en": "Market rates", "es": "Tasas de mercado"},
     "def": {"pt": "Crédito com taxas livres, definidas pelos bancos. Não subsidiado, geralmente mais caro e com maior inadimplência.",
             "en": "Credit with free bank-set rates. Not subsidized, usually costlier and more delinquent.",
             "es": "Crédito con tasas libres definidas por los bancos."}},
    {"termo": {"pt": "PF vs PJ", "en": "Individuals vs Corporate", "es": "PF vs PJ"},
     "def": {"pt": "PF = produtor pessoa física (individual). PJ = empresas rurais e cooperativas. Comparar os dois revela onde o risco de crédito está concentrado.",
             "en": "Individuals vs rural companies/co-ops. Comparing both shows where credit risk concentrates.",
             "es": "Persona Física (productor) vs Persona Jurídica (empresas/cooperativas)."}},
    {"termo": {"pt": "Percentil histórico", "en": "Historical percentile", "es": "Percentil histórico"},
     "def": {"pt": "Posição do valor atual dentro da série disponível (20 meses). Ex.: 90% = perto do maior valor já registrado no período.",
             "en": "Position of the current value within the available series (20 months).",
             "es": "Posición del valor actual dentro de la serie disponible."}},
]


def _a(d): return f'data-pt="{d["pt"]}" data-en="{d["en"]}" data-es="{d["es"]}"'


def _fmt(v, unidade):
    """Formata valor com sufixo % quando aplicável, ou '—' se ausente."""
    if v is None:
        return "—"
    suf = "%" if unidade == "%" else ""
    return f"{v:.2f}{suf}"


def _farol_por_tendencia(tend):
    """Reaproveita as classes farol do Early Signals. Menor=melhor -> baixa=verde."""
    mapa = {
        "baixa": ("farol-positive", {"pt": "Melhorando", "en": "Improving", "es": "Mejorando"}),
        "alta":  ("farol-critical", {"pt": "Piorando", "en": "Worsening", "es": "Empeorando"}),
    }
    return mapa.get(tend, ("farol-warning", {"pt": "Estável", "en": "Stable", "es": "Estable"}))


def _icone_por_tipo(grupo, tipo):
    if grupo == "juros":
        return "💰"
    return {"Total": "📊", "Reguladas": "🏛️", "Mercado": "🏦"}.get(tipo, "📊")


def _classe_card(tend):
    return {"baixa": "tendencia-positiva", "alta": "tendencia-negativa"}.get(tend, "tendencia-neutra")


def _delta_txt(v, sufixo="p.p."):
    if v is None:
        return '<span class="cr-neutral">—</span>'
    if v > 0:
        return f'<span class="cr-down">▲ +{v:.2f} {sufixo}</span>'
    if v < 0:
        return f'<span class="cr-up">▼ {v:.2f} {sufixo}</span>'
    return f'<span class="cr-neutral">▬ {v:.2f} {sufixo}</span>'


def _card(r):
    """Card no padrão analysis-card do Early Signals."""
    farol_cls, farol_rot = _farol_por_tendencia(r["tendencia"])
    card_cls = _classe_card(r["tendencia"])
    icone = _icone_por_tipo(r["grupo"], r["tipo"])
    unidade = r["unidade"]

    return f'''
        <div class="analysis-card {card_cls} cr-card">
            <div class="analysis-header">
                <span class="analysis-icon">{icone}</span>
                <h3 class="analysis-card-title">{r["tipo"]}</h3>
                <span class="farol {farol_cls}"><span class="farol-dot"></span><span {_a(farol_rot)}>{farol_rot["pt"]}</span></span>
            </div>
            <div class="cr-value-row">
                <span class="cr-value">{r["atual"]:.2f}</span>
                <span class="cr-unit">{unidade}</span>
                <span class="cr-ref">{r["mes_ref"]}</span>
            </div>
            <div class="cr-deltas">
                <div class="cr-delta-item"><span class="cr-delta-lbl" {_a(TR["mm"])}>{TR["mm"]["pt"]}</span>{_delta_txt(r["delta_pp"])}</div>
                <div class="cr-delta-item"><span class="cr-delta-lbl" {_a(TR["aa"])}>{TR["aa"]["pt"]}</span>{_delta_txt(r.get("delta_aa"))}</div>
            </div>
            <div class="cr-fech">
                <span class="cr-fech-lbl" {_a(TR["fechamentos"])}>{TR["fechamentos"]["pt"]}</span>
                <div class="cr-fech-vals">
                    <span class="cr-fech-item">{r.get("fech_ano2_label","")}: <b>{_fmt(r.get("fech_ano2"), unidade)}</b></span>
                    <span class="cr-fech-item">{r.get("fech_ano1_label","")}: <b>{_fmt(r.get("fech_ano1"), unidade)}</b></span>
                </div>
            </div>
            <div class="cr-hist">
                <span class="cr-hist-item"><span class="cr-hist-lbl" {_a(TR["avg"])}>{TR["avg"]["pt"]}</span> {_fmt(r.get("media_r12"), unidade)}</span>
                <span class="cr-hist-item"><span class="cr-hist-lbl" {_a(TR["range"])}>{TR["range"]["pt"]}</span> {r["minimo"]:.2f} – {r["maximo"]:.2f}</span>
            </div>
        </div>'''


def _coluna(pessoa_label, series):
    if not series:
        return ""
    ordenados = sorted(series, key=lambda x: (x["tipo"] != "Total", x["tipo"]))
    cards = "".join(_card(r) for r in ordenados)
    return f'''
        <div class="cr-coluna">
            <div class="cr-coluna-head" {_a(pessoa_label)}>{pessoa_label["pt"]}</div>
            {cards}
        </div>'''


def _secao(titulo_label, grupo_dados, mostrar_nota=False):
    pf = grupo_dados.get("PF", [])
    pj = grupo_dados.get("PJ", [])
    if not pf and not pj:
        return ""
    nota = (f'<div class="cr-nota"><span {_a(TR["nota_estrutura"])}>{TR["nota_estrutura"]["pt"]}</span></div>'
            if mostrar_nota else "")
    return f'''
    <h2 class="section-title" {_a(titulo_label)}>{titulo_label["pt"]}</h2>
    {nota}
    <div class="cr-pfpj">
        {_coluna(TR["pf"], pf)}
        {_coluna(TR["pj"], pj)}
    </div>'''


def _glossario():
    itens = ""
    for g in GLOSSARIO:
        itens += (f'<div class="cr-gloss-item">'
                  f'<span class="cr-gloss-termo" {_a(g["termo"])}>{g["termo"]["pt"]}</span>'
                  f'<span class="cr-gloss-def" {_a(g["def"])}>{g["def"]["pt"]}</span>'
                  f'</div>')
    return (f'<details class="cr-gloss"><summary {_a(TR["glossary"])}>📖 {TR["glossary"]["pt"]}</summary>'
            f'<div class="cr-gloss-body">{itens}</div></details>')


def gerar_bloco_credito_rural(dados):
    if not dados or not dados.get("disponivel"):
        return ('<div class="analysis-grid"><p data-pt="Dados de crédito rural indisponíveis no momento." '
                'data-en="Rural credit data unavailable." data-es="Datos no disponibles.">'
                'Dados de crédito rural indisponíveis no momento.</p></div>')

    html = f'<p class="cr-subtitle" {_a(TR["subtitle"])}>{TR["subtitle"]["pt"]}</p>'

    ins = dados.get("insight")
    if ins:
        html += (f'<div class="cr-insight">💡 '
                 f'<strong {_a(TR["insight"])}>{TR["insight"]["pt"]}:</strong> '
                 f'<span {_a(ins)}>{ins["pt"]}</span></div>')

    html += _glossario()
    html += _secao(TR["inad"], dados.get("inadimplencia", {}), mostrar_nota=True)
    html += _secao(TR["juros"], dados.get("juros", {}), mostrar_nota=False)
    html += (f'<p class="cr-fonte"><strong {_a(TR["source"])}>{TR["source"]["pt"]}:</strong> '
             f'Banco Central do Brasil — Sistema Gerenciador de Séries Temporais (SGS). '
             f'Séries mensais, atualizadas automaticamente.</p>')
    return html


CSS_CREDITO_RURAL = """
<style>
.cr-subtitle { font-size:13px; color:#555; line-height:1.6; margin:0 0 16px; max-width:900px; }
.cr-insight { background:#eef4ff; border-left:5px solid #1a56db; color:#1e3a8a; padding:13px 18px; margin-bottom:20px; font-size:13.5px; border-radius:4px; line-height:1.55; }
/* Glossário colapsável */
.cr-gloss { background:var(--agco-light-gray); border:1px solid #e0e0e0; border-radius:6px; margin-bottom:28px; }
.cr-gloss summary { cursor:pointer; padding:12px 18px; font-weight:700; font-size:13px; color:var(--agco-dark-gray); text-transform:uppercase; letter-spacing:.4px; user-select:none; }
.cr-gloss summary:hover { color:var(--agco-red); }
.cr-gloss-body { padding:6px 18px 16px; display:grid; grid-template-columns:1fr 1fr; gap:12px 22px; }
@media (max-width:768px){ .cr-gloss-body { grid-template-columns:1fr; } }
.cr-gloss-item { display:flex; flex-direction:column; gap:3px; }
.cr-gloss-termo { font-size:12px; font-weight:800; color:var(--agco-red); text-transform:uppercase; letter-spacing:.3px; }
.cr-gloss-def { font-size:12.5px; color:#555; line-height:1.5; }
/* Seções PF/PJ */
.cr-pfpj { display:grid; grid-template-columns:1fr 1fr; gap:22px; margin-bottom:30px; }
@media (max-width:768px){ .cr-pfpj { grid-template-columns:1fr; } }
.cr-coluna-head { font-size:12px; font-weight:800; color:#fff; background:var(--agco-black); padding:8px 14px; border-radius:4px; text-transform:uppercase; letter-spacing:.5px; margin-bottom:14px; }
/* Card (herda analysis-card do template, ajustes específicos) */
.cr-card { margin-bottom:14px; }
.cr-value-row { display:flex; align-items:baseline; gap:8px; margin-bottom:12px; }
.cr-value { font-size:30px; font-weight:900; color:var(--agco-black); letter-spacing:-1px; line-height:1; }
.cr-unit { font-size:13px; color:#888; font-weight:600; }
.cr-ref { font-size:10px; color:#aaa; margin-left:auto; text-transform:uppercase; letter-spacing:.5px; }
.cr-deltas { display:grid; grid-template-columns:1fr 1fr; gap:10px; padding:10px 0; border-top:1px solid #f1f3f5; border-bottom:1px solid #f1f3f5; }
.cr-delta-item { display:flex; flex-direction:column; gap:3px; }
.cr-delta-lbl { font-size:10px; color:#888; text-transform:uppercase; letter-spacing:.4px; font-weight:600; }
.cr-up { color:#2e7d32; font-weight:800; font-size:14px; }
.cr-down { color:#c62828; font-weight:800; font-size:14px; }
.cr-neutral { color:#f9a825; font-weight:800; font-size:14px; }
.cr-nota { background:#f8f9fa; border:1px dashed #ccc; border-radius:5px; padding:10px 14px; margin-bottom:16px; font-size:12px; color:#555; line-height:1.55; }
.cr-nota b { color:var(--agco-dark-gray); }
.cr-fech { margin-top:10px; padding-top:8px; }
.cr-fech-lbl { font-size:9.5px; color:#999; text-transform:uppercase; letter-spacing:.3px; font-weight:700; display:block; margin-bottom:4px; }
.cr-fech-vals { display:flex; gap:16px; }
.cr-fech-item { font-size:12px; color:#666; }
.cr-fech-item b { color:var(--agco-black); font-weight:800; }
.cr-hist { display:flex; justify-content:space-between; gap:12px; margin-top:10px; padding-top:8px; border-top:1px solid #f1f3f5; font-size:11.5px; color:#666; }
.cr-hist-item { display:flex; flex-direction:column; gap:2px; }
.cr-hist-lbl { font-size:9.5px; color:#999; text-transform:uppercase; letter-spacing:.3px; font-weight:700; }
.cr-fonte { font-size:11px; color:#999; font-style:italic; border-top:1px solid #f0f0f0; padding-top:14px; margin-top:6px; }
</style>
"""
