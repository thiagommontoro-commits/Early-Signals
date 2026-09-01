# -*- coding: utf-8 -*-
"""
render_margem_agricola.py  (v3.4 — safra anterior no dash + comparativo a/a)
===========================================================================
Renderiza a aba "Margem do Produtor" (metodologia CONAB COE/COT/CT). Cada
cartão traz, em destaque:
    • Margem Econômica da safra vigente (KPI principal)
    • Variação vs a safra anterior (▲/▼ % e R$/ha)  <<< comparativo a/a
    • Bloco explícito "2024/25 vs 2025/26" com os dois valores
    • Receita Bruta, Margem Bruta (−COE), Margem Econômica (−CT) como apoio

O cartão usa como vigente a última safra com dado real; o comparativo aparece
sempre que a safra anterior tiver margem real (nada inventado).

Interface: from render_margem_agricola import gerar_bloco_margem, CSS_MARGEM
Autoria: Global Reporting & Analytics — Thiago Montoro (AGCO)
"""

_ICO = {"Soja": "🌱", "Milho": "🌽", "Algodão": "🧵", "Trigo": "🌾", "Arroz": "🌾",
        "Feijão": "🫘", "Sorgo": "🌾", "Café": "☕", "Girassol": "🌻",
        "Amendoim": "🥜", "Cevada": "🌾", "Aveia": "🌾", "Canola": "🌼"}
_BADGE = {
    "alta":         ("pos", "Margem ↑"),
    "baixa":        ("neg", "Margem ↓"),
    "estavel":      ("neu", "Estável"),
    "indisponivel": ("neu", "S/ comparativo"),
}
_QUAL = {
    "completo":   ("q-ok",   "● Dado oficial"),
    "parcial":    ("q-warn", "◐ Contém dado repetido"),
    "incompleto": ("q-off",  "○ Indisponível"),
}


def _fmt(v, prefixo="R$ "):
    if v is None:
        return "—"
    return f"{prefixo}{v:,.0f}".replace(",", ".")


def _mk(status):
    return "*" if status == "repetido" else ""


def _delta_html(atual, ant):
    if atual is None or ant in (None, 0):
        return '<span class="dl">&nbsp;</span>'
    d = (atual - ant) / abs(ant) * 100.0
    cls, seta = ("up", "▲") if d >= 0 else ("dn", "▼")
    return f'<span class="dl {cls}">{seta} {abs(d):.0f}%</span>'


def _pontos_validos(serie, chave="margem_economica_ha"):
    return [(i, s) for i, s in enumerate(serie) if s.get(chave) is not None]


def _card_html(card):
    cultura, uf = card.get("cultura", "—"), card.get("uf", "—")
    serie = card.get("serie", []) or [{}]

    validos = _pontos_validos(serie)
    if validos:
        idx = validos[-1][0]
        idx_ant = validos[-2][0] if len(validos) >= 2 else None
    else:
        idx, idx_ant = len(serie) - 1, None

    vigente = serie[idx]
    anterior = serie[idx_ant] if idx_ant is not None else {}

    cls_badge, txt_badge = _BADGE.get(card.get("tendencia", "indisponivel"), ("neu", "S/ comparativo"))
    cls_card = cls_badge
    ico = _ICO.get(cultura, "🌱")
    unid = "@/ha" if card.get("unidade") == "arroba" else "sc/ha"

    q_cls, q_txt = _QUAL.get(vigente.get("status_geral", "incompleto"), ("q-off", "○ Indisponível"))

    receita = vigente.get("receita_ha")
    m_bruta = vigente.get("margem_bruta_ha")
    m_econ = vigente.get("margem_economica_ha")
    coe = vigente.get("coe_ha")
    ct = vigente.get("ct_ha")

    m_econ_ant = anterior.get("margem_economica_ha")
    safra_vig = vigente.get("safra", "—")
    safra_ant = anterior.get("safra", "safra anterior")

    # --- Comparativo a/a destacado ---
    if m_econ is not None and m_econ_ant not in (None, 0):
        dif = m_econ - m_econ_ant
        pct = dif / abs(m_econ_ant) * 100.0
        cls_cmp, seta = ("yoy-up", "▲") if dif >= 0 else ("yoy-dn", "▼")
        comparativo_html = (
            f'<div class="mc-yoy {cls_cmp}">'
            f'<span class="yoy-seta">{seta}</span> <b>{abs(pct):.0f}%</b> '
            f'vs {safra_ant} <span class="yoy-abs">({_fmt(dif)}/ha)</span></div>'
        )
    else:
        comparativo_html = ('<div class="mc-yoy yoy-na">Sem comparativo da safra anterior '
                            '(indisponível na fonte)</div>')

    # --- Bloco explícito das 2 safras ---
    linha_ant = (f'<div class="cmp-row"><span>{safra_ant}</span>'
                 f'<b>{_fmt(m_econ_ant)}/ha</b></div>') if m_econ_ant is not None else \
                (f'<div class="cmp-row cmp-off"><span>{safra_ant}</span><b>—</b></div>')
    linha_vig = (f'<div class="cmp-row cmp-latest"><span>{safra_vig}</span>'
                 f'<b>{_fmt(m_econ)}/ha</b></div>')
    comparativo_bloco = f'<div class="mc-cmp">{linha_ant}{linha_vig}</div>'

    spread = None
    if m_bruta is not None and m_econ is not None:
        spread = round(m_bruta - m_econ, 2)
    spread_html = ""
    if spread is not None and m_bruta not in (None, 0):
        pct = spread / abs(m_bruta) * 100.0 if m_bruta != 0 else 0
        spread_html = (f'<div class="mc-spread">Aperto econômico (terra+capital+deprec.): '
                       f'<b>{_fmt(spread)}/ha</b> · {pct:.0f}% da margem bruta</div>')

    d_receita = _delta_html(receita, anterior.get("receita_ha"))
    d_bruta = _delta_html(m_bruta, anterior.get("margem_bruta_ha"))
    d_econ = _delta_html(m_econ, m_econ_ant)

    return f"""
      <div class="margem-card {cls_card}">
        <div class="mc-head">
          <span class="mc-ico">{ico}</span>
          <span class="mc-title">{cultura}</span>
          <span class="mc-uf">{uf}</span>
          <span class="mc-badge {cls_badge}"><span class="d"></span>{txt_badge}</span>
        </div>
        <div class="mc-qual {q_cls}">{q_txt}</div>

        <div class="mc-kpi-label">Margem Econômica {safra_vig} · Receita − CT</div>
        <div class="mc-kpi {cls_card}">{_fmt(m_econ)}/ha</div>
        {comparativo_html}

        {comparativo_bloco}
        {spread_html}

        <div class="mc-kpis3">
          <div class="k3">
            <span class="k3l">Receita Bruta</span>
            <span class="k3v">{_fmt(receita)}</span>
            <span class="k3d">{d_receita}</span>
          </div>
          <div class="k3">
            <span class="k3l">Margem Bruta (−COE)</span>
            <span class="k3v">{_fmt(m_bruta)}</span>
            <span class="k3d">{d_bruta}</span>
          </div>
          <div class="k3">
            <span class="k3l">Margem Econ. (−CT)</span>
            <span class="k3v">{_fmt(m_econ)}</span>
            <span class="k3d">{d_econ}</span>
          </div>
        </div>

        <div class="mc-sub">Prod. <b>{('—' if vigente.get('produtividade') is None else f"{vigente.get('produtividade'):.0f} {unid}")}{_mk(vigente.get('produtividade_status','incompleto'))}</b> ·
             Preço <b>{_fmt(vigente.get('preco_medio'))}{_mk(vigente.get('preco_status','incompleto'))}</b> ·
             COE <b>{_fmt(coe)}</b> · CT <b>{_fmt(ct)}</b></div>
      </div>"""


def gerar_bloco_margem(dados_margem):
    if not dados_margem or not dados_margem.get("cards"):
        return ('<p style="color:#888;font-style:italic">Dados de margem indisponíveis no momento. '
                'A aba será populada automaticamente quando a CONAB/CEPEA responderem.</p>')

    cards_html = "".join(_card_html(c) for c in dados_margem["cards"])
    safras = " · ".join(dados_margem.get("safras", []))
    fontes = dados_margem.get("fontes", {})
    n_comp = dados_margem.get("n_com_comparativo", 0)
    n_total = dados_margem.get("n_combinacoes", 0)
    aviso = dados_margem.get("aviso")
    aviso_html = (f'<div class="margem-aviso">⚠ {aviso} — valores exibidos como "—".</div>'
                  if aviso else "")

    resumo_html = (
        f'<div class="margem-quality">'
        f'<span class="qp q-ok">✔ {n_comp} com comparativo 24/25 vs 25/26</span>'
        f'<span class="qp-total">de {n_total} culturas exibidas</span>'
        f'</div>'
    )

    metodologia_html = (
        '<div class="margem-metod">'
        '<b>Metodologia (CONAB):</b> '
        '<span class="mtag">Receita Bruta</span> = Produtividade × Preço CEPEA · '
        '<span class="mtag">Margem Bruta</span> = Receita − <b>COE</b> '
        '(custo operacional efetivo, "caixa") · '
        '<span class="mtag">Margem Econômica</span> = Receita − <b>CT</b> '
        '(custo total: caixa + depreciação + remuneração de terra e capital). '
        'O <b>Aperto econômico</b> (Margem Bruta − Margem Econômica) mede quanto do '
        'resultado é consumido por terra/capital — sinal antecedente de decisão de '
        'investimento em máquinas.'
        '</div>'
    )

    legenda_html = (
        '<div class="margem-legenda-prov">'
        '<b>Nota:</b> cada cartão traz a <b>Margem Econômica da safra vigente</b> e a '
        '<b>variação vs a safra anterior</b> (comparativo ano-a-ano). Culturas com '
        'valores fora de faixa plausível (erro de preço/custo na fonte) são '
        '<b>automaticamente removidas</b> — nenhum número irreal é exibido e nada é inventado.'
        '</div>'
    )

    rodape = (f"COE/COT/CT conforme metodologia de custos da CONAB · "
              f"Custo: {fontes.get('custo','CONAB')} · Produtividade: "
              f"{fontes.get('produtividade','CONAB (GEASA)')} · Preço: "
              f"{fontes.get('preco','CEPEA/ESALQ')}. "
              f"Atualizado em {dados_margem.get('gerado_em','')[:10]}.")

    return f"""
    <div class="margem-legend">Comparativo das últimas safras (<b>{safras}</b>) · foco na <b>variação da Margem Econômica ano-a-ano</b>, com Receita Bruta, Margem Bruta (−COE) e Margem Econômica (−CT).</div>
    {resumo_html}
    {metodologia_html}
    {legenda_html}
    {aviso_html}
    <div class="margem-grid">{cards_html}</div>
    <div class="margem-foot">{rodape}<br><i>{dados_margem.get('autoria','')}</i></div>"""


CSS_MARGEM = """
<style>
/* ===== EARLY SIGNALS · Aba Margem do Produtor v3.4 (CONAB COE/COT/CT) ===== */
.margem-legend { font-size:12px; color:#555; background:#f4f4f4; border-left:5px solid #cc0000; border-radius:4px; padding:10px 18px; margin-bottom:14px; font-weight:600; }
.margem-legend b { color:#111; }
.margem-quality { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-bottom:12px; }
.margem-quality .qp { font-size:12px; font-weight:800; padding:4px 12px; border-radius:20px; }
.margem-quality .qp-total { font-size:11px; color:#888; font-weight:600; }
.q-ok { background:#e2f0d9; color:#2e7d32; }
.q-warn { background:#fff2cc; color:#7f6000; }
.q-off { background:#f0f0f0; color:#888; }
.margem-metod { font-size:11.5px; color:#444; background:#fff; border:1px solid #eee; border-left:4px solid #cc0000; border-radius:6px; padding:10px 15px; margin-bottom:12px; line-height:1.65; }
.margem-metod .mtag { font-weight:800; color:#cc0000; }
.margem-legenda-prov { font-size:11px; color:#555; background:#fff; border:1px dashed #d9d9d9; border-radius:6px; padding:8px 14px; margin-bottom:18px; line-height:1.6; }
.margem-aviso { background:#fff2cc; border-left:5px solid #ffc000; color:#7f6000; padding:10px 16px; border-radius:4px; font-size:12px; font-weight:700; margin-bottom:18px; }
.margem-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:18px; }
@media(max-width:600px){ .margem-grid { grid-template-columns:1fr; } }
.margem-card { background:#fff; border:1px solid #e0e0e0; border-top:4px solid #cc0000; border-radius:6px; box-shadow:0 2px 6px rgba(0,0,0,0.05); padding:18px; position:relative; overflow:hidden; transition:transform .2s,box-shadow .2s; }
.margem-card:hover { transform:translateY(-3px); box-shadow:0 8px 16px rgba(0,0,0,0.08); }
.margem-card.pos { border-top-color:#70ad47; }
.margem-card.neg { border-top-color:#c00000; }
.margem-card.neu { border-top-color:#ffc000; }
.mc-head { display:flex; align-items:center; gap:10px; margin-bottom:8px; }
.mc-ico { width:34px; height:34px; border-radius:8px; background:#f4f4f4; display:grid; place-items:center; font-size:18px; flex-shrink:0; }
.mc-title { font-weight:800; font-size:15px; text-transform:uppercase; color:#111; }
.mc-uf { font-size:10px; font-weight:800; color:#fff; background:#cc0000; padding:2px 7px; border-radius:3px; }
.mc-badge { margin-left:auto; font-size:10px; font-weight:800; letter-spacing:.4px; padding:3px 9px; border-radius:12px; display:inline-flex; align-items:center; gap:5px; text-transform:uppercase; white-space:nowrap; }
.mc-badge .d { width:7px; height:7px; border-radius:50%; }
.mc-badge.pos { background:#e2f0d9; color:#385723; } .mc-badge.pos .d { background:#70ad47; }
.mc-badge.neg { background:#fce4d6; color:#c65911; } .mc-badge.neg .d { background:#c00000; }
.mc-badge.neu { background:#fff2cc; color:#7f6000; } .mc-badge.neu .d { background:#ffc000; }
.mc-qual { display:inline-block; font-size:10px; font-weight:800; padding:2px 9px; border-radius:12px; margin-bottom:10px; }
.mc-qual.q-ok { background:#e2f0d9; color:#2e7d32; }
.mc-qual.q-warn { background:#fff2cc; color:#7f6000; }
.mc-qual.q-off { background:#f0f0f0; color:#888; }
.mc-kpi-label { font-size:10px; font-weight:700; letter-spacing:.6px; text-transform:uppercase; color:#888; }
.mc-kpi { font-size:26px; font-weight:900; line-height:1.05; margin:2px 0; letter-spacing:-1px; }
.mc-kpi.pos { color:#385723; } .mc-kpi.neg { color:#c65911; } .mc-kpi.neu { color:#111; }
/* Comparativo ano-a-ano em destaque */
.mc-yoy { display:inline-flex; align-items:center; gap:6px; font-size:12.5px; font-weight:800; padding:5px 11px; border-radius:20px; margin:4px 0 10px; }
.mc-yoy .yoy-seta { font-size:13px; }
.mc-yoy .yoy-abs { font-weight:700; opacity:.85; }
.mc-yoy.yoy-up { background:#e2f0d9; color:#2e7d32; }
.mc-yoy.yoy-dn { background:#fce4d6; color:#c0392b; }
.mc-yoy.yoy-na { background:#f0f0f0; color:#999; font-weight:600; font-size:11px; }
/* Bloco explícito das 2 safras */
.mc-cmp { border:1px solid #eee; border-radius:6px; overflow:hidden; margin-bottom:10px; }
.cmp-row { display:flex; justify-content:space-between; align-items:center; padding:7px 12px; font-size:12px; color:#555; background:#fafafa; }
.cmp-row + .cmp-row { border-top:1px solid #eee; }
.cmp-row b { color:#333; font-weight:800; }
.cmp-row.cmp-latest { background:#e2f0d9; color:#2e7d32; }
.cmp-row.cmp-latest b { color:#1e5e22; }
.cmp-row.cmp-off b { color:#bbb; }
.mc-spread { font-size:10.5px; color:#7f6000; background:#fff8e1; border:1px solid #ffe08a; border-radius:4px; padding:5px 9px; margin:2px 0 10px; line-height:1.35; }
.mc-spread b { color:#5f4a00; }
.mc-kpis3 { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin:6px 0 12px; }
.k3 { background:#fafafa; border:1px solid #eee; border-radius:6px; padding:8px 6px; text-align:center; display:flex; flex-direction:column; gap:3px; }
.k3l { font-size:8.5px; font-weight:700; color:#888; text-transform:uppercase; letter-spacing:.3px; line-height:1.2; min-height:22px; }
.k3v { font-size:13px; font-weight:800; color:#111; }
.k3d { font-size:10px; font-weight:700; }
.mc-sub { font-size:11px; color:#777; line-height:1.5; }
.mc-sub b { color:#333; font-weight:700; }
.dl.up { color:#2e7d32; } .dl.dn { color:#c62828; }
.margem-foot { margin-top:22px; font-size:11px; color:#999; line-height:1.6; font-style:italic; border-top:1px solid #f5f5f5; padding-top:12px; }
</style>
"""


if __name__ == "__main__":
    from modulo_margem_agricola import processar_margem_agricola
    print(gerar_bloco_margem(processar_margem_agricola()))
