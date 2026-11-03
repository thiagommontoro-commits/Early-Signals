# -*- coding: utf-8 -*-
"""
gerador_dashboard_early_signals.py   ←←← SUBSTITUI o arquivo que já existe
==========================================================================
VERSÃO: v5 (dados oficiais + IA com pesquisa web, um país por vez)

  v5: CORRIGE NOTÍCIAS SUMINDO — a IA passa a gerar um país por vez, com
      validação (cada país precisa ter notícias) e cache v5 novo.

  1. "Juros (Selic)" e "Câmbio (Dólar)" do Brasil vêm do Banco Central
     (arquivo 'modulo_indicadores_oficiais.py' — séries SGS 432 e 1).
  2. Dados oficiais (Selic, Dólar, Inadimplência, Juros PF/PJ) são buscados
     ANTES da IA e injetados no prompt — a IA é proibida de citar outros valores.
  3. A IA (Gemini) usa PESQUISA NO GOOGLE para os demais fatores e notícias.
  4. Cache renomeado para 'cache_dados_ia_v4_AAAA_MM.json' -> o cache antigo
     com números errados é ignorado automaticamente.
  5. Mantidos: comparação mês a mês, selo "vs <mês>" derivado do dado,
     impactos citando linhas de máquinas, aba Margem removida.
"""
import os
import re
import sys
import json
from pathlib import Path
import datetime
import traceback
import time

from dotenv import load_dotenv
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

CACHE_VERSAO = "v5"

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


def gerar_blocos_noticias(noticias_pais, codigo_pais=""):
    if not noticias_pais:
        return f'<div class="news-grid"><p {i18n_attrs("no_news")}>{TRANSLATIONS["pt"]["no_news"]}</p></div>'
    html_output = '<div class="news-grid">\n'
    temas_brasil = [("Soja", "🌱"), ("Milho", "🌽"), ("Café", "☕"), ("Cana", "🎋"), ("Algodão", "🧺"), ("Trigo", "🌾")]
    for i, noticia in enumerate(noticias_pais):
        tn = noticia.get('tendencia_noticia', 'incerto')
        tk = get_farol_translation_key(tn)
        icon_html = ""
        if codigo_pais == 'br' and i < len(temas_brasil):
            tema, icone = temas_brasil[i]
            icon_html = f'<span class="news-topic-icon" title="{tema}">{icone}</span>'
        html_output += f'''
        <div class="news-block">
            <div class="news-header">
                <h3 class="news-title">{icon_html}{noticia.get('titulo_noticia', TRANSLATIONS['pt']['unavailable_title'])}</h3>
                <span class="farol {get_farol_class(tn)}"><span class="farol-dot"></span><span {i18n_attrs(tk)}>{TRANSLATIONS['pt'][tk]}</span></span>
            </div>
            <div class="news-body">
                {noticia.get('corpo_noticia', TRANSLATIONS['pt']['unavailable_body'])}
                <p class="news-source"><strong {i18n_attrs("source")}>{TRANSLATIONS["pt"]["source"]}:</strong> {noticia.get('fonte_noticia', TRANSLATIONS['pt']['not_informed'])}</p>
            </div>
            <div class="machinery-analysis">
                <div class="analysis-title" {i18n_attrs("product_line_impact")}>{TRANSLATIONS['pt']['product_line_impact']}</div>
                <div class="machinery-items">
        '''
        for produto, impacto in noticia.get('impacto_produtos', {}).items():
            tp = impacto.get('tendencia', 'incerto')
            tkp = get_farol_translation_key(tp)
            seg = impacto.get('segmento_impactado')
            seg_html = f' <span class="m-segment">({seg})</span>' if seg and str(seg).strip() else ''
            html_output += f'''
                    <div class="m-item">
                        <div class="m-header"><span class="m-name">{produto.capitalize()}{seg_html}</span><span class="farol {get_farol_class(tp)}"><span class="farol-dot"></span><span {i18n_attrs(tkp)}>{TRANSLATIONS['pt'][tkp]}</span></span></div>
                        <div class="m-desc">{impacto.get('descricao', TRANSLATIONS['pt']['analysis_unavailable'])}</div>
                    </div>'''
        html_output += '\n                </div>\n            </div>\n        </div>'
    return html_output + '\n</div>'


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
    """Extrai o objeto JSON da resposta (remove cercas ``` e texto extra)."""
    t = texto.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    ini, fim = t.find("{"), t.rfind("}")
    if ini == -1 or fim == -1:
        raise ValueError("Resposta da IA sem objeto JSON.")
    return json.loads(t[ini:fim + 1])


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


def _n_noticias(pais):
    return 6 if pais in ("br", "ar") else 4


def _prompt_pais(pais, contexto_oficial, now):
    """Prompt de UM país (resposta menor = sem truncamento do JSON)."""
    meses_pt = TRANSLATIONS["pt"]["months"]
    year, month = now.year, now.month
    mes_nome, mes_ant = meses_pt[month - 1], meses_pt[(month - 2) % 12]
    ano_ant = year if month > 1 else year - 1
    hoje_txt = now.strftime("%d/%m/%Y")

    base_noticia = {
        "titulo_noticia": "...", "tendencia_noticia": "positivo|negativo|incerto",
        "corpo_noticia": "...", "fonte_noticia": "...",
        "impacto_produtos": {p: {"tendencia": "positivo|negativo|incerto", "descricao": "...", "segmento_impactado": "..."}
                             for p in ["tratores", "colheitadeiras", "pulverizadores", "plantadeiras"]}
    }
    if pais == "br":
        noticias = [{**base_noticia, "tema": t} for t in TEMAS_BR]
    else:
        noticias = [base_noticia] * _n_noticias(pais)
    estrutura = {
        "fatores_economicos": [{**f, "tendencia": "...", "direcao": "melhorando|piorando|estavel",
                                "descricao": "...", "impactos": "...", "fonte": "..."} for f in FATORES_BASE[pais]],
        "noticias": noticias,
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
    regra_br = ("Retorne EXATAMENTE 6 notícias, uma para cada valor do campo `tema` "
                "(Soja, Milho, Café, Cana, Algodão, Trigo), nessa ordem."
                if pais == "br" else f"Retorne EXATAMENTE {_n_noticias(pais)} notícias.")

    return f"""
    Você é Analista de Inteligência de Mercado Sênior do setor de máquinas agrícolas.
    HOJE É {hoje_txt}. País: {NOMES_PAISES[pais].upper()}. Relatório de {mes_nome}/{year}.
{bloco_oficial}
    PESQUISA E ATUALIDADE:
    - Use a pesquisa Google para fatores e notícias. Não escreva números de memória;
      sem número confiável e recente, descreva o fato sem número.
    - Apenas informações dos últimos 45 dias. "fonte" = veículo/órgão real.

    COMPARAÇÃO MÊS A MÊS: compare {mes_nome}/{year} com {mes_ant}/{ano_ant}. Se o dado oficial
    mais recente for anterior, compare os dois últimos meses publicados e diga o mês.

    1. fatores_economicos:
       - "tendencia": 'positivo','negativo','incerto','estavel','alta','baixa','restritiva','expansiva'.
       - "direcao": 'melhorando'|'piorando'|'estavel' vs mês anterior, sob a ótica da demanda por máquinas.
       - "descricao": máx 25 palavras, com a comparação ("ante {mes_ant}") e o número.
       - "impactos": máx 30 palavras, citando tratores/colheitadeiras/pulverizadores/plantadeiras
         e se a compra tende a ACELERAR, ADIAR ou ficar NEUTRA.
       - "Margens Produtor": quais culturas melhoraram e quais pioraram ante {mes_ant}.
    2. noticias: REAIS e RECENTES. {regra_br}
       - "titulo_noticia" (máx 15 palavras), "corpo_noticia" (máx 40 palavras), "fonte_noticia" (veículo real).
       - "impacto_produtos": "tendencia", "descricao" (máx 20 palavras), "segmento_impactado":
         tratores 'Baixa Potência (<80cv)'|'Média Potência (80-170cv)'|'Alta Potência (>170cv)';
         plantadeiras 'Pequeno Porte (<20 linhas)'|'Grande Porte (>20 linhas)';
         colheitadeiras 'Médio Porte (Classes 4-6)'|'Grande Porte (Classes 7+)';
         pulverizadores 'De Arrasto'|'Autopropelido'; ou "".

    Responda SOMENTE com o JSON abaixo preenchido, sem texto antes/depois e sem markdown.

    {json.dumps(estrutura, indent=2, ensure_ascii=False)}
    """


def _resposta_valida(dados, pais):
    if not isinstance(dados, dict):
        return False, "resposta não é objeto JSON"
    if not dados.get("fatores_economicos"):
        return False, "sem fatores_economicos"
    noticias = [n for n in dados.get("noticias", []) if isinstance(n, dict) and n.get("titulo_noticia")]
    if not noticias:
        return False, "sem notícias"
    return True, f"{len(dados['fatores_economicos'])} fatores, {len(noticias)} notícias"


def _gerar_pais(client, pais, contexto_oficial, now):
    """Gera UM país. 1º com pesquisa Google, 2º sem pesquisa. Retorna dict ou None."""
    prompt = _prompt_pais(pais, contexto_oficial, now)
    modos = [
        ("com pesquisa Google", types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.2, max_output_tokens=16384)),
        ("sem pesquisa", types.GenerateContentConfig(
            response_mime_type="application/json", temperature=0.2, max_output_tokens=16384)),
    ]
    for rotulo, config in modos:
        for tentativa in range(1, 3):
            try:
                resp = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
                dados = _extrair_json(resp.text or "")
                ok, motivo = _resposta_valida(dados, pais)
                if ok:
                    print(f"   ✅ {pais.upper()} ({rotulo}): {motivo}")
                    return dados
                print(f"   ⚠ {pais.upper()} ({rotulo}, tentativa {tentativa}): resposta incompleta — {motivo}")
            except Exception as e:
                print(f"   ⚠ {pais.upper()} ({rotulo}, tentativa {tentativa}): {e}")
            time.sleep(5 * tentativa)
    print(f"   ❌ {pais.upper()}: IA falhou em todos os modos.")
    return None


def atualizar_dados_com_ia(dados_path, script_dir, contexto_oficial=None):
    """
    v5: gera UM PAÍS POR VEZ. Na v4 era uma única chamada gigante (8 países +
    40 notícias); com a pesquisa Google ativada a resposta era cortada no meio
    e as notícias se perdiam. Agora cada país é validado (precisa ter notícias)
    e, se um falhar, os demais continuam. O cache só é gravado com TODOS os
    países completos — senão a próxima execução tenta de novo.
    """
    now = datetime.datetime.now()
    cache_path = script_dir / f"cache_dados_ia_{CACHE_VERSAO}_{now.year}_{now.month:02d}.json"

    if cache_path.exists():
        print(f"🧠 Usando cache {cache_path.name}.")
        try:
            dados = json.loads(cache_path.read_text(encoding="utf-8"))
            dados_path.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception as e:
            print(f"⚠️ Cache inválido ({e}). Gerando novamente.")

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

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    print(f"🤖 Gerando análises da IA país a país ({len(FATORES_BASE)} países)...")

    resultado, falhas = {}, []
    for pais in FATORES_BASE:
        dados_pais = _gerar_pais(client, pais, contexto_oficial, now)
        if dados_pais is None:
            falhas.append(pais)
            dados_pais = erro_pais(pais, "Falha na comunicação com a IA nesta execução.")
        if pais == "br":
            dados_pais["fatores_economicos"] = [f for f in dados_pais.get("fatores_economicos", [])
                                                if f.get("titulo") not in TITULOS_OFICIAIS_BR]
            for n in dados_pais.get("noticias", []):
                n.pop("tema", None)
        resultado[pais] = dados_pais
        time.sleep(4)  # respeita limite de requisições por minuto do Gemini

    dados_path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    if falhas:
        print(f"⚠️ Países sem análise completa: {', '.join(p.upper() for p in falhas)}. "
              f"Cache NÃO gravado — a próxima execução tenta novamente.")
        return False
    cache_path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Análises de todos os países salvas em {cache_path.name}.")
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
        for codigo_pais, dados_pais in dados_completos.items():
            html_content = html_content.replace(
                f"{{{{BLOCO_ANALISES_{codigo_pais.upper()}}}}}",
                gerar_bloco_analises(dados_pais.get('fatores_economicos', []), mes_anterior_nome))
            html_content = html_content.replace(
                f"{{{{BLOCO_NOTICIAS_{codigo_pais.upper()}}}}}",
                gerar_blocos_noticias(dados_pais.get('noticias', []), codigo_pais))

        print("Processando Commodity Intelligence...")
        xlsx = template_path.parent / "data" / "precos_agricolas_latest.xlsx"
        commodities, aviso = processar_commodities(xlsx)
        html_content = html_content.replace("{{BLOCO_COMMODITIES}}", gerar_bloco_commodities(commodities, aviso))

        print("Processando Crédito Rural Deep Dive...")
        html_content = html_content.replace("{{BLOCO_CREDITO_RURAL}}", gerar_bloco_credito_rural(processar_credito_rural()))
        html_content = html_content.replace("</head>", CSS_CREDITO_RURAL + "</head>")

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

    print("🚀 Iniciando a geração do dashboard 'Early Signals' (v5)...")
    try:
        if not template_arquivo.exists():
            raise FileNotFoundError(f"Template '{template_arquivo.name}' não encontrado em '{script_dir}'")

        # 1) Dados oficiais do BCB primeiro (alimentam os cards E o prompt da IA).
        cards_oficiais_br, contexto_oficial = coletar_dados_oficiais_br()

        # 2) IA com os números oficiais + pesquisa web.
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
