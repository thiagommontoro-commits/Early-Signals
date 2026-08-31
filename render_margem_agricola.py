# -*- coding: utf-8 -*-
"""
render_margem_agricola.py  (v2 — com sinalização de PROVENIÊNCIA)
================================================================
Renderiza a aba "Margem do Produtor" mostrando EXPLICITAMENTE a qualidade/origem
de cada dado:

  ● Oficial      -> dado veio direto da CONAB/CEPEA para aquela safra
  ◐ Repetido     -> herdado da safra anterior (carry-forward; CONAB ainda não
                    publicou o novo ciclo) — sinalizado com "*" e cor âmbar
  ○ Indisponível -> fonte não retornou dado -> "—"

Interface (contrato do gerador):
    from render_margem_agricola import gerar_bloco_margem, CSS_MARGEM

Autoria: Global Reporting & Analytics — Thiago Montoro (AGCO)
"""

_ICO = {"Soja": "🌱", "Milho": "🌽", "Algodão": "🧵", "Trigo": "🌾"}
_BADGE = {
    "alta":         ("pos", "Margem ↑"),
    "baixa":        ("neg", "Margem ↓"),
    "estavel":      ("neu", "Estável"),
    "indisponivel": ("neu", "S/ dado"),
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


def _mk(valor, status):
    """Marca '*' quando o dado é repetido (carry-forward)."""
    return "*" if status == "repetido" else ""


def _card_html(card):
    cultura, uf = card["cultura"], card["uf"]
    serie = card["serie"]
    vigente = serie[-1]
    cls_badge, txt_badge = _BADGE.get(card.get("tendencia", "indisponivel"), ("neu", "S/ dado"))
    cls_card = cls_badge
    ico = _ICO.get(cultura, "🌱")
    unid = "@/ha" if card.get("unidade") == "arroba" else "sc/ha"

    q_cls, q_txt = _QUAL.get(vigente.get("status_geral", "incompleto"), ("q-off", "○ Indisponível"))

    minis = ""
    for i, s in enumerate(serie):
        margem = s["margem_ha"]
        is_last = (i == len(serie) - 1)
        cell_q = ""
        if s["status_geral"] == "parcial":
            cell_q = " sf-rep"
        elif s["status_geral"] == "incompleto":
            cell_q = " sf-off"
        delta_html = "&nbsp;"
        if i > 0:
            ant = serie[i - 1]["margem_ha"]
            if margem is not None and ant not in (None, 0):
                d = (margem - ant) / abs(ant) * 100.0
                cls, seta = ("up", "▲") if d >= 0 else ("dn", "▼")
                delta_html = f'<span class="dl {cls}">{seta} {abs(d):.0f}%</span>'
        marca = _mk(s["custo_total_ha"], s["custo_status"])
        minis += (
            f'<div class="sf{" latest" if is_last else ""}{cell_q}">'
            f'<div class="yr">{s["safra"]}</div>'
            f'<div class="mg">{_fmt(margem, "")}{marca}</div>'
            f'<div class="dl">{delta_html if i > 0 else "&nbsp;"}</div></div>'
        )

    custo_parts = []
    for s in serie:
        custo_parts.append(_fmt(s["custo_total_ha"], "") + _mk(s["custo_total_ha"], s["custo_status"]))
    custos = " → ".join(custo_parts)

    prod_txt = "—" if vigente["produtividade"] is None else f'{vigente["produtividade"]:.0f} {unid}'
    prod_txt += _mk(vigente["produtividade"], vigente["produtividade_status"])
    preco_mk = _mk(vigente["preco_medio"], vigente["preco_status"])

    return f"""
      <div class="margem-card {cls_card}">
        <div class="mc-head">
          <span class="mc-ico">{ico}</span>
          <span class="mc-title">{cultura}</span>
          <span class="mc-uf">{uf}</span>
          <span class="mc-badge {cls_badge}"><span class="d"></span>{txt_badge}</span>
        </div>
        <div class="mc-qual {q_cls}">{q_txt}</div>
        <div class="mc-kpi-label">Margem {vigente['safra']}</div>
        <div class="mc-kpi {cls_card}">{_fmt(vigente['margem_ha'])}/ha</div>
        <div class="mc-sub">Receita <b>{_fmt(vigente['receita_ha'])}{preco_mk}</b> ·
             Custo <b>{_fmt(vigente['custo_total_ha'])}{_mk(vigente['custo_total_ha'], vigente['custo_status'])}</b> ·
             Prod. <b>{prod_txt}</b></div>
        <div class="mc-mini">
          <div class="mc-mini-h"><span>Margem por safra</span><span>Δ a/a</span></div>
          <div class="mc-safras">{minis}</div>
          <div class="mc-cost"><span>Custo total (ref.)</span><span><b>R$ {custos}</b></span></div>
        </div>
      </div>"""


def gerar_bloco_margem(dados_margem):
    if not dados_margem or not dados_margem.get("cards"):
        return ('<p style="color:#888;font-style:italic">Dados de margem indisponíveis no momento. '
                'A aba será populada automaticamente quando a CONAB/CEPEA responderem.</p>')

    cards_html = "".join(_card_html(c) for c in dados_margem["cards"])
    safras = " · ".join(dados_margem.get("safras", []))
    fontes = dados_margem.get("fontes", {})
    rq = dados_margem.get("resumo_qualidade", {})
    aviso = dados_margem.get("aviso")
    aviso_html = (f'<div class="margem-aviso">⚠ {aviso} — valores exibidos como "—".</div>'
                  if aviso else "")

    resumo_html = ""
    if rq:
        resumo_html = (
            f'<div class="margem-quality">'
            f'<span class="qp q-ok">● {rq.get("completos",0)} oficiais</span>'
            f'<span class="qp q-warn">◐ {rq.get("parciais",0)} com dado repetido</span>'
            f'<span class="qp q-off">○ {rq.get("incompletos",0)} indisponíveis</span>'
            f'<span class="qp-total">de {rq.get("total",0)} pontos (8 culturas × 3 safras)</span>'
            f'</div>'
        )

    legenda_html = (
        '<div class="margem-legenda-prov">'
        '<b>Legenda de proveniência:</b> '
        '<span class="lg q-ok">● Oficial</span> = direto da fonte na safra · '
        '<span class="lg q-warn">◐ Repetido&nbsp;*</span> = herdado da safra anterior '
        '(CONAB ainda não publicou o novo ciclo) · '
        '<span class="lg q-off">○ Indisponível</span> = "—". '
        'O asterisco (*) marca o valor repetido no próprio número.'
        '</div>'
    )

    rodape = (f"Margem (R$/ha) = Receita (Produtividade × Preço) − Custo Total. "
              f"Custo/Produtividade: {fontes.get('custo','CONAB')} · "
              f"Preço: {fontes.get('preco','CEPEA/ESALQ')} (referência de mercado/porto; "
              f"pode não descontar frete regional). "
              f"Atualizado em {dados_margem.get('gerado_em','')[:10]}.")

    return f"""
    <div class="margem-legend">Comparativo das últimas 3 safras (<b>{safras}</b>) · foco em <b>Margem (R$/ha)</b>, com custo total como referência.</div>
    {resumo_html}
    {legenda_html}
    {aviso_html}
    <div class="margem-grid">{cards_html}</div>
    <div class="margem-foot">{rodape}<br><i>{dados_margem.get('autoria','')}</i></div>"""


CSS_MARGEM = """
<style>
/* ===== EARLY SIGNALS · Aba Margem do Produtor (CONAB + CEPEA) ===== */
.margem-legend { font-size:12px; color:#555; background:#f4f4f4; border-left:5px solid #cc0000; border-radius:4px; padding:10px 18px; margin-bottom:14px; font-weight:600; }
.margem-legend b { color:#111; }
.margem-quality { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-bottom:12px; }
.margem-quality .qp { font-size:12px; font-weight:800; padding:4px 12px; border-radius:20px; }
.margem-quality .qp-total { font-size:11px; color:#888; font-weight:600; }
.q-ok { background:#e2f0d9; color:#2e7d32; }
.q-warn { background:#fff2cc; color:#7f6000; }
.q-off { background:#f0f0f0; color:#888; }
.margem-legenda-prov { font-size:11px; color:#555; background:#fff; border:1px dashed #d9d9d9; border-radius:6px; padding:8px 14px; margin-bottom:18px; line-height:1.6; }
.margem-legenda-prov .lg { font-weight:800; padding:1px 8px; border-radius:12px; }
.margem-aviso { background:#fff2cc; border-left:5px solid #ffc000; color:#7f6000; padding:10px 16px; border-radius:4px; font-size:12px; font-weight:700; margin-bottom:18px; }
.margem-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:18px; }
@media(max-width:1050px){ .margem-grid { grid-template-columns:repeat(2,1fr); } }
@media(max-width:600px){ .margem-grid { grid-template-columns:1fr; } }
.margem-card { background:#fff; border:1px solid #e0e0e0; border-top:4px solid #cc0000; border-radius:6px; box-shadow:0 2px 6px rgba(0,0,0,0.05); padding:18px; position:relative; overflow:hidden; transition:transform .2s,box-shadow .2s; }
.margem-card:hover { transform:translateY(-3px); box-shadow:0 8px 16px rgba(0,0,0,0.08); }
.margem-card.pos { border-top-color:#70ad47; }
.margem-card.neg { border-top-color:#c00000; animation:blink-critical 1.3s ease-in-out infinite; }
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
.mc-kpi { font-size:27px; font-weight:900; line-height:1.05; margin:2px 0; letter-spacing:-1px; }
.mc-kpi.pos { color:#385723; } .mc-kpi.neg { color:#c65911; } .mc-kpi.neu { color:#111; }
.mc-sub { font-size:11.5px; color:#777; margin-bottom:12px; }
.mc-sub b { color:#333; font-weight:700; }
.mc-mini { border-top:1px dashed #e0e0e0; padding-top:10px; }
.mc-mini-h { display:flex; justify-content:space-between; font-size:9.5px; font-weight:700; letter-spacing:.5px; text-transform:uppercase; color:#888; margin-bottom:8px; }
.mc-safras { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }
.sf { background:#fafafa; border:1px solid #eee; border-radius:6px; padding:7px 8px; text-align:center; }
.sf.latest { background:#e2f0d9; border-color:#bfe7cd; }
.sf.sf-rep { background:#fff8e1; border-color:#ffe08a; }
.sf.sf-off { background:#f5f5f5; border-color:#e6e6e6; }
.sf .yr { font-size:10px; font-weight:700; color:#888; }
.sf .mg { font-size:13.5px; font-weight:800; margin:2px 0; color:#385723; }
.sf.sf-off .mg { color:#bbb; }
.sf .dl { font-size:10px; font-weight:700; }
.sf .dl.up { color:#2e7d32; } .sf .dl.dn { color:#c62828; }
.mc-cost { margin-top:9px; font-size:11px; color:#777; display:flex; justify-content:space-between; border-top:1px dashed #e0e0e0; padding-top:8px; gap:8px; }
.mc-cost b { color:#333; }
.margem-foot { margin-top:22px; font-size:11px; color:#999; line-height:1.6; font-style:italic; border-top:1px solid #f5f5f5; padding-top:12px; }
</style>
"""


if __name__ == "__main__":
    from modulo_margem_agricola import processar_margem_agricola
    print(gerar_bloco_margem(processar_margem_agricola()))
