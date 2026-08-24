# ==========================================================================
# RENDERIZADOR HTML - COMMODITY INTELLIGENCE
# Reaproveita as classes visuais do dashboard (farol) + estilos próprios.
# Inclui banner de alerta caso os dados estejam desatualizados (Camada 4).
# ==========================================================================

LABELS = {
    "mm":       {"pt": "vs mês anterior",   "en": "vs prev. month",      "es": "vs mes anterior"},
    "aa":       {"pt": "vs ano anterior",   "en": "vs prev. year",       "es": "vs prev. year"},
    "avg5":     {"pt": "Média 5 anos",      "en": "5-year average",      "es": "Media 5 años"},
    "position": {"pt": "Posição histórica", "en": "Historical position", "es": "Posición histórica"},
    "source":   {"pt": "Fonte",             "en": "Source",              "es": "Fuente"},
    "ranking":  {"pt": "Ranking de Momento (percentil histórico)",
                 "en": "Momentum Ranking (historical percentile)",
                 "es": "Ranking de Momento (percentil histórico)"},
}
FAROL_TXT = {"positive": {"pt": "Positivo", "en": "Positive", "es": "Positivo"},
             "critical": {"pt": "Crítico", "en": "Critical", "es": "Crítico"},
             "warning":  {"pt": "Atenção", "en": "Warning", "es": "Atención"}}


def _a(d): return f'data-pt="{d["pt"]}" data-en="{d["en"]}" data-es="{d["es"]}"'
def _fclass(t): return {"positivo": "farol-positive", "negativo": "farol-critical"}.get(t, "farol-warning")
def _fkey(t):   return {"positivo": "positive", "negativo": "critical"}.get(t, "warning")


def _delta(v):
    if v is None: return '<span class="delta-neutral">—</span>'
    if v > 0:  return f'<span class="delta-up">▲ +{v:.1f}%</span>'
    if v < 0:  return f'<span class="delta-down">▼ {v:.1f}%</span>'
    return f'<span class="delta-neutral">▬ {v:.1f}%</span>'


def _barra(p):
    p = p if p is not None else 0
    return (f'<div class="perc-bar-track"><div class="perc-bar-fill" style="width:{p:.0f}%;"></div>'
            f'<span class="perc-bar-label">{p:.0f}%</span></div>')


def gerar_bloco_commodities(commodities, aviso_frescor=None):
    if not commodities:
        return ('<div class="news-grid"><p data-pt="Dados de commodities indisponíveis." '
                'data-en="Commodity data unavailable." data-es="Datos no disponibles.">'
                'Dados de commodities indisponíveis.</p></div>')

    banner = ""
    if aviso_frescor:
        banner = ('<div class="stale-data-banner">⚠️ '
                  '<span data-pt="Dados possivelmente desatualizados — verifique a atualização mensal da planilha do consultor." '
                  'data-en="Data possibly outdated — check the monthly consultant spreadsheet update." '
                  'data-es="Datos posiblemente desactualizados — verifique la actualización mensual.">'
                  'Dados possivelmente desatualizados — verifique a atualização mensal da planilha do consultor.'
                  '</span></div>')

    cards = '<div class="commodity-grid">\n'
    for c in commodities:
        fclass, ftxt = _fclass(c["tendencia"]), FAROL_TXT[_fkey(c["tendencia"])]
        n = c["nome"]
        neg = 'tendencia-negativa' if c['tendencia'] == 'negativo' else ''
        cards += f'''
        <div class="commodity-card {neg}">
            <div class="commodity-head">
                <span class="commodity-icon">{c["icone"]}</span>
                <h3 class="commodity-name" data-pt="{n['pt']}" data-en="{n['en']}" data-es="{n['es']}">{n['pt']}</h3>
                <span class="farol {fclass}"><span class="farol-dot"></span><span {_a(ftxt)}>{ftxt['pt']}</span></span>
            </div>
            <div class="commodity-price">
                <span class="price-value">{c["preco_atual"]:,.2f}</span>
                <span class="price-unit">{c["unidade"]}</span>
                <span class="price-ref">{c["mes_ref"]}</span>
            </div>
            <div class="commodity-metrics">
                <div class="metric"><span class="metric-label" {_a(LABELS['mm'])}>{LABELS['mm']['pt']}</span>{_delta(c["delta_mm"])}</div>
                <div class="metric"><span class="metric-label" {_a(LABELS['aa'])}>{LABELS['aa']['pt']}</span>{_delta(c["delta_aa"])}</div>
                <div class="metric"><span class="metric-label" {_a(LABELS['avg5'])}>{LABELS['avg5']['pt']}</span><span class="metric-val">{c["media_5a"]:,.2f}</span></div>
            </div>
            <div class="commodity-position">
                <span class="metric-label" {_a(LABELS['position'])}>{LABELS['position']['pt']}</span>
                {_barra(c["percentil"])}
            </div>
            <div class="commodity-source"><strong {_a(LABELS['source'])}>{LABELS['source']['pt']}:</strong> {c["fonte"]}</div>
        </div>'''
    cards += '\n</div>'

    ordenado = sorted(commodities, key=lambda x: (x["percentil"] or 0), reverse=True)
    ranking = f'<h2 class="section-title" {_a(LABELS["ranking"])}>{LABELS["ranking"]["pt"]}</h2>\n<div class="ranking-list">\n'
    for i, c in enumerate(ordenado, 1):
        n = c["nome"]
        ranking += f'''
        <div class="ranking-row">
            <span class="ranking-pos">{i}º</span><span class="ranking-icon">{c["icone"]}</span>
            <span class="ranking-name" data-pt="{n['pt']}" data-en="{n['en']}" data-es="{n['es']}">{n['pt']}</span>
            <span class="ranking-bar-track"><span class="ranking-bar-fill {_fclass(c['tendencia'])}" style="width:{(c['percentil'] or 0):.0f}%;"></span></span>
            <span class="ranking-perc">{(c['percentil'] or 0):.0f}%</span>
        </div>'''
    ranking += '\n</div>'
    return banner + '\n' + cards + '\n' + ranking


CSS_COMMODITIES = """
<style>
.stale-data-banner { background:#fff2cc; border-left:5px solid #ffc000; color:#7f6000; padding:12px 20px; margin-bottom:20px; font-size:13px; font-weight:700; border-radius:4px; }
.commodity-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:20px; margin-bottom:35px; }
.commodity-card { background:#fff; border:1px solid #e0e0e0; border-top:4px solid var(--agco-red); border-radius:6px; padding:20px; box-shadow:0 2px 6px rgba(0,0,0,0.05); display:flex; flex-direction:column; gap:15px; transition:transform .2s,box-shadow .2s; }
.commodity-card:hover { transform:translateY(-4px); box-shadow:0 8px 18px rgba(0,0,0,0.08); }
.commodity-card.tendencia-negativa { animation:blink-critical 1.3s ease-in-out infinite; }
.commodity-head { display:flex; align-items:center; gap:12px; }
.commodity-icon { font-size:26px; }
.commodity-name { font-size:16px; font-weight:800; color:var(--agco-black); margin:0; flex-grow:1; text-transform:uppercase; }
.commodity-price { display:flex; align-items:baseline; gap:8px; border-bottom:1px solid #f0f0f0; padding-bottom:12px; }
.price-value { font-size:32px; font-weight:900; color:var(--agco-black); letter-spacing:-1px; }
.price-unit { font-size:13px; color:#777; font-weight:600; }
.price-ref { font-size:11px; color:#aaa; margin-left:auto; text-transform:uppercase; letter-spacing:.5px; }
.commodity-metrics { display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; }
.metric { display:flex; flex-direction:column; gap:4px; }
.metric-label { font-size:10px; color:#888; text-transform:uppercase; letter-spacing:.5px; font-weight:600; }
.metric-val { font-size:15px; font-weight:700; color:var(--agco-dark-gray); }
.delta-up { font-size:15px; font-weight:700; color:#2e7d32; }
.delta-down { font-size:15px; font-weight:700; color:#c62828; }
.delta-neutral { font-size:15px; font-weight:700; color:#f9a825; }
.commodity-position { display:flex; flex-direction:column; gap:6px; }
.perc-bar-track { position:relative; background:#eee; border-radius:10px; height:18px; overflow:hidden; }
.perc-bar-fill { position:absolute; left:0; top:0; height:100%; background:linear-gradient(90deg,#70ad47,#ffc000,#c00000); border-radius:10px; }
.perc-bar-label { position:absolute; right:8px; top:50%; transform:translateY(-50%); font-size:11px; font-weight:700; color:#333; }
.commodity-source { font-size:11px; color:#999; font-style:italic; border-top:1px solid #f5f5f5; padding-top:8px; }
.ranking-list { display:flex; flex-direction:column; gap:8px; margin-top:10px; }
.ranking-row { display:flex; align-items:center; gap:12px; background:#fafafa; border:1px solid #eee; border-radius:6px; padding:10px 15px; }
.ranking-pos { font-size:16px; font-weight:900; color:var(--agco-red); width:32px; }
.ranking-icon { font-size:20px; }
.ranking-name { font-size:13px; font-weight:700; text-transform:uppercase; color:var(--agco-dark-gray); width:200px; }
.ranking-bar-track { flex-grow:1; background:#eee; border-radius:8px; height:14px; overflow:hidden; }
.ranking-bar-fill { display:block; height:100%; border-radius:8px; }
.ranking-bar-fill.farol-positive { background:#70ad47; }
.ranking-bar-fill.farol-critical { background:#c00000; }
.ranking-bar-fill.farol-warning { background:#ffc000; }
.ranking-perc { font-size:13px; font-weight:800; color:#333; width:45px; text-align:right; }
@media (max-width:600px){ .commodity-metrics{grid-template-columns:1fr 1fr;} .ranking-name{width:auto;} }
</style>
"""
