# ==========================================================================
# RENDERIZADOR HTML — MARGEM & CUSTO AGRÍCOLA (CONAB)
# Padrão visual Early Signals (analysis-card + farol). Por cultura × UF × safra.
# Adaptativo: mostra Margem se houver; senão, Custo total/ha. + glossário + fonte.
# ==========================================================================

TR = {
    "subtitle": {
        "pt": "Rentabilidade e custo de produção agrícola por cultura, região (UF) e safra. Fonte oficial: CONAB — Companhia Nacional de Abastecimento.",
        "en": "Agricultural profitability and production cost by crop, region (state) and crop-year. Official source: CONAB (Brazil).",
        "es": "Rentabilidad y costo de producción por cultivo, región y zafra. Fuente: CONAB (Brasil)."},
    "margem": {"pt": "Margem", "en": "Margin", "es": "Margen"},
    "custo": {"pt": "Custo total/ha", "en": "Total cost/ha", "es": "Costo total/ha"},
    "receita": {"pt": "Receita/ha", "en": "Revenue/ha", "es": "Ingreso/ha"},
    "produt": {"pt": "Produtividade", "en": "Yield", "es": "Productividad"},
    "preco": {"pt": "Preço recebido", "en": "Price received", "es": "Precio recibido"},
    "safra": {"pt": "Safra", "en": "Crop-year", "es": "Zafra"},
    "source": {"pt": "Fonte", "en": "Source", "es": "Fuente"},
    "glossary": {"pt": "Glossário — o que significa cada indicador",
                 "en": "Glossary — what each indicator means", "es": "Glosario"},
    "aviso_custo": {
        "pt": "Para estas culturas a CONAB disponibiliza o CUSTO DE PRODUÇÃO oficial. A margem final depende do preço de venda praticado por cada produtor.",
        "en": "For these crops CONAB provides the official PRODUCTION COST. Final margin depends on each farmer's selling price.",
        "es": "Para estos cultivos CONAB publica el COSTO DE PRODUCCIÓN oficial."},
}

GLOSSARIO = [
    {"termo": {"pt": "Margem líquida", "en": "Net margin", "es": "Margen neto"},
     "def": {"pt": "Receita menos TODOS os custos (variável + fixo). Se negativa, há prejuízo mesmo com boa colheita.",
             "en": "Revenue minus all costs (variable + fixed). Negative = loss.",
             "es": "Ingreso menos todos los costos."}},
    {"termo": {"pt": "Custo total/ha", "en": "Total cost/ha", "es": "Costo total/ha"},
     "def": {"pt": "Soma de todos os custos por hectare (sementes, fertilizantes, defensivos, operações) pela metodologia oficial da CONAB.",
             "en": "Sum of all per-hectare costs per CONAB's methodology.",
             "es": "Suma de todos los costos por hectárea (CONAB)."}},
    {"termo": {"pt": "Safra", "en": "Crop-year", "es": "Zafra"},
     "def": {"pt": "Ano-safra de referência (ex.: 2024/25). Permite comparar a mesma cultura entre anos.",
             "en": "Reference crop-year (e.g., 2024/25).",
             "es": "Año-zafra de referencia."}},
    {"termo": {"pt": "Região (UF)", "en": "Region (State)", "es": "Región"},
     "def": {"pt": "Unidade da Federação onde o custo foi levantado (ex.: MT, PR, RS). Custos variam muito por região.",
             "en": "State where the cost was surveyed (e.g., MT, PR, RS).",
             "es": "Estado donde se relevó el costo."}},
]


def _a(d): return f'data-pt="{d["pt"]}" data-en="{d["en"]}" data-es="{d["es"]}"'


def _fmt(v, prefixo="R$ ", sufixo=""):
    if v is None:
        return "—"
    return f"{prefixo}{v:,.2f}{sufixo}"


def _farol(tend):
    mapa = {
        "positivo": ("farol-positive", {"pt": "Lucro", "en": "Profit", "es": "Ganancia"}),
        "negativo": ("farol-critical", {"pt": "Prejuízo", "en": "Loss", "es": "Pérdida"}),
    }
    return mapa.get(tend, ("farol-warning", {"pt": "Neutro", "en": "Neutral", "es": "Neutral"}))


def _classe_card(tend):
    return {"positivo": "tendencia-positiva", "negativo": "tendencia-negativa"}.get(tend, "tendencia-neutra")


def _glossario():
    itens = ""
    for g in GLOSSARIO:
        itens += (f'<div class="mg-gloss-item">'
                  f'<span class="mg-gloss-termo" {_a(g["termo"])}>{g["termo"]["pt"]}</span>'
                  f'<span class="mg-gloss-def" {_a(g["def"])}>{g["def"]["pt"]}</span></div>')
    return (f'<details class="mg-gloss"><summary {_a(TR["glossary"])}>📖 {TR["glossary"]["pt"]}</summary>'
            f'<div class="mg-gloss-body">{itens}</div></details>')


def _card(item):
    tend = item.get("tendencia", "incerto")
    farol_cls, farol_rot = _farol(tend)
    card_cls = _classe_card(tend)
    n = item["nome"]
    titulo = f'{n["pt"]} · {item["uf"]}'
    safra_txt = item.get("safra") or "—"

    if item.get("margem") is not None:
        destaque_lbl = TR["margem"]
        sinal = "+" if item["margem"] >= 0 else ""
        destaque_val = f'{sinal}{_fmt(item["margem"], sufixo="/ha")}'
    else:
        destaque_lbl = TR["custo"]
        destaque_val = _fmt(item.get("custo_total"), sufixo="/ha")

    linhas = f'<div class="mg-linha"><span class="mg-lbl" {_a(TR["safra"])}>{TR["safra"]["pt"]}</span><span class="mg-val">{safra_txt}</span></div>'
    linhas += f'<div class="mg-linha"><span class="mg-lbl" {_a(TR["custo"])}>{TR["custo"]["pt"]}</span><span class="mg-val">{_fmt(item.get("custo_total"))}</span></div>'
    if item.get("preco") is not None:
        linhas += f'<div class="mg-linha"><span class="mg-lbl" {_a(TR["preco"])}>{TR["preco"]["pt"]}</span><span class="mg-val">{_fmt(item.get("preco"))}</span></div>'
    if item.get("receita") is not None:
        linhas += f'<div class="mg-linha"><span class="mg-lbl" {_a(TR["receita"])}>{TR["receita"]["pt"]}</span><span class="mg-val">{_fmt(item.get("receita"))}</span></div>'
    prod = item.get("produtividade")
    linhas += f'<div class="mg-linha"><span class="mg-lbl" {_a(TR["produt"])}>{TR["produt"]["pt"]}</span><span class="mg-val">{prod if prod is not None else "—"}</span></div>'

    return f'''
        <div class="analysis-card {card_cls} mg-card">
            <div class="analysis-header">
                <span class="analysis-icon">{item["icone"]}</span>
                <h3 class="analysis-card-title">{titulo}</h3>
                <span class="farol {farol_cls}"><span class="farol-dot"></span><span {_a(farol_rot)}>{farol_rot["pt"]}</span></span>
            </div>
            <div class="mg-destaque">
                <span class="mg-destaque-lbl" {_a(destaque_lbl)}>{destaque_lbl["pt"]}</span>
                <span class="mg-destaque-val">{destaque_val}</span>
            </div>
            <div class="mg-linhas">{linhas}</div>
        </div>'''


def gerar_bloco_margem(dados):
    if not dados or not dados.get("disponivel"):
        return ('<div class="analysis-grid"><p data-pt="Dados de margem agrícola (CONAB) indisponíveis no momento." '
                'data-en="Agricultural margin data (CONAB) unavailable." data-es="Datos no disponibles.">'
                'Dados de margem agrícola (CONAB) indisponíveis no momento.</p></div>')

    html = f'<p class="mg-subtitle" {_a(TR["subtitle"])}>{TR["subtitle"]["pt"]}</p>'

    if dados.get("modo_dado") == "custo_oficial":
        html += (f'<div class="mg-insight">ℹ️ '
                 f'<span {_a(TR["aviso_custo"])}>{TR["aviso_custo"]["pt"]}</span></div>')

    html += _glossario()
    cards = "".join(_card(it) for it in dados.get("itens", []))
    html += f'<div class="analysis-grid">{cards}</div>'
    html += (f'<p class="mg-fonte"><strong {_a(TR["source"])}>{TR["source"]["pt"]}:</strong> '
             f'CONAB — Companhia Nacional de Abastecimento (Custo de Produção / Comparativo Rentabilidade). '
             f'Atualização conforme divulgação oficial da CONAB.</p>')
    return html


CSS_MARGEM = """
<style>
.mg-card { margin-bottom: 0; }
.mg-destaque { display:flex; flex-direction:column; gap:2px; margin-bottom:12px; padding-bottom:12px; border-bottom:1px solid #f1f3f5; }
.mg-destaque-lbl { font-size:10px; color:#888; text-transform:uppercase; letter-spacing:.4px; font-weight:700; }
.mg-destaque-val { font-size:26px; font-weight:900; color:var(--agco-black); letter-spacing:-.5px; }
.mg-linhas { display:flex; flex-direction:column; gap:7px; }
.mg-linha { display:flex; align-items:center; justify-content:space-between; gap:10px; }
.mg-lbl { font-size:11px; color:#6c757d; text-transform:uppercase; letter-spacing:.4px; font-weight:600; }
.mg-val { font-size:13px; font-weight:700; color:var(--agco-dark-gray); }
.mg-subtitle { font-size:13px; color:#555; line-height:1.6; margin:0 0 16px; max-width:900px; }
.mg-insight { background:#eef4ff; border-left:5px solid #1a56db; color:#1e3a8a; padding:12px 18px; margin-bottom:22px; font-size:13px; border-radius:4px; line-height:1.55; }
.mg-gloss { background:var(--agco-light-gray); border:1px solid #e0e0e0; border-radius:6px; margin-bottom:26px; }
.mg-gloss summary { cursor:pointer; padding:12px 18px; font-weight:700; font-size:13px; color:var(--agco-dark-gray); text-transform:uppercase; letter-spacing:.4px; user-select:none; }
.mg-gloss summary:hover { color:var(--agco-red); }
.mg-gloss-body { padding:6px 18px 16px; display:grid; grid-template-columns:1fr 1fr; gap:12px 22px; }
@media (max-width:768px){ .mg-gloss-body { grid-template-columns:1fr; } }
.mg-gloss-item { display:flex; flex-direction:column; gap:3px; }
.mg-gloss-termo { font-size:12px; font-weight:800; color:var(--agco-red); text-transform:uppercase; letter-spacing:.3px; }
.mg-gloss-def { font-size:12.5px; color:#555; line-height:1.5; }
.mg-fonte { font-size:11px; color:#999; font-style:italic; border-top:1px solid #f0f0f0; padding-top:14px; margin-top:20px; }
</style>
"""
