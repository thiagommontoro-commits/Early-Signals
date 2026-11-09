# -*- coding: utf-8 -*-
"""
gerador_dashboard_early_signals.py   <<< SUBSTITUI o arquivo que já existe
==========================================================================
VERSÃO: v12
  v12 — NOTÍCIAS VIA GOOGLE NEWS RSS + ANÁLISE DA IA:
  • As notícias são coletadas pelo próprio script no Google News RSS (gratuito, sem chave,
    sem cota). Link, veículo e data vêm do RSS -> 100% verificáveis.
  • O Gemini NÃO pesquisa mais: recebe as manchetes, escolhe as mais relevantes por tema
    (pelo id) e escreve a análise (por que importa, impacto por produto, radar estratégico,
    fatores). Usa o modo sem pesquisa, que tem cota bem maior no Free Tier.
  • ~8 chamadas ao Gemini por execução (1 por país). Mais rápido.
  • Log em tempo real no GitHub Actions (stdout sem buffer).
  v11 — modelo reserva gemini-3.5-flash-lite; erro 404 também troca de modelo.
  v10 — para na hora com cota diária esgotada; mantém dados anteriores se a IA falhar.
  v9  — cache gravado com >=1 notícia e fallback ao cache anterior.
  Forçar regeração: python gerador_dashboard_early_signals.py --forcar
"""
import os
import re
import sys
import json
from pathlib import Path
import datetime
import traceback
import time
import threading
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(line_buffering=True)   # log em tempo real no GitHub Actions
except Exception:
    pass

load_dotenv()
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
from modulo_inadimplencia import obter_inadimplencia_rural
from modulo_juros_rural import obter_juros_rural
from modulo_indicadores_oficiais import obter_indicadores_oficiais
from modulo_commodities import processar_commodities
from render_commodities import gerar_bloco_commodities, CSS_COMMODITIES
from modulo_credito_rural_deepdive import processar_credito_rural
from render_credito_rural import gerar_bloco_credito_rural, CSS_CREDITO_RURAL

CACHE_VERSAO = "v8"

TRANSLATIONS = {
    "pt": {
        "positive": "Positivo", "critical": "Crítico", "warning": "Atenção",
        "description": "Descrição", "impacts": "Impactos", "source": "Fonte",
        "no_analysis": "Nenhuma análise disponível para este país.", "unavailable_title": "Título Indisponível",
        "unavailable_body": "Corpo da notícia indisponível.", "not_informed": "Não informada",
        "product_line_impact": "Impacto por Linha de Produto", "analysis_unavailable": "Análise indisponível.",
        "no_news": "Nenhuma notícia disponível para este país.",
        "months": ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"],
        "suggest_improvement": "Sugerir Melhoria",
    },
    "en": {
        "positive": "Positive", "critical": "Critical", "warning": "Warning",
        "description": "Description", "impacts": "Impacts", "source": "Source",
        "no_analysis": "No analysis available for this country.", "unavailable_title": "Title Unavailable",
        "unavailable_body": "News body unavailable.", "not_informed": "Not informed",
        "product_line_impact": "Impact by Product Line", "analysis_unavailable": "Analysis unavailable.",
        "no_news": "No news available for this country.",
        "months": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        "suggest_improvement": "Suggest Improvement",
    },
    "es": {
        "positive": "Positivo", "critical": "Crítico", "warning": "Atención",
        "description": "Descripción", "impacts": "Impactos", "source": "Fuente",
        "no_analysis": "No hay análisis disponible para este país.", "unavailable_title": "Título no disponible",
        "unavailable_body": "Cuerpo de la noticia no disponible.", "not_informed": "No informada",
        "product_line_impact": "Impacto por Línea de Producto", "analysis_unavailable": "Análisis no disponible.",
        "no_news": "No hay noticias disponibles para este país.",
        "months": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
        "suggest_improvement": "Sugerir Mejora",
    }
}

# Mês de comparação do selo ("Piorando vs Julho"): derivado do DADO, não do calendário.
_MESES_PT_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun",
                   "jul", "ago", "set", "out", "nov", "dez"]


def _nomes_mes_por_indice(idx0):
    return {lang: TRANSLATIONS[lang]["months"][idx0] for lang in ("pt", "en", "es")}


def _resolver_mes_comparacao(analise, mes_anterior_calendario=None):
    mc = analise.get("mes_comparacao")
    if isinstance(mc, dict) and mc.get("pt"):
        return mc
    descricao = str(analise.get("descricao", ""))
    m = re.search(r"(?:ante|vs\.?|frente a)\s+(" + "|".join(TRANSLATIONS["pt"]["months"]) + r")",
                  descricao, re.IGNORECASE)
    if m:
        for i, mes in enumerate(TRANSLATIONS["pt"]["months"]):
            if mes.lower() == m.group(1).lower():
                return _nomes_mes_por_indice(i)
    m = re.search(r"\b([A-Za-zçÇãÃéÉ]{3,9})\.?/(\d{4})\b", descricao)
    if m and m.group(1).lower()[:3] in _MESES_PT_ABREV:
        return _nomes_mes_por_indice((_MESES_PT_ABREV.index(m.group(1).lower()[:3]) - 1) % 12)
    return mes_anterior_calendario


def i18n_attrs(key):
    return ' '.join([f'data-{lang}="{tr.get(key, "")}"' for lang, tr in TRANSLATIONS.items()])


def get_farol_class(tendencia):
    mapa = {"positivo": "farol-positive", "negativo": "farol-critical", "incerto": "farol-warning",
            "estavel": "farol-warning", "alta": "farol-critical", "baixa": "farol-positive",
            "restritiva": "farol-critical", "expansiva": "farol-positive"}
    return mapa.get(str(tendencia).lower(), "farol-warning")


def get_farol_translation_key(tendencia):
    t = str(tendencia).lower()
    if t in ["positivo", "baixa", "expansiva"]:
        return "positive"
    if t in ["negativo", "alta", "restritiva"]:
        return "critical"
    return "warning"


def get_direcao_badge(analise, mes_anterior_nome=None):
    direcao = str(analise.get("direcao", "estavel")).lower()
    mapa = {
        "melhorando": ("▲", "dir-up",   {"pt": "Melhorando", "en": "Improving", "es": "Mejorando"}),
        "piorando":   ("▼", "dir-down", {"pt": "Piorando",   "en": "Worsening", "es": "Empeorando"}),
    }
    seta, css, rot = mapa.get(direcao, ("▬", "dir-stable", {"pt": "Estável", "en": "Stable", "es": "Estable"}))
    mes_ref = _resolver_mes_comparacao(analise, mes_anterior_nome)
    txt = {l: rot[l] + (f" vs {mes_ref[l]}" if mes_ref else "") for l in ("pt", "en", "es")}
    attrs = f'data-pt="{txt["pt"]}" data-en="{txt["en"]}" data-es="{txt["es"]}"'
    return f'<span class="dir-pill {css}">{seta} <span {attrs}>{txt["pt"]}</span></span>'


def gerar_bloco_analises(analises_pais, mes_anterior_nome=None):
    if not analises_pais:
        return f'<p {i18n_attrs("no_analysis")}>{TRANSLATIONS["pt"]["no_analysis"]}</p>'
    classes = {"restritiva": "tendencia-negativa", "alta": "tendencia-negativa", "negativo": "tendencia-negativa",
               "expansiva": "tendencia-positiva", "baixa": "tendencia-positiva", "positivo": "tendencia-positiva"}
    html_output = '<div class="analysis-grid">\n'
    for analise in analises_pais:
        tendencia = analise.get("tendencia", "incerto")
        css_class = classes.get(tendencia, "tendencia-neutra")
        tk = get_farol_translation_key(tendencia)
        farol_html = (f'<span class="farol {get_farol_class(tendencia)}"><span class="farol-dot"></span>'
                      f'<span {i18n_attrs(tk)}>{TRANSLATIONS["pt"][tk]}</span></span>')
        direcao_html = get_direcao_badge(analise, mes_anterior_nome)
        html_output += f'''
        <div class="analysis-card {css_class}">
            <div class="analysis-header">
                <span class="analysis-icon">{analise.get("icone", "📊")}</span>
                <h3 class="analysis-card-title">{analise.get("titulo", "")}</h3>
                {farol_html}
            </div>
            <div class="analysis-trend-row">{direcao_html}</div>
            <div class="analysis-body">
                <div>
                    <span class="analysis-label" {i18n_attrs("description")}>{TRANSLATIONS["pt"]["description"]}</span>
                    <p class="analysis-text">{analise.get("descricao", "")}</p>
                </div>
                <div>
                    <span class="analysis-label" {i18n_attrs("impacts")}>{TRANSLATIONS["pt"]["impacts"]}</span>
                    <p class="analysis-text">{analise.get("impactos", "")}</p>
                </div>
                <div>
                    <span class="analysis-label" {i18n_attrs("source")}>{TRANSLATIONS["pt"]["source"]}</span>
                    <p class="analysis-text source-text">{analise.get("fonte", "")}</p>
                </div>
            </div>
        </div>'''
    return html_output + '\n</div>'


_ORDEM_RELEVANCIA = {"alta": 0, "media": 1, "média": 1, "baixa": 2}
_ROTULO_RELEVANCIA = {"alta": {"pt": "Relevância alta", "en": "High relevance", "es": "Relevancia alta"},
                      "media": {"pt": "Relevância média", "en": "Medium relevance", "es": "Relevancia media"},
                      "baixa": {"pt": "Relevância baixa", "en": "Low relevance", "es": "Relevancia baja"}}
_ROTULO_HORIZONTE = {"imediato": {"pt": "Efeito imediato", "en": "Immediate effect", "es": "Efecto inmediato"},
                     "3-6 meses": {"pt": "Efeito em 3-6 meses", "en": "Effect in 3-6 months", "es": "Efecto en 3-6 meses"},
                     "6-12 meses": {"pt": "Efeito em 6-12 meses", "en": "Effect in 6-12 months", "es": "Efecto en 6-12 meses"}}
_TXT = {
    "why": {"pt": "Por que importa", "en": "Why it matters", "es": "Por qué importa"},
    "radar": {"pt": "Radar Estratégico do Mês", "en": "Strategic Radar of the Month", "es": "Radar Estratégico del Mes"},
    "risks": {"pt": "Riscos", "en": "Risks", "es": "Riesgos"},
    "opps": {"pt": "Oportunidades", "en": "Opportunities", "es": "Oportunidades"},
    "watch": {"pt": "Monitorar (30-60 dias)", "en": "Watch (30-60 days)", "es": "Monitorear (30-60 días)"},
    "outlook": {"pt": "Demanda 6 meses", "en": "6-month demand", "es": "Demanda 6 meses"},
}


def _span_i18n(d):
    pt = d.get("pt", "")
    attrs = " ".join(f'data-{l}="{d.get(l, pt)}"' for l in ("pt", "en", "es"))
    return f"<span {attrs}>{pt}</span>"


def _selo_tema(tema):
    if not tema:
        return ""
    rot = {"pt": tema, **ROTULOS_TEMA.get(tema, {})}
    classe = "tag-estrategico" if tema in TEMAS_ESTRATEGICOS_NOMES else "tag-mercado"
    return f'<span class="news-tag {classe}">{ICONES_TEMA.get(tema, "")} {_span_i18n(rot)}</span>'


def gerar_bloco_sintese(sintese):
    if not isinstance(sintese, dict) or not str(sintese.get("manchete", "")).strip() \
            or sintese.get("manchete") == "...":
        return ""
    term = sintese.get("termometro", "incerto")
    tk = get_farol_translation_key(term)

    def lista(chave):
        itens = [str(x) for x in (sintese.get(chave) or []) if str(x).strip() and x != "..."]
        return "".join(f"<li>{x}</li>" for x in itens) or "<li>—</li>"
    return f'''
<div class="radar-box">
    <div class="radar-top">
        <div class="radar-kicker">🧭 {_span_i18n(_TXT["radar"])}</div>
        <div class="radar-outlook">{_span_i18n(_TXT["outlook"])}:
            <span class="farol {get_farol_class(term)}"><span class="farol-dot"></span><span {i18n_attrs(tk)}>{TRANSLATIONS["pt"][tk]}</span></span>
        </div>
    </div>
    <h3 class="radar-headline">{sintese.get("manchete")}</h3>
    <p class="radar-text">{sintese.get("leitura", "")}</p>
    <div class="radar-cols">
        <div class="radar-col radar-risk"><h4>⚠️ {_span_i18n(_TXT["risks"])}</h4><ul>{lista("riscos")}</ul></div>
        <div class="radar-col radar-opp"><h4>🚀 {_span_i18n(_TXT["opps"])}</h4><ul>{lista("oportunidades")}</ul></div>
        <div class="radar-col radar-watch"><h4>📅 {_span_i18n(_TXT["watch"])}</h4><ul>{lista("monitorar")}</ul></div>
    </div>
</div>'''


def gerar_blocos_noticias(noticias_pais, codigo_pais="", sintese=None):
    radar = gerar_bloco_sintese(sintese)
    if not noticias_pais:
        return radar + f'<div class="news-grid"><p {i18n_attrs("no_news")}>{TRANSLATIONS["pt"]["no_news"]}</p></div>'
    ordenadas = sorted(enumerate(noticias_pais),
                       key=lambda x: (_ORDEM_RELEVANCIA.get(str(x[1].get("relevancia", "")).lower(), 1), x[0]))
    html_output = radar + '<div class="news-grid">\n'
    for _, noticia in ordenadas:
        tn = noticia.get('tendencia_noticia', 'incerto')
        tk = get_farol_translation_key(tn)
        tema = noticia.get('tema')
        icon_html = f'<span class="news-topic-icon" title="{tema}">{ICONES_TEMA[tema]}</span>' if tema in ICONES_TEMA else ""
        rel = str(noticia.get("relevancia", "")).lower().replace("média", "media")
        hor = str(noticia.get("horizonte", "")).lower()
        meta = _selo_tema(tema)
        if rel in _ROTULO_RELEVANCIA:
            meta += f'<span class="news-tag tag-rel-{rel}">{_span_i18n(_ROTULO_RELEVANCIA[rel])}</span>'
        if hor in _ROTULO_HORIZONTE:
            meta += f'<span class="news-tag tag-horizonte">⏱ {_span_i18n(_ROTULO_HORIZONTE[hor])}</span>'
        pq = str(noticia.get("por_que_importa", "")).strip()
        pq_html = (f'<div class="news-why"><strong>💡 {_span_i18n(_TXT["why"])}:</strong> {pq}</div>'
                   if pq and pq != "..." else "")
        html_output += f'''
        <div class="news-block{' news-high' if rel == 'alta' else ''}">
            <div class="news-meta">{meta}</div>
            <div class="news-header">
                <h3 class="news-title">{icon_html}{noticia.get('titulo_noticia', TRANSLATIONS['pt']['unavailable_title'])}</h3>
                <span class="farol {get_farol_class(tn)}"><span class="farol-dot"></span><span {i18n_attrs(tk)}>{TRANSLATIONS['pt'][tk]}</span></span>
            </div>
            <div class="news-body">
                {noticia.get('corpo_noticia', TRANSLATIONS['pt']['unavailable_body'])}
                {pq_html}
                <p class="news-source"><strong {i18n_attrs("source")}>{TRANSLATIONS["pt"]["source"]}:</strong> {noticia.get('fonte_noticia', TRANSLATIONS['pt']['not_informed'])}</p>
            </div>
            <div class="machinery-analysis">
                <div class="analysis-title" {i18n_attrs("product_line_impact")}>{TRANSLATIONS['pt']['product_line_impact']}</div>
                <div class="machinery-items">
        '''
        for produto, impacto in (noticia.get('impacto_produtos') or {}).items():
            if not isinstance(impacto, dict):
                continue
            tp = impacto.get('tendencia', 'incerto')
            tkp = get_farol_translation_key(tp)
            seg = impacto.get('segmento_impactado')
            seg_html = f' <span class="m-segment">({seg})</span>' if seg and str(seg).strip() and seg != "..." else ''
            html_output += f'''
                    <div class="m-item">
                        <div class="m-header"><span class="m-name">{produto.capitalize()}{seg_html}</span><span class="farol {get_farol_class(tp)}"><span class="farol-dot"></span><span {i18n_attrs(tkp)}>{TRANSLATIONS['pt'][tkp]}</span></span></div>
                        <div class="m-desc">{impacto.get('descricao', TRANSLATIONS['pt']['analysis_unavailable'])}</div>
                    </div>'''
        html_output += '\n                </div>\n            </div>\n        </div>'
    return html_output + '\n</div>'


CSS_NOTICIAS_ESTRATEGICAS = """
<style>
.radar-box{background:linear-gradient(135deg,#1f1f1f 0%,#3a3a3a 100%);color:#fff;border-left:6px solid #CC0000;
  border-radius:12px;padding:20px 22px;margin:0 0 22px 0;box-shadow:0 4px 14px rgba(0,0,0,.15)}
.radar-top{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.radar-kicker{font-size:12px;letter-spacing:1.2px;text-transform:uppercase;color:#ffb3b3;font-weight:700}
.radar-outlook{font-size:13px;display:flex;align-items:center;gap:8px}
.radar-headline{font-size:20px;margin:10px 0 8px;line-height:1.3;color:#fff}
.radar-text{font-size:14px;line-height:1.55;color:#e6e6e6;margin:0 0 14px}
.radar-cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.radar-col{background:rgba(255,255,255,.07);border-radius:8px;padding:10px 12px}
.radar-col h4{margin:0 0 6px;font-size:13px;color:#fff}
.radar-col ul{margin:0;padding-left:18px;font-size:13px;line-height:1.5;color:#ddd}
.radar-risk{border-top:3px solid #e74c3c}.radar-opp{border-top:3px solid #2ecc71}.radar-watch{border-top:3px solid #f1c40f}
.news-meta{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}
.news-tag{font-size:11px;font-weight:600;padding:3px 9px;border-radius:20px;background:#f0f0f0;color:#444;white-space:nowrap}
.tag-estrategico{background:#fdecec;color:#a30000}.tag-mercado{background:#eef6ee;color:#2e6b2e}
.tag-rel-alta{background:#CC0000;color:#fff}.tag-rel-media{background:#ffe9b3;color:#7a5a00}.tag-rel-baixa{background:#e8e8e8;color:#666}
.tag-horizonte{background:#eaf1fb;color:#2b5797}
.news-block.news-high{border-top:4px solid #CC0000}
.news-why{margin:10px 0 4px;padding:8px 10px;background:#fff7e6;border-left:3px solid #f0a500;border-radius:4px;font-size:13px;line-height:1.45}
</style>
"""


def carregar_dados_paises(caminho_json):
    try:
        print(f"📄 Carregando dados de '{caminho_json.name}'...")
        with open(caminho_json, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        print("✅ Dados carregados com sucesso.")
        return dados
    except Exception as e:
        print(f"❌ ERRO ao carregar '{caminho_json}': {e}")
        return None


# DADOS OFICIAIS (BCB) — buscados ANTES da IA
TITULOS_OFICIAIS_BR = {"Juros (Selic)", "Câmbio (Dólar)"}


def coletar_dados_oficiais_br():
    """Retorna (cards_oficiais_em_ordem, linhas_de_contexto_para_prompt)."""
    cards, contexto = [], []
    inad = obter_inadimplencia_rural()
    if inad:
        cards.append(inad)
        contexto.append(f"Inadimplência crédito rural PF (BCB SGS 21148): {inad['descricao']}")
    for c in obter_juros_rural() or []:
        cards.append(c)
        contexto.append(f"{c['titulo']} (BCB): {c['descricao']}")
    oficiais, ctx = obter_indicadores_oficiais()
    cards.extend(oficiais)
    contexto.extend(ctx)
    print(f"   ✅ {len(cards)} card(s) com dado oficial do BCB para o Brasil.")
    return cards, contexto


def _extrair_json(texto):
    """Extrai o objeto JSON da resposta (remove cercas ```, texto extra e vírgulas sobrando)."""
    t = (texto or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    ini, fim = t.find("{"), t.rfind("}")
    if ini == -1 or fim == -1:
        raise ValueError("Resposta da IA sem objeto JSON (provável resposta cortada ou só texto).")
    bruto = t[ini:fim + 1]
    try:
        return json.loads(bruto)
    except json.JSONDecodeError:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", bruto))


FATORES_BASE = {
  "br": [ { "titulo": "Crédito Rural", "icone": "💳" }, { "titulo": "Prod. Grãos", "icone": "🚜" }, { "titulo": "Margens Produtor", "icone": "📊" } ],
  "ar": [ { "titulo": "Crédito/Financ.", "icone": "💳" }, { "titulo": "Inflação/Câmbio", "icone": "📈" }, { "titulo": "Retenciones", "icone": "⚖️" }, { "titulo": "Prod. Agrícola", "icone": "🚜" }, { "titulo": "Margens Produtor", "icone": "📊" } ],
  "cl": [ { "titulo": "Cenário Hídrico", "icone": "💧" }, { "titulo": "Export. Frutas", "icone": "🍒" }, { "titulo": "Custo de Insumos", "icone": "📦" }, { "titulo": "Reg. Ambiental", "icone": "🌿" }, { "titulo": "Margens Produtor", "icone": "📊" } ],
  "uy": [ { "titulo": "Export. Carne", "icone": "🐄" }, { "titulo": "Preço Commod.", "icone": "📉" }, { "titulo": "Atraso Cambial", "icone": "💵" }, { "titulo": "Prod. Florestal", "icone": "🌲" }, { "titulo": "Margens Produtor", "icone": "📊" } ],
  "py": [ { "titulo": "Expansão Agro", "icone": "🌱" }, { "titulo": "Logística Fluvial", "icone": "🚢" }, { "titulo": "Prod. Carne", "icone": "🥩" }, { "titulo": "Fiscal/Câmbio", "icone": "🏛️" }, { "titulo": "Margens Produtor", "icone": "📊" } ],
  "pe": [ { "titulo": "Agroexport (Costa)", "icone": "🥑" }, { "titulo": "Agro Andino", "icone": "🥔" }, { "titulo": "Irrigação", "icone": "🏞️" }, { "titulo": "Cenário Político", "icone": "⚖️" }, { "titulo": "Margens Produtor", "icone": "📊" } ],
  "bo": [ { "titulo": "Soja (Oriente)", "icone": "🌱" }, { "titulo": "Escassez de Dólar", "icone": "💸" }, { "titulo": "Biocombustíveis", "icone": "⛽" }, { "titulo": "Infra. Logística", "icone": "🛣️" }, { "titulo": "Margens Produtor", "icone": "📊" } ],
  "mx": [ { "titulo": "Export. p/ EUA", "icone": "🥑" }, { "titulo": "Escassez Hídrica", "icone": "🏜️" }, { "titulo": "Prod. Agave", "icone": "🌵" }, { "titulo": "Remessas/Agro Fam.", "icone": "👨‍👩‍👧‍👦" }, { "titulo": "Margens Produtor", "icone": "📊" } ]
}
NOMES_PAISES = {"br": "Brasil", "ar": "Argentina", "cl": "Chile", "uy": "Uruguai",
                "py": "Paraguai", "pe": "Peru", "bo": "Bolívia", "mx": "México"}
TEMAS_BR = ["Soja", "Milho", "Café", "Cana", "Algodão", "Trigo"]

# Pauta ESTRATÉGICA — o que mexe com a decisão de compra de máquinas.
TEMAS_ESTRATEGICOS = [
    ("Política & Eleições",
     "eleições, transição de governo, agenda do Congresso/Legislativo, reforma tributária, "
     "medidas fiscais e posicionamento de governo/candidatos sobre o agro"),
    ("Política Agrícola & Crédito",
     "Plano Safra / programas oficiais de financiamento, equalização de juros, Moderfrota/BNDES "
     "ou equivalentes locais, renegociação de dívidas rurais, recuperação judicial no agro"),
    ("Comércio Exterior & Geopolítica",
     "China, EUA, tarifas e guerras comerciais, acordo Mercosul-UE, cotas/retenciones, "
     "barreiras sanitárias, câmbio e fluxo de exportação"),
    ("Clima & Safra",
     "El Niño/La Niña, seca/chuvas, andamento do plantio/colheita, estimativas oficiais de safra"),
]
N_NOTICIAS_MERCADO_OUTROS = 2   # países ≠ BR: notícias livres de mercado/produção
ICONES_TEMA = {
    "Soja": "🌱", "Milho": "🌽", "Café": "☕", "Cana": "🎋", "Algodão": "🧺", "Trigo": "🌾",
    "Política & Eleições": "🗳️", "Política Agrícola & Crédito": "🏦",
    "Comércio Exterior & Geopolítica": "🌐", "Clima & Safra": "🌦️", "Mercado & Produção": "🚜",
}
ROTULOS_TEMA = {
    "Política & Eleições": {"en": "Politics & Elections", "es": "Política y Elecciones"},
    "Política Agrícola & Crédito": {"en": "Ag Policy & Credit", "es": "Política Agrícola y Crédito"},
    "Comércio Exterior & Geopolítica": {"en": "Trade & Geopolitics", "es": "Comercio Exterior y Geopolítica"},
    "Clima & Safra": {"en": "Weather & Crop", "es": "Clima y Cosecha"},
    "Mercado & Produção": {"en": "Market & Production", "es": "Mercado y Producción"},
    "Soja": {"en": "Soybean", "es": "Soja"}, "Milho": {"en": "Corn", "es": "Maíz"},
    "Café": {"en": "Coffee", "es": "Café"}, "Cana": {"en": "Sugarcane", "es": "Caña"},
    "Algodão": {"en": "Cotton", "es": "Algodón"}, "Trigo": {"en": "Wheat", "es": "Trigo"},
}
TEMAS_ESTRATEGICOS_NOMES = [t for t, _ in TEMAS_ESTRATEGICOS]


def _temas_pais(pais):
    if pais == "br":
        return TEMAS_ESTRATEGICOS_NOMES + TEMAS_BR
    return TEMAS_ESTRATEGICOS_NOMES + ["Mercado & Produção"] * N_NOTICIAS_MERCADO_OUTROS


# =============================================================================
# CONFIGURAÇÃO DA IA / NOTÍCIAS
# =============================================================================
MODELO_GEMINI = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
# Modelos reserva (separados por vírgula), tentados em ordem quando o atual
# esgota a cota diária (429) ou não existe mais (404). Cada modelo tem cota própria.
MODELOS_RESERVA = [m.strip() for m in os.environ.get(
    "GEMINI_MODEL_RESERVA", "gemini-3.5-flash-lite").split(",") if m.strip()]
_COTA = {"esgotada": False, "modelo": MODELO_GEMINI, "lock": threading.Lock()}

JANELA_NOTICIAS_DIAS = 30        # notícia só entra se publicada nos últimos N dias
MINIMO_NOTICIAS_RECENTES = 2     # alvo mínimo (cache é gravado a partir de 1)
CACHE_VALIDADE_DIAS = 3          # país em cache é reaproveitado por no máx. N dias
FORCAR_ATUALIZACAO = ("--forcar" in sys.argv) or os.environ.get("FORCAR_IA") == "1"
DEBUG_IA = True                  # grava as respostas brutas da IA em /debug_ia
PAISES_EM_PARALELO = 2           # países processados ao mesmo tempo (1 = sequencial)
TENTATIVAS_IA = 3                # chamadas por país (inclui troca de modelo)
ORCAMENTO_RACIOCINIO = 1024      # "thinking" do Gemini (tokens). 0 = desliga; -1 = automático
TIMEOUT_CHAMADA_SEG = 240        # corta chamada travada em vez de esperar indefinidamente
MAX_TOKENS_RESPOSTA = 16384

# --- v12: Google News RSS ----------------------------------------------------
RSS_POR_TEMA = 6                 # manchetes candidatas por tema enviadas à IA
RSS_TIMEOUT_SEG = 20
RSS_LOCAIS = {  # (hl, gl, ceid)
    "br": ("pt-BR", "BR", "BR:pt-419"),
    "ar": ("es-419", "AR", "AR:es-419"),
    "cl": ("es-419", "CL", "CL:es-419"),
    "uy": ("es-419", "UY", "UY:es-419"),
    "py": ("es-419", "PY", "PY:es-419"),
    "pe": ("es-419", "PE", "PE:es-419"),
    "bo": ("es-419", "BO", "BO:es-419"),
    "mx": ("es-419", "MX", "MX:es-419"),
}
NOMES_ES = {"ar": "Argentina", "cl": "Chile", "uy": "Uruguay", "py": "Paraguay",
            "pe": "Perú", "bo": "Bolivia", "mx": "México"}


def _consultas_rss(pais):
    """Uma busca por tema. Edite aqui para mudar o foco das notícias."""
    if pais == "br":
        return {
            "Política & Eleições": '(eleições OR Congresso OR "reforma tributária" OR governo) agronegócio',
            "Política Agrícola & Crédito": '"Plano Safra" OR "crédito rural" OR Moderfrota OR "dívida rural" OR "recuperação judicial" produtor',
            "Comércio Exterior & Geopolítica": 'agronegócio exportação (China OR tarifa OR Mercosul OR "Estados Unidos")',
            "Clima & Safra": 'safra (Conab OR plantio OR colheita) (chuva OR seca OR clima)',
            "Soja": 'soja preço produtor safra',
            "Milho": 'milho preço safra produtor',
            "Café": 'café safra preço produtor',
            "Cana": 'cana-de-açúcar etanol safra usinas',
            "Algodão": 'algodão safra exportação preço',
            "Trigo": 'trigo safra preço produtor',
        }
    n = NOMES_ES[pais]
    return {
        "Política & Eleições": f'{n} (elecciones OR gobierno OR congreso) (agro OR campo OR productores)',
        "Política Agrícola & Crédito": f'{n} (crédito OR financiamiento OR deudas) (agropecuario OR productores OR campo)',
        "Comércio Exterior & Geopolítica": f'{n} exportaciones (agro OR granos OR carne) (China OR aranceles OR "Estados Unidos" OR Mercosur OR retenciones)',
        "Clima & Safra": f'{n} (cosecha OR siembra OR campaña agrícola) (clima OR sequía OR lluvias OR heladas)',
        "Mercado & Produção": f'{n} ("maquinaria agrícola" OR "producción agrícola" OR ganadería OR "precios de granos" OR tractores)',
    }


def _ler_rss(consulta, pais):
    hl, gl, ceid = RSS_LOCAIS[pais]
    url = ("https://news.google.com/rss/search?q="
           + urllib.parse.quote_plus(f"{consulta} when:{JANELA_NOTICIAS_DIAS}d")
           + f"&hl={hl}&gl={gl}&ceid={ceid}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EarlySignals dashboard)"})
    with urllib.request.urlopen(req, timeout=RSS_TIMEOUT_SEG) as r:
        raiz = ET.fromstring(r.read())
    itens = []
    for it in raiz.iter("item"):
        titulo = (it.findtext("title") or "").strip()
        fonte = (it.findtext("source") or "").strip()
        if fonte and titulo.endswith(" - " + fonte):
            titulo = titulo[: -(len(fonte) + 3)].strip()
        try:
            d = parsedate_to_datetime(it.findtext("pubDate") or "").date()
        except Exception:
            d = None
        itens.append({"titulo": titulo, "url": (it.findtext("link") or "").strip(),
                      "fonte": fonte or "Google News", "data": d})
    return itens


def coletar_noticias_rss(pais, now):
    """Manchetes reais e recentes por tema, com id (N1, N2...) para a IA referenciar."""
    hoje = now.date()
    corte = hoje - datetime.timedelta(days=JANELA_NOTICIAS_DIAS)
    candidatos, vistos = [], set()
    for tema, consulta in _consultas_rss(pais).items():
        try:
            itens = _ler_rss(consulta, pais)
        except Exception as e:
            print(f"      ⚠ {pais.upper()} RSS '{tema}': {str(e)[:150]}")
            continue
        itens = [i for i in itens if i["data"] and i["titulo"] and i["url"]
                 and corte <= i["data"] <= hoje + datetime.timedelta(days=1)]
        itens.sort(key=lambda i: i["data"], reverse=True)
        k = 0
        for i in itens:
            chave = re.sub(r"\W+", "", i["titulo"].lower())[:80]
            if chave in vistos:
                continue
            vistos.add(chave)
            k += 1
            candidatos.append({**i, "tema": tema, "id": f"N{len(candidatos) + 1}",
                               "data": i["data"].isoformat()})
            if k >= RSS_POR_TEMA:
                break
    print(f"   📰 {pais.upper()}: {len(candidatos)} manchetes recentes coletadas (Google News RSS)")
    return candidatos


# --- Cota / troca de modelo -------------------------------------------------
def _modelo_indisponivel(e):
    m = str(e).lower()
    return "404" in m and ("not_found" in m or "no longer available" in m)


def _cota_diaria(e):
    m = str(e).lower()
    return ("429" in m or "resource_exhausted" in m) and ("per day" in m or "perday" in m)


def _modelo_atual():
    return _COTA["modelo"]


def _registrar_cota_esgotada(modelo_que_falhou):
    """Passa para o próximo modelo da lista; se a lista acabou, para a IA."""
    with _COTA["lock"]:
        if _COTA["modelo"] != modelo_que_falhou:
            return                       # outra thread já trocou
        _COTA.setdefault("usados", {MODELO_GEMINI}).add(modelo_que_falhou)
        proximo = next((m for m in MODELOS_RESERVA if m not in _COTA["usados"]), None)
        if proximo:
            print(f"   🔁 {modelo_que_falhou} sem cota/indisponível. Trocando para {proximo}.")
            _COTA["modelo"] = proximo
        else:
            if not _COTA["esgotada"]:
                print("   🛑 Cota diária do Gemini esgotada em todos os modelos. Parando a IA e "
                      "mantendo os dados anteriores.")
            _COTA["esgotada"] = True


def _bloco_candidatas(candidatos):
    if not candidatos:
        return "    (nenhuma manchete recente encontrada)"
    linhas, tema_atual = [], None
    for c in candidatos:
        if c["tema"] != tema_atual:
            tema_atual = c["tema"]
            linhas.append(f"    • Tema: {tema_atual}")
        linhas.append(f"      [{c['id']}] {c['data']} | {c['fonte']} | {c['titulo']}")
    return "\n".join(linhas)


def _prompt_pais(pais, contexto_oficial, now, candidatos):
    meses_pt = TRANSLATIONS["pt"]["months"]
    year, month = now.year, now.month
    mes_nome, mes_ant = meses_pt[month - 1], meses_pt[(month - 2) % 12]
    ano_ant = year if month > 1 else year - 1
    hoje_txt = now.strftime("%d/%m/%Y")
    base_noticia = {
        "id_noticia": "N?", "titulo_noticia": "...", "tendencia_noticia": "positivo|negativo|incerto",
        "corpo_noticia": "...",
        "relevancia": "alta|media|baixa", "horizonte": "imediato|3-6 meses|6-12 meses",
        "por_que_importa": "...",
        "impacto_produtos": {p: {"tendencia": "positivo|negativo|incerto", "descricao": "...", "segmento_impactado": "..."}
                             for p in ["tratores", "colheitadeiras", "pulverizadores", "plantadeiras"]}
    }
    estrutura = {
        "fatores_economicos": [{**f, "tendencia": "...", "direcao": "melhorando|piorando|estavel",
                                "descricao": "...", "impactos": "...", "fonte": "..."} for f in FATORES_BASE[pais]],
        "sintese_estrategica": {
            "manchete": "...", "termometro": "positivo|negativo|incerto", "leitura": "...",
            "riscos": ["..."], "oportunidades": ["..."], "monitorar": ["..."]
        },
        "noticias": [{"tema": t, **base_noticia} for t in _temas_pais(pais)],
    }
    bloco_oficial = ""
    if pais == "br":
        linhas = "\n".join(f"    - {l}" for l in (contexto_oficial or [])) or "    - (indisponíveis)"
        bloco_oficial = f"""
    DADOS OFICIAIS DO BANCO CENTRAL DO BRASIL (coletados hoje):
{linhas}
    - Se mencionar Selic, dólar, inadimplência rural ou juros do crédito rural, use
      EXATAMENTE estes números. É PROIBIDO citar outro valor.
    - NÃO crie cards de "Juros (Selic)" nem de "Câmbio (Dólar)".
"""
    focos = "\n".join(f"         • {t}: {f}" for t, f in TEMAS_ESTRATEGICOS)
    if pais == "br":
        regra = ("Uma notícia para cada `tema` do JSON, na ordem, mantendo o campo `tema`: "
                 "primeiro os 4 temas estratégicos, depois as culturas (Soja, Milho, Café, Cana, "
                 "Algodão, Trigo). Nas culturas, prefira o fato que muda a renda/decisão do produtor "
                 "(preço, custo, safra, demanda externa) e não a cotação do dia.")
    else:
        regra = (f"Uma notícia por `tema` do JSON, mantendo o campo `tema`: os 4 temas "
                 f"estratégicos e {N_NOTICIAS_MERCADO_OUTROS} de 'Mercado & Produção' (assuntos diferentes).")
    return f"""
    Você é Analista de Inteligência de Mercado Sênior do setor de máquinas agrícolas
    (tratores, colheitadeiras, pulverizadores, plantadeiras), escrevendo para a diretoria.
    Seu trabalho é ligar os fatos do momento (política, eleições, crédito, comércio global,
    clima, preços) ao que eles significam para a demanda de máquinas.
    HOJE É {hoje_txt}. País: {NOMES_PAISES[pais].upper()}. Relatório de {mes_nome}/{year}.
{bloco_oficial}
    MANCHETES REAIS DISPONÍVEIS (Google News, últimos {JANELA_NOTICIAS_DIAS} dias) — formato [id] data | veículo | título:
{_bloco_candidatas(candidatos)}

    REGRAS DAS NOTÍCIAS (OBRIGATÓRIO):
    - Escolha SOMENTE entre as manchetes acima e informe o "id_noticia" exato (ex.: "N7").
    - Não repita id. Se nenhuma manchete servir para um tema, OMITA esse tema.
    - NÃO invente notícias, fatos ou números que não estejam no título ou nos dados oficiais.
    - Escreva tudo em português do Brasil.

    COMPARAÇÃO MÊS A MÊS: compare {mes_nome}/{year} com {mes_ant}/{ano_ant}. Se o dado oficial
    mais recente for anterior, compare os dois últimos meses publicados e diga o mês.
    1. fatores_economicos (baseie-se nas manchetes, nos dados oficiais e no contexto conhecido do país;
       sem número confirmado, descreva a tendência SEM inventar números):
       - "tendencia": 'positivo','negativo','incerto','estavel','alta','baixa','restritiva','expansiva'.
       - "direcao": 'melhorando'|'piorando'|'estavel' vs mês anterior, sob a ótica da demanda por máquinas.
       - "descricao": máx 25 palavras, com a comparação ("ante {mes_ant}").
       - "impactos": máx 30 palavras, citando tratores/colheitadeiras/pulverizadores/plantadeiras
         e se a compra tende a ACELERAR, ADIAR ou ficar NEUTRA.
       - "fonte": veículos das manchetes usadas e/ou "BCB".
       - "Margens Produtor": quais culturas melhoraram e quais pioraram ante {mes_ant}.
    2. noticias: {regra}
       Foco dos temas estratégicos:
{focos}
       CRITÉRIO DE ESCOLHA: a manchete que MAIS altera a decisão de investimento do produtor em
       máquinas (renda, crédito, confiança, custo, prazo). Evite nota institucional ou cotação diária.
       Política: relate FATOS e consequências econômicas de forma NEUTRA e apartidária.
       - "titulo_noticia" (máx 15 palavras, fiel ao título original), "corpo_noticia" (máx 40 palavras:
         o fato do título e o contexto).
       - "por_que_importa": máx 30 palavras — efeito de 2ª ordem para a indústria de máquinas.
       - "relevancia": 'alta' | 'media' | 'baixa' para a demanda de máquinas.
       - "horizonte": 'imediato' | '3-6 meses' | '6-12 meses'.
       - "impacto_produtos": "tendencia", "descricao" (máx 20 palavras), "segmento_impactado":
         tratores 'Baixa Potência (<80cv)'|'Média Potência (80-170cv)'|'Alta Potência (>170cv)';
         plantadeiras 'Pequeno Porte (<20 linhas)'|'Grande Porte (>20 linhas)';
         colheitadeiras 'Médio Porte (Classes 4-6)'|'Grande Porte (Classes 7+)';
         pulverizadores 'De Arrasto'|'Autopropelido'; ou "".
    3. sintese_estrategica (resumo executivo do país, baseado nas manchetes):
       - "manchete": máx 15 palavras, a mensagem central do mês para quem vende máquinas.
       - "termometro": 'positivo'|'negativo'|'incerto' para a demanda nos próximos 6 meses.
       - "leitura": máx 60 palavras conectando política, crédito, clima, preços e câmbio (causa -> efeito).
       - "riscos", "oportunidades", "monitorar": 2 a 3 itens cada, máx 15 palavras por item;
         "monitorar" = eventos/datas dos próximos 30-60 dias.
    Responda SOMENTE com o JSON abaixo preenchido, sem texto antes/depois e sem markdown.
    {json.dumps(estrutura, indent=2, ensure_ascii=False)}
    """


# -----------------------------------------------------------------------------
# Validações
# -----------------------------------------------------------------------------
def _parse_data(valor):
    s = str(valor or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _filtrar_noticias_recentes(noticias, now):
    hoje = now.date()
    corte = hoje - datetime.timedelta(days=JANELA_NOTICIAS_DIAS)
    validas, descartadas = [], []
    for n in noticias or []:
        if not isinstance(n, dict) or not str(n.get("titulo_noticia", "")).strip() \
                or n.get("titulo_noticia") == "...":
            continue
        d = _parse_data(n.get("data_publicacao"))
        titulo = str(n.get("titulo_noticia"))[:60]
        if d is None:
            descartadas.append((titulo, f"sem data ('{n.get('data_publicacao')}')"))
        elif d > hoje + datetime.timedelta(days=1):
            descartadas.append((titulo, f"data futura {d:%d/%m/%Y}"))
        elif d < corte:
            descartadas.append((titulo, f"antiga {d:%d/%m/%Y} (corte {corte:%d/%m/%Y})"))
        else:
            n["data_publicacao"] = d.isoformat()
            validas.append(n)
    return validas, descartadas


def _vincular_noticias(noticias, mapa, now):
    """Liga cada notícia da IA à manchete real do RSS (link, veículo e data vêm do RSS)."""
    validas, descartadas, usados = [], [], set()
    for n in noticias or []:
        if not isinstance(n, dict):
            continue
        cid = str(n.get("id_noticia", "")).strip().strip("[]").upper()
        titulo = str(n.get("titulo_noticia", ""))[:60]
        c = mapa.get(cid)
        if not c:
            descartadas.append((titulo, f"id inexistente '{cid}'"))
            continue
        if cid in usados:
            descartadas.append((titulo, f"id repetido {cid}"))
            continue
        usados.add(cid)
        n["id_noticia"] = cid
        n["url_noticia"] = c["url"]
        n["fonte_noticia"] = c["fonte"]
        n["data_publicacao"] = c["data"]
        if not str(n.get("titulo_noticia", "")).strip() or n.get("titulo_noticia") == "...":
            n["titulo_noticia"] = c["titulo"]
        validas.append(n)
    ok, desc2 = _filtrar_noticias_recentes(validas, now)
    return ok, descartadas + desc2


def _finish_reason(resp):
    try:
        return str(resp.candidates[0].finish_reason)
    except Exception:
        return "?"


def _salvar_debug(script_dir, pais, rotulo, tentativa, texto):
    if not DEBUG_IA:
        return
    try:
        pasta = script_dir / "debug_ia"
        pasta.mkdir(exist_ok=True)
        (pasta / f"{pais}_{rotulo}_{tentativa}.txt").write_text(texto or "(resposta vazia)", encoding="utf-8")
    except Exception:
        pass


def _tratar_erro(e, pais, rotulo, tentativa, modelo):
    """Retorna False se deve abandonar o país (cota esgotada em todos os modelos)."""
    if _cota_diaria(e) or _modelo_indisponivel(e):
        motivo = "cota DIÁRIA esgotada (429)" if _cota_diaria(e) else "modelo não disponível (404)"
        print(f"   ⚠ {pais.upper()} ({rotulo}, {modelo}): {motivo}.")
        _registrar_cota_esgotada(modelo)
        return not _COTA["esgotada"]
    print(f"   ⚠ {pais.upper()} ({rotulo}, tentativa {tentativa}): {str(e)[:300]}")
    time.sleep(_espera_erro(e, tentativa, pais))
    return True


def _espera_erro(e, tentativa, pais=""):
    msg = str(e)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
        print(f"      ⏳ {pais.upper()}: limite por minuto do Gemini (429). Aguardando 60s...")
        return 60
    return 3 * tentativa


def _config_ia():
    """Sem pesquisa Google (cota maior); resposta em JSON."""
    kw = dict(temperature=0.2, max_output_tokens=MAX_TOKENS_RESPOSTA,
              response_mime_type="application/json")
    try:
        kw["thinking_config"] = types.ThinkingConfig(thinking_budget=ORCAMENTO_RACIOCINIO)
        return types.GenerateContentConfig(**kw)
    except Exception:          # biblioteca antiga sem ThinkingConfig
        kw.pop("thinking_config", None)
        return types.GenerateContentConfig(**kw)


def _gerar_pais(client, pais, contexto_oficial, now, script_dir):
    """
    v12: coleta manchetes no Google News RSS e pede ao Gemini (sem pesquisa) a seleção +
    análise. Retorna (dados|None, status).
    """
    t0 = time.time()
    candidatos = coletar_noticias_rss(pais, now)
    mapa = {c["id"]: c for c in candidatos}
    prompt = _prompt_pais(pais, contexto_oficial, now, candidatos)
    cfg = _config_ia()
    melhor = None
    for tentativa in range(1, TENTATIVAS_IA + 1):
        if _COTA["esgotada"]:
            break
        modelo = _modelo_atual()
        try:
            t1 = time.time()
            resp = client.models.generate_content(model=modelo, contents=prompt, config=cfg)
            texto = resp.text or ""
            _salvar_debug(script_dir, pais, "ia", tentativa, texto)
            if "MAX_TOKENS" in _finish_reason(resp):
                print(f"      ⚠ {pais.upper()}: resposta cortada por limite de tokens")
            dados = _extrair_json(texto)
            if not isinstance(dados, dict) or not dados.get("fatores_economicos"):
                raise ValueError("JSON sem fatores_economicos")
            validas, descartadas = _vincular_noticias(dados.get("noticias"), mapa, now)
            print(f"   {pais.upper()} tentativa {tentativa} ({modelo}): {time.time() - t1:.0f}s | "
                  f"{len(candidatos)} manchetes | {len(validas)} notícias selecionadas")
            for t, motivo in descartadas:
                print(f"      ✂ {pais.upper()} descartada: {t} → {motivo}")
            dados["noticias"] = validas
            if not validas:
                dados.pop("sintese_estrategica", None)
            if melhor is None or len(validas) > len(melhor["noticias"]):
                melhor = dados
            if validas or not candidatos:
                break
        except Exception as e:
            if not _tratar_erro(e, pais, "IA", tentativa, modelo):
                break
    if melhor is None:
        print(f"   ❌ {pais.upper()}: IA falhou.")
        return None, {"modo": "cota" if _COTA["esgotada"] else "falha", "validas": 0}
    n = len(melhor["noticias"])
    icone = "✅" if n >= MINIMO_NOTICIAS_RECENTES else "⚠"
    print(f"   {icone} {pais.upper()} concluído em {time.time() - t0:.0f}s: {n} notícias")
    return melhor, {"modo": "rss+ia", "validas": n}


def _pos_processar_pais(pais, dados_pais):
    if pais == "br":
        dados_pais["fatores_economicos"] = [f for f in dados_pais.get("fatores_economicos", [])
                                            if f.get("titulo") not in TITULOS_OFICIAIS_BR]
    for n in dados_pais.get("noticias", []):
        d = _parse_data(n.get("data_publicacao"))
        fonte = str(n.get("fonte_noticia") or TRANSLATIONS["pt"]["not_informed"])
        if d and d.strftime("%d/%m/%Y") not in fonte:
            fonte = f"{fonte} · {d:%d/%m/%Y}"
        url = str(n.get("url_noticia") or "")
        if url.startswith("http") and "href=" not in fonte:
            fonte = f'<a href="{url}" target="_blank" rel="noopener">{fonte}</a>'
        n["fonte_noticia"] = fonte
    return dados_pais


def atualizar_dados_com_ia(dados_path, script_dir, contexto_oficial=None):
    """Países em paralelo; cache por país (CACHE_VALIDADE_DIAS); mantém dados anteriores em falha."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    inicio = time.time()
    now = datetime.datetime.now()
    cache_path = script_dir / f"cache_dados_ia_{CACHE_VERSAO}.json"
    cache = {}
    print(f"🗂  Cache: {cache_path}  (existe: {cache_path.exists()})")
    cache_disco = {}
    if cache_path.exists():
        try:
            cache_disco = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache_disco = {}
    # dados da execução anterior (arquivo versionado no repositório) = rede de segurança
    anteriores = {}
    if dados_path.exists():
        try:
            anteriores = json.loads(dados_path.read_text(encoding="utf-8")) or {}
        except Exception:
            anteriores = {}
    if cache_path.exists() and not FORCAR_ATUALIZACAO:
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️ Cache inválido ({e}). Ignorando.")
    elif FORCAR_ATUALIZACAO:
        print("♻️  --forcar ativo: cache ignorado, todos os países serão regerados.")

    def dados_anteriores(pais):
        """Melhor versão anterior do país: cache (mesmo vencido) ou dados_paises.json."""
        for fonte in ((cache.get(pais) or cache_disco.get(pais) or {}).get("dados"), anteriores.get(pais)):
            if isinstance(fonte, dict) and fonte.get("noticias"):
                return fonte
        return None

    def cache_valido(pais):
        item = cache.get(pais)
        if not item:
            return None
        try:
            gerado = datetime.datetime.fromisoformat(item["gerado_em"])
        except Exception:
            return None
        if (now - gerado).days >= CACHE_VALIDADE_DIAS:
            return None
        validas, _ = _filtrar_noticias_recentes(item["dados"].get("noticias", []), now)
        if len(validas) < MINIMO_NOTICIAS_RECENTES:
            return None
        return item["dados"]

    def erro_pais(pais, msg):
        return {"fatores_economicos": [{**f, "tendencia": "incerto", "direcao": "estavel", "descricao": msg,
                                         "impactos": "Não foi possível carregar os impactos.",
                                         "fonte": "Sistema Interno"} for f in FATORES_BASE[pais]],
                "noticias": []}

    if not genai or not os.environ.get("GEMINI_API_KEY"):
        msg = "IA indisponível (biblioteca google-genai ou GEMINI_API_KEY ausente)."
        print(f"❌ {msg}")
        dados_path.write_text(json.dumps({p: erro_pais(p, msg) for p in FATORES_BASE},
                                         ensure_ascii=False, indent=2), encoding="utf-8")
        return False
    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"),
                              http_options=types.HttpOptions(timeout=TIMEOUT_CHAMADA_SEG * 1000))
    except Exception:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    resultado, resumo, falhas = {}, {}, []
    pendentes = []
    for pais in FATORES_BASE:
        em_cache = cache_valido(pais)
        if em_cache is not None:
            print(f"   🧠 {pais.upper()}: cache recente reaproveitado.")
            resultado[pais] = em_cache
            resumo[pais] = ("cache", len(em_cache.get("noticias", [])))
        else:
            pendentes.append(pais)

    if pendentes:
        print(f"🤖 Gerando {len(pendentes)} país(es) | {PAISES_EM_PARALELO} em paralelo | modelo {MODELO_GEMINI} "
              f"(reserva: {', '.join(MODELOS_RESERVA) or '-'}) | notícias: Google News RSS {JANELA_NOTICIAS_DIAS} dias")
        with ThreadPoolExecutor(max_workers=max(1, PAISES_EM_PARALELO)) as ex:
            futuros = {}
            for i, pais in enumerate(pendentes):
                futuros[ex.submit(_gerar_pais, client, pais, contexto_oficial, now, script_dir)] = pais
                if i < PAISES_EM_PARALELO:
                    time.sleep(1)   # escalona o arranque para não estourar o limite por minuto
            for fut in as_completed(futuros):
                pais = futuros[fut]
                try:
                    dados_pais, status = fut.result()
                except Exception as e:
                    print(f"   ❌ {pais.upper()}: erro inesperado {e}")
                    dados_pais, status = None, {"modo": "falha"}
                antigo = dados_anteriores(pais)
                if dados_pais is None:
                    falhas.append(pais)
                    if antigo:
                        print(f"   ↩ {pais.upper()}: IA indisponível; mantendo dados anteriores "
                              f"({len(antigo.get('noticias', []))} notícias).")
                        dados_pais, status = antigo, {"modo": "anterior"}
                    else:
                        dados_pais = erro_pais(pais, "Falha na comunicação com a IA nesta execução.")
                else:
                    dados_pais = _pos_processar_pais(pais, dados_pais)
                    if antigo and len(dados_pais.get("noticias", [])) < len(antigo.get("noticias", [])):
                        print(f"   ↩ {pais.upper()}: rodada nova trouxe menos notícias; mantendo as anteriores.")
                        dados_pais["noticias"] = antigo["noticias"]
                        if antigo.get("sintese_estrategica"):
                            dados_pais["sintese_estrategica"] = antigo["sintese_estrategica"]
                    if dados_pais.get("noticias"):
                        if FORCAR_ATUALIZACAO and not cache:
                            cache.update({k: v for k, v in cache_disco.items() if k != pais})
                        cache[pais] = {"gerado_em": now.isoformat(timespec="seconds"), "dados": dados_pais}
                        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
                        print(f"   💾 {pais.upper()}: cache gravado ({len(dados_pais['noticias'])} notícias)")
                    if len(dados_pais.get("noticias", [])) < MINIMO_NOTICIAS_RECENTES:
                        falhas.append(pais)
                resultado[pais] = dados_pais
                resumo[pais] = (status.get("modo"), len(dados_pais.get("noticias", [])))

    resultado = {p: resultado[p] for p in FATORES_BASE if p in resultado}   # ordem original
    dados_path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📋 RESUMO DAS NOTÍCIAS (em {(time.time() - inicio) / 60:.1f} min)")
    print("   País | Origem       | Notícias recentes")
    for pais in FATORES_BASE:
        modo, n = resumo.get(pais, ("?", 0))
        print(f"   {pais.upper():4} | {str(modo):12} | {n}")
    if falhas:
        print(f"⚠️ Países com poucas/nenhuma notícia recente: {', '.join(p.upper() for p in falhas)}. "
              f"A próxima execução tenta de novo. Veja a pasta debug_ia/.")
        return False
    print(f"✅ Todos os países com notícias recentes. Cache: {cache_path.name}")
    return True


def gerar_dashboard(template_path, output_path, dados_path, cards_oficiais_br=None):
    try:
        print(f"📄 Lendo template de '{template_path.name}'...")
        html_content = template_path.read_text(encoding="utf-8")
        dados_completos = carregar_dados_paises(dados_path)
        if not dados_completos:
            raise ValueError("Não foi possível carregar os dados dos países do arquivo JSON.")
        # Cards oficiais do BCB no INÍCIO dos fatores do Brasil + cards da IA.
        if "br" in dados_completos and cards_oficiais_br:
            fatores_ia = [f for f in dados_completos["br"].get("fatores_economicos", [])
                          if f.get("titulo") not in TITULOS_OFICIAIS_BR]
            dados_completos["br"]["fatores_economicos"] = list(cards_oficiais_br) + fatores_ia
        now = datetime.datetime.now()
        year, month_idx = now.year, now.month - 1
        mes_anterior_nome = _nomes_mes_por_indice((now.month - 2) % 12)
        html_content = html_content.replace("{{DATA_RELATORIO_PT}}", f"{TRANSLATIONS['pt']['months'][month_idx]} de {year}")
        html_content = html_content.replace("{{DATA_RELATORIO_EN}}", f"{TRANSLATIONS['en']['months'][month_idx]} {year}")
        html_content = html_content.replace("{{DATA_RELATORIO_ES}}", f"{TRANSLATIONS['es']['months'][month_idx]} de {year}")
        print("📊 Gerando blocos de análise e notícias para cada país...")
        for cp in dados_completos:
            ph = f"{{{{BLOCO_NOTICIAS_{cp.upper()}}}}}"
            if ph not in html_content:
                print(f"   ⚠ Placeholder {ph} NÃO existe no template — notícias de {cp.upper()} não serão exibidas.")
        for codigo_pais, dados_pais in dados_completos.items():
            html_content = html_content.replace(
                f"{{{{BLOCO_ANALISES_{codigo_pais.upper()}}}}}",
                gerar_bloco_analises(dados_pais.get('fatores_economicos', []), mes_anterior_nome))
            html_content = html_content.replace(
                f"{{{{BLOCO_NOTICIAS_{codigo_pais.upper()}}}}}",
                gerar_blocos_noticias(dados_pais.get('noticias', []), codigo_pais,
                                      dados_pais.get('sintese_estrategica')))
        print("Processando Commodity Intelligence...")
        xlsx = template_path.parent / "data" / "precos_agricolas_latest.xlsx"
        commodities, aviso = processar_commodities(xlsx)
        html_content = html_content.replace("{{BLOCO_COMMODITIES}}", gerar_bloco_commodities(commodities, aviso))
        print("Processando Crédito Rural Deep Dive...")
        html_content = html_content.replace("{{BLOCO_CREDITO_RURAL}}", gerar_bloco_credito_rural(processar_credito_rural()))
        html_content = html_content.replace("</head>", CSS_CREDITO_RURAL + CSS_NOTICIAS_ESTRATEGICAS + "</head>")
        feedback_modal_html = f"""
<style>
    .feedback-button {{ position: fixed; bottom: 25px; right: 25px; background-color: #CC0000; color: white;
        padding: 12px 18px; border-radius: 50px; font-family: 'Roboto', sans-serif; font-size: 15px; font-weight: 500;
        box-shadow: 0 5px 15px rgba(0,0,0,0.25); z-index: 1000; display: flex; align-items: center; gap: 10px;
        cursor: pointer; border: none; transition: transform 0.2s ease-in-out, background-color 0.3s; }}
    .feedback-button:hover {{ background-color: #A30000; transform: translateY(-3px); }}
    .feedback-button svg {{ width: 20px; height: 20px; }}
    .modal-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6);
        z-index: 2000; display: none; align-items: center; justify-content: center; }}
    .modal-content {{ background: #fff; padding: 30px; border-radius: 12px; width: 90%; max-width: 550px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2); position: relative; }}
    .modal-close {{ position: absolute; top: 15px; right: 15px; background: none; border: none; font-size: 24px;
        color: #888; cursor: pointer; line-height: 1; }}
    .modal-title {{ margin-top: 0; font-size: 22px; color: #333; }}
    .form-group {{ margin-bottom: 20px; }}
    .form-group label {{ display: block; margin-bottom: 8px; font-weight: 500; color: #555; }}
    .form-group input, .form-group textarea {{ width: 100%; padding: 10px; border: 1px solid #ccc;
        border-radius: 6px; font-family: 'Roboto', sans-serif; font-size: 15px; }}
    .form-group textarea {{ resize: vertical; min-height: 100px; }}
    .submit-btn {{ background-color: #CC0000; color: white; border: none; padding: 12px 25px; border-radius: 6px;
        font-size: 16px; font-weight: 500; cursor: pointer; width: 100%; }}
    .submit-btn:hover {{ background-color: #A30000; }}
    .formspree-thanks {{ display: none; text-align: center; padding: 20px; }}
</style>
<button id="openFeedbackModal" class="feedback-button">
    <svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 16 16"><path d="M2 6a6 6 0 1 1 10.174 4.31c-.203.196-.359.4-.453.619l-.762 1.769A.5.5 0 0 1 10.5 13h-5a.5.5 0 0 1-.46-.302l-.761-1.77a1.964 1.964 0 0 0-.453-.618A6 6 0 0 1 2 6zm6 8.5a.5.5 0 0 0 .5.5h.5a.5.5 0 0 0 0-1h-.5a.5.5 0 0 0-.5.5zM8 1a5 5 0 0 0-3.536 8.536L5.136 11.5h5.728l.672-1.964A5 5 0 0 0 8 1z"/></svg>
    <span {i18n_attrs("suggest_improvement")}>{TRANSLATIONS["pt"]["suggest_improvement"]}</span>
</button>
<div id="feedbackModal" class="modal-overlay">
    <div class="modal-content">
        <button id="closeFeedbackModal" class="modal-close">&times;</button>
        <h2 class="modal-title">Feedback sobre o Dashboard</h2>
        <form id="feedbackForm" action="https://formspree.io/f/mvzjaqow" method="POST">
            <div class="form-group"><label for="satisfaction">Em uma escala de 1 a 5, quão útil é este dashboard para você?</label>
                <input type="number" name="satisfaction" min="1" max="5" required style="width: 80px;"></div>
            <div class="form-group"><label for="suggestion">Deixe sua sugestão de melhoria ou novo indicador aqui:</label>
                <textarea id="suggestion" name="suggestion" required></textarea></div>
            <div class="form-group"><label for="email">Seu e-mail (opcional, para entrarmos em contato)</label>
                <input type="email" id="email" name="email"></div>
            <button type="submit" class="submit-btn">Enviar Feedback</button>
        </form>
        <div id="formspreeThanks" class="formspree-thanks"><h3>Obrigado pelo seu feedback!</h3><p>Sua sugestão foi enviada com sucesso.</p></div>
    </div>
</div>
<script>
    const openBtn = document.getElementById('openFeedbackModal');
    const closeBtn = document.getElementById('closeFeedbackModal');
    const modal = document.getElementById('feedbackModal');
    const form = document.getElementById('feedbackForm');
    const thanksMessage = document.getElementById('formspreeThanks');
    openBtn.addEventListener('click', () => {{ modal.style.display = 'flex'; }});
    closeBtn.addEventListener('click', () => {{ modal.style.display = 'none'; }});
    modal.addEventListener('click', (e) => {{ if (e.target === modal) {{ modal.style.display = 'none'; }} }});
    form.addEventListener('submit', async (e) => {{
        e.preventDefault();
        try {{
            const response = await fetch(form.action, {{ method: 'POST', body: new FormData(form), headers: {{ 'Accept': 'application/json' }} }});
            if (response.ok) {{
                form.style.display = 'none'; thanksMessage.style.display = 'block';
                setTimeout(() => {{ modal.style.display = 'none'; form.style.display = 'block'; thanksMessage.style.display = 'none'; form.reset(); }}, 3000);
            }} else {{ alert('Ocorreu um erro ao enviar o formulário. Tente novamente.'); }}
        }} catch (error) {{ alert('Ocorreu um erro de conexão. Verifique sua internet e tente novamente.'); }}
    }});
</script>
"""
        html_content = html_content.replace("</body>", feedback_modal_html + "</body>")
        output_path.write_text(html_content, encoding="utf-8")
        print(f"✅ Dashboard '{output_path.name}' gerado com sucesso!")
    except Exception as e:
        print(f"❌ Erro na geração do dashboard: {e}")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    script_dir = Path(__file__).resolve().parent
    template_arquivo = script_dir / "dashboard_template.html"
    output_arquivo = script_dir / "index.html"
    dados_arquivo = script_dir / "dados_paises.json"
    print("🚀 Iniciando a geração do dashboard 'Early Signals' (v12)...")
    try:
        if not template_arquivo.exists():
            raise FileNotFoundError(f"Template '{template_arquivo.name}' não encontrado em '{script_dir}'")
        # 1) Dados oficiais do BCB primeiro (alimentam os cards E o prompt da IA).
        cards_oficiais_br, contexto_oficial = coletar_dados_oficiais_br()
        # 2) Notícias do Google News RSS + análise da IA.
        atualizar_dados_com_ia(dados_arquivo, script_dir, contexto_oficial)
        # 3) Monta o dashboard.
        gerar_dashboard(template_arquivo, output_arquivo, dados_arquivo, cards_oficiais_br)
        if not output_arquivo.exists() or output_arquivo.stat().st_size == 0:
            raise RuntimeError("index.html não foi gerado corretamente.")
        print(f"✅ index.html validado: {output_arquivo.stat().st_size:,} bytes")
    except Exception as e:
        print("\n" + "=" * 60 + "\n❌ OCORREU UM ERRO E O ARQUIVO NÃO FOI GERADO\n" + "=" * 60)
        print(f"\nCausa do erro: {e}\n")
        traceback.print_exc()
        sys.exit(1)
