# -*- coding: utf-8 -*-
"""
render_margem_agricola.py  (v3.3 — comparativo a/a destacado + remoção de irreais)
=================================================================================
Renderiza a aba "Margem do Produtor" (metodologia CONAB COE/COT/CT) com:
    • Receita Bruta   = Produtividade x Preço CEPEA
    • Margem Bruta    = Receita - COE
    • Margem Econômica = Receita - CT
    • COMPARATIVO ANO-A-ANO destacado: variação da Margem Econômica 25/26 vs
      a safra anterior (24/25), logo abaixo do KPI principal.

O cartão SEMPRE usa como "vigente" a última safra com dado real; o comparativo
só aparece quando a safra anterior tem dado confiável (nada inventado).

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


def _mk(status):
    return "*" if status == "repetido" else ""


def _delta_html(atual, ant):
    if atual is None or ant in (None, 0):
        return '<span class="dl">&nbsp;</span>'
    d = (atual - ant) / abs(ant) * 100.0
    cls, seta = ("up", "▲") if d >= 0 else ("dn", "▼")
    return f'<span class="dl {cls}">{seta} {abs(d):.0f}%</span>'


def _indice_vigente(serie):
    """Índice do ÚLTIMO ponto com margem econômica real."""
    for i in range(len(serie) - 1, -1, -1):
        if serie[i].get("margem_economica_ha") is not None:
            return i
    return len(serie) - 1


def _indice_anterior_valido(serie, idx_vig):
    """Índice do ponto válido imediatamente anterior ao vigente."""
    for i in range(idx_vig - 1, -1, -1):
        if serie[i].get("margem_economica_ha") is not None:
            return i
    return None


def _card_html(card):
    cultura, uf = card.get("cultura", "—"), card.get("uf", "—")
    serie = card.get("serie", []) or [{}]

    idx = _indice_vigente(serie)
    vigente = serie[idx]
    idx_ant = _indice_anterior_valido(serie, idx)
    anterior = serie[idx_ant] if idx_ant is not None else {}

    cls_badge, txt_badge = _BADGE.get(card.get("tendencia", "indisponivel"), ("neu", "S/ dado"))
    cls_card = cls_badge
    ico = _ICO.get(cultura, "🌱")
    unid = "@/ha" if card.get("unidade") == "arroba" else "sc/ha"

    q_cls, q_txt = _QUAL.get(vigente.get("status_geral", "incompleto"), ("q-off", "○ Indisponível"))

    receita = vigente.get("receita_ha")
    m_bruta = vigente.get("margem_bruta_ha")
    m_econ = vigente.get("margem_economica_ha")
    coe = vigente.get("coe_ha")
    ct = vigente.get("ct_ha")

    # --- COMPARATIVO ANO-A-ANO (destaque) ---
    m_econ_ant = anterior.get("margem_economica_ha")
    comparativo_html = ""
    if m_econ is not None and m_econ_ant not in (None, 0):
        dif = m_econ - m_econ_ant
        pct = dif / abs(m_econ_ant) * 100.0
        if dif >= 0:
            cls_cmp, seta = "yoy-up", "▲"
        else:
            cls_cmp, seta = "yoy-dn", "▼"
        comparativo_html = (
            f'<div class="mc-yoy {cls_cmp}">'
            f'<span class="yoy-seta">{seta}</span> '
            f'<b>{abs(pct):.0f}%</b> vs {anterior.get("safra","safra anterior")} '
            f'<span class="yoy-abs">({_fmt(dif)}/ha)</span>'
            f'</div>'
        )
    else:
        comparativo_html = ('<div class="mc-yoy yoy-na">Sem comparativo da safra anterior '
                            '(dado indisponível na fonte)</div>')

    d_receita = _delta_html(receita, anterior.get("receita_ha"))
    d_bruta = _delta_html(m_bruta, anterior.get("margem_bruta_ha"))
    d_econ = _delta_html(m_econ, m_econ_ant)

    spread = None
    if m_bruta is not None and m_econ is not None:
        spread = round(m_bruta - m_econ, 2)
    spread_html = ""
    if spread is not None and m_bruta not in (None, 0):
        pct = spread / abs(m_bruta) * 100.0 if m_bruta != 0 else 0
        spread_html = (f'<div class="mc-spread">Aperto econômico (terra+capital+deprec.): '
                       f'<b>{_fmt(spread)}/ha</b> · {pct:.0f}% da margem bruta</div>')

    def _mini(chave):
        cells = ""
        for i, s in enumerate(serie):
            v = s.get(chave)
            is_vig = (i == idx)
            cq = " sf-off" if v is None else (" latest" if is_vig else "")
            dl = _delta_html(v, serie[i - 1].get(chave)) if i > 0 else '<span class="dl">&nbsp;</span>'
            val = _fmt(v, "")
            cells += (f'<div class="sf{cq}"><div class="yr">{s.get("safra","—")}</div>'
                      f'<div class="mg">{val}</div><div class="dl">{dl if i>0 else "&nbsp;"}</div></div>')
        return cells

    return f"""
      <div class="margem-card {cls_card}">
        <div class="mc-head">
          <span class="mc-ico">{ico}</span>
          <span class="mc-title">{cultura}</span>
          <span class="mc-uf">{uf}</span>
          <span class="mc-badge {cls_badge}"><span class="d"></span>{txt_badge}</span>
        </div>
        <div class="mc-qual {q_cls}">{q_txt}</div>

        <div class="mc-kpi-label">Margem Econômica {vigente.get('safra','—')} · Receita − CT</div>
        <div class="mc-kpi {cls_card}">{_fmt(m_econ)}/ha</div>
        {comparativo_html}
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

        <div class="mc-mini">
          <div class="mc-mini-h"><span>Margem Econômica por safra</span><span>Δ a/a</span></div>
          <div class="mc-safras">{_mini('margem_economica_ha')}</div>
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
            f'<span class="qp-total">de {rq.get("total",0)} pontos exibidos</span>'
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
        '<b>Nota:</b> cada cartão traz a <b>variação da Margem Econômica vs a safra '
        'anterior</b> (comparativo ano-a-ano). Culturas com valores fora de faixa '
        'plausível (erro de preço/custo na fonte) são <b>automaticamente removidas</b> '
        'do relatório — nenhum número irreal é exibido e nada é inventado.'
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
/* ===== EARLY SIGNALS · Aba Margem do Produtor v3.3 (CONAB COE/COT/CT) ===== */
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
.mc-yoy { display:inline-flex; align-items:center; gap:6px; font-size:12.5px; font-weight:800; padding:5px 11px; border-radius:20px; margin:4px 0 8px; }
.mc-yoy .yoy-seta { font-size:13px; }
.mc-yoy .yoy-abs { font-weight:700; opacity:.85; }
.mc-yoy.yoy-up { background:#e2f0d9; color:#2e7d32; }
.mc-yoy.yoy-dn { background:#fce4d6; color:#c0392b; }
.mc-yoy.yoy-na { background:#f0f0f0; color:#999; font-weight:600; font-size:11px; }
.mc-spread { font-size:10.5px; color:#7f6000; background:#fff8e1; border:1px solid #ffe08a; border-radius:4px; padding:5px 9px; margin:2px 0 10px; line-height:1.35; }
.mc-spread b { color:#5f4a00; }
.mc-kpis3 { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin:6px 0 12px; }
.k3 { background:#fafafa; border:1px solid #eee; border-radius:6px; padding:8px 6px; text-align:center; display:flex; flex-direction:column; gap:3px; }
.k3l { font-size:8.5px; font-weight:700; color:#888; text-transform:uppercase; letter-spacing:.3px; line-height:1.2; min-height:22px; }
.k3v { font-size:13px; font-weight:800; color:#111; }
.k3d { font-size:10px; font-weight:700; }
.mc-sub { font-size:11px; color:#777; margin-bottom:12px; line-height:1.5; }
.mc-sub b { color:#333; font-weight:700; }
.mc-mini { border-top:1px dashed #e0e0e0; padding-top:10px; }
.mc-mini-h { display:flex; justify-content:space-between; font-size:9.5px; font-weight:700; letter-spacing:.5px; text-transform:uppercase; color:#888; margin-bottom:8px; }
.mc-safras { display:grid; grid-template-columns:repeat(2,1fr); gap:8px; }
.sf { background:#fafafa; border:1px solid #eee; border-radius:6px; padding:7px 8px; text-align:center; }
.sf.latest { background:#e2f0d9; border-color:#bfe7cd; }
.sf.sf-off { background:#f5f5f5; border-color:#e6e6e6; }
.sf .yr { font-size:10px; font-weight:700; color:#888; }
.sf .mg { font-size:14px; font-weight:800; margin:2px 0; color:#385723; }
.sf.sf-off .mg { color:#bbb; }
.sf .dl { font-size:10px; font-weight:700; }
.dl.up { color:#2e7d32; } .dl.dn { color:#c62828; }
.margem-foot { margin-top:22px; font-size:11px; color:#999; line-height:1.6; font-style:italic; border-top:1px solid #f5f5f5; padding-top:12px; }
</style>
"""


if __name__ == "__main__":
    from modulo_margem_agricola import processar_margem_agricola
    print(gerar_bloco_margem(processar_margem_agricola()))
