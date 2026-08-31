# -*- coding: utf-8 -*-
"""
render_margem_agricola.py
=========================
Renderiza a aba "Margem do Produtor" do Early Signals.

Interface (contrato usado por gerador_dashboard_early_signals.py):
    from render_margem_agricola import gerar_bloco_margem, CSS_MARGEM
    bloco_margem_html = gerar_bloco_margem(dados_margem)
    html_content = html_content.replace("{{BLOCO_MARGEM}}", bloco_margem_html)
    html_content = html_content.replace("</head>", CSS_MARGEM + "</head>")

- gerar_bloco_margem(dados_margem): recebe o dict de modulo_margem_agricola e
  devolve o HTML dos cards (número principal = MARGEM R$/ha, custo como referência,
  comparativo das últimas 3 safras dentro do card, badge de tendência).
- CSS_MARGEM: bloco <style> (padrão visual AGCO/farol) injetado no <head>.

Onde faltar dado oficial, exibe "—" (nunca estima).

Autoria: Global Reporting & Analytics — Thiago Montoro (AGCO)
"""

_ICO = {"Soja": "🌱", "Milho": "🌽", "Algodão": "🧵", "Trigo": "🌾"}
_BADGE = {
    "alta":         ("pos", "Margem ↑"),
    "baixa":        ("neg", "Margem ↓"),
    "estavel":      ("neu", "Estável"),
    "indisponivel": ("neu", "S/ dado"),
}


def _fmt(v, prefixo="R$ "):
    if v is None:
        return "—"
    return f"{prefixo}{v:,.0f}".replace(",", ".")


def _card_html(card):
    cultura, uf = card["cultura"], card["uf"]
    serie = card["serie"]
    vigente = serie[-1]
    cls_badge, txt_badge = _BADGE.get(card.get("tendencia", "indisponivel"), ("neu", "S/ dado"))
    cls_card = cls_badge
    ico = _ICO.get(cultura, "🌱")
    unid = "@/ha" if card.get("unidade") == "arroba" else "sc/ha"

    minis = ""
    for i, s in enumerate(serie):
        margem = s["margem_ha"]
        is_last = (i == len(serie) - 1)
        delta_html = "&nbsp;"
        if i > 0:
            ant = serie[i - 1]["margem_ha"]
            if margem is not None and ant not in (None, 0):
                d = (margem - ant) / abs(ant) * 100.0
                cls, seta = ("up", "▲") if d >= 0 else ("dn", "▼")
                delta_html = f'<span class="dl {cls}">{seta} {abs(d):.0f}%</span>'
        minis += (
            f'<div class="sf{" latest" if is_last else ""}">'
            f'<div class="yr">{s["safra"]}</div>'
            f'<div class="mg">{_fmt(margem, "")}</div>'
            f'<div class="dl">{delta_html if i > 0 else "&nbsp;"}</div></div>'
        )

    custos = " → ".join(_fmt(s["custo_total_ha"], "") for s in serie)
    prod_txt = "—" if vigente["produtividade"] is None else f'{vigente["produtividade"]:.0f} {unid}'

    return f"""
      <div class="margem-card {cls_card}">
        <div class="mc-head">
          <span class="mc-ico">{ico}</span>
          <span class="mc-title">{cultura}</span>
          <span class="mc-uf">{uf}</span>
          <span class="mc-badge {cls_badge}"><span class="d"></span>{txt_badge}</span>
        </div>
        <div class="mc-kpi-label">Margem {vigente['safra']}</div>
        <div class="mc-kpi {cls_card}">{_fmt(vigente['margem_ha'])}/ha</div>
        <div class="mc-sub">Receita <b>{_fmt(vigente['receita_ha'])}</b> ·
             Custo <b>{_fmt(vigente['custo_total_ha'])}</b> · Prod. <b>{prod_txt}</b></div>
        <div class="mc-mini">
          <div class="mc-mini-h"><span>Margem por safra</span><span>Δ a/a</span></div>
          <div class="mc-safras">{minis}</div>
          <div class="mc-cost"><span>Custo total (ref.)</span><span><b>R$ {custos}</b></span></div>
        </div>
      </div>"""


def gerar_bloco_margem(dados_margem):
    """Recebe o dict de processar_margem_agricola() e devolve o HTML da aba."""
    if not dados_margem or not dados_margem.get("cards"):
        return ('<p style="color:#888;font-style:italic">Dados de margem indisponíveis no momento. '
                'A aba será populada automaticamente quando a CONAB/CEPEA responderem.</p>')

    cards_html = "".join(_card_html(c) for c in dados_margem["cards"])
    safras = " · ".join(dados_margem.get("safras", []))
    fontes = dados_margem.get("fontes", {})
    aviso = dados_margem.get("aviso")
    aviso_html = (f'<div class="margem-aviso">⚠ {aviso} — valores exibidos como "—".</div>'
                  if aviso else "")
    rodape = (f"Margem (R$/ha) = Receita (Produtividade × Preço) − Custo Total. "
              f"Custo/Produtividade: {fontes.get('custo', 'CONAB')} · "
              f"Preço: {fontes.get('preco', 'CONAB - Preço recebido produtor')}. "
              f"Atualizado em {dados_margem.get('gerado_em', '')[:10]}.")

    return f"""
    <div class="margem-legend">Comparativo das últimas 3 safras (<b>{safras}</b>) · foco em <b>Margem (R$/ha)</b>, com custo total como referência.</div>
    {aviso_html}
    <div class="margem-grid">{cards_html}</div>
    <div class="margem-foot">{rodape}<br><i>{dados_margem.get('autoria', '')}</i></div>"""


# --------------------------------------------------------------------------
# CSS injetado no <head> pelo gerador (padrão AGCO/farol do dashboard)
# --------------------------------------------------------------------------
CSS_MARGEM = """
<style>
/* ===== EARLY SIGNALS · Aba Margem do Produtor (CONAB + CEPEA) ===== */
.margem-legend { font-size:12px; color:#555; background:#f4f4f4; border-left:5px solid #cc0000; border-radius:4px; padding:10px 18px; margin-bottom:22px; font-weight:600; }
.margem-legend b { color:#111; }
.margem-aviso { background:#fff2cc; border-left:5px solid #ffc000; color:#7f6000; padding:10px 16px; border-radius:4px; font-size:12px; font-weight:700; margin-bottom:18px; }
.margem-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:18px; }
@media(max-width:1050px){ .margem-grid { grid-template-columns:repeat(2,1fr); } }
@media(max-width:600px){ .margem-grid { grid-template-columns:1fr; } }
.margem-card { background:#fff; border:1px solid #e0e0e0; border-top:4px solid #cc0000; border-radius:6px; box-shadow:0 2px 6px rgba(0,0,0,0.05); padding:18px; position:relative; overflow:hidden; transition:transform .2s,box-shadow .2s; }
.margem-card:hover { transform:translateY(-3px); box-shadow:0 8px 16px rgba(0,0,0,0.08); }
.margem-card.pos { border-top-color:#70ad47; }
.margem-card.neg { border-top-color:#c00000; animation:blink-critical 1.3s ease-in-out infinite; }
.margem-card.neu { border-top-color:#ffc000; }
.mc-head { display:flex; align-items:center; gap:10px; margin-bottom:12px; }
.mc-ico { width:34px; height:34px; border-radius:8px; background:#f4f4f4; display:grid; place-items:center; font-size:18px; flex-shrink:0; }
.mc-title { font-weight:800; font-size:15px; text-transform:uppercase; color:#111; }
.mc-uf { font-size:10px; font-weight:800; color:#fff; background:#cc0000; padding:2px 7px; border-radius:3px; }
.mc-badge { margin-left:auto; font-size:10px; font-weight:800; letter-spacing:.4px; padding:3px 9px; border-radius:12px; display:inline-flex; align-items:center; gap:5px; text-transform:uppercase; white-space:nowrap; }
.mc-badge .d { width:7px; height:7px; border-radius:50%; }
.mc-badge.pos { background:#e2f0d9; color:#385723; } .mc-badge.pos .d { background:#70ad47; }
.mc-badge.neg { background:#fce4d6; color:#c65911; } .mc-badge.neg .d { background:#c00000; }
.mc-badge.neu { background:#fff2cc; color:#7f6000; } .mc-badge.neu .d { background:#ffc000; }
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
.sf .yr { font-size:10px; font-weight:700; color:#888; }
.sf .mg { font-size:13.5px; font-weight:800; margin:2px 0; color:#385723; }
.sf .dl { font-size:10px; font-weight:700; }
.sf .dl.up { color:#2e7d32; } .sf .dl.dn { color:#c62828; }
.mc-cost { margin-top:9px; font-size:11px; color:#777; display:flex; justify-content:space-between; border-top:1px dashed #e0e0e0; padding-top:8px; }
.mc-cost b { color:#333; }
.margem-foot { margin-top:22px; font-size:11px; color:#999; line-height:1.6; font-style:italic; border-top:1px solid #f5f5f5; padding-top:12px; }
</style>
"""


if __name__ == "__main__":
    from modulo_margem_agricola import processar_margem_agricola
    print(gerar_bloco_margem(processar_margem_agricola()))
