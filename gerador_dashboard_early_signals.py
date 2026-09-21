# -*- coding: utf-8 -*-
"""
gerador_dashboard_early_signals.py   ←←← SUBSTITUI o arquivo que já existe
==========================================================================
>>> O QUE FAZER COM ESTE ARQUIVO:
    SUBSTITUIR o 'gerador_dashboard_early_signals.py' que já está na raiz do
    seu repositório (apague o conteúdo antigo e cole este por cima).

Mudanças desta versão:
  1. Importa e usa o NOVO 'modulo_juros_rural.py' (2 cards: Juros PF e PJ).
  2. CORREÇÃO DO SELO "vs <mês>": o mês de comparação agora é derivado do
     PRÓPRIO DADO, não do calendário. O BCB publica com defasagem — em
     setembro o dado mais recente pode ser de julho, e nesse caso o selo
     deve dizer "vs Junho" (e não "vs Agosto"). Quando sair agosto, vira
     "vs Julho"; quando sair setembro, "vs Agosto" — automaticamente.
  3. Prompt da IA exige comparação contra o mês anterior e impactos citando
     linhas de máquinas (tratores/colheitadeiras/pulverizadores/plantadeiras).
  4. Aba "Margem do Produtor" permanece REMOVIDA do pipeline.
"""
import os
import re
import sys
import json
from pathlib import Path
import datetime
import traceback
import time

# Suporte ao arquivo .env para carregar a chave automaticamente
from dotenv import load_dotenv
load_dotenv()

try:
    # Atualizado para a nova biblioteca oficial do Google
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors
except ImportError:
    genai = None

# --- Módulos Early Signals (Inadimplência + Juros + Commodities) ---
# NOTA: o módulo de Margem Agrícola foi REMOVIDO do pipeline. Os arquivos
# 'modulo_margem_agricola.py' e 'render_margem_agricola.py' podem ser
# excluídos do repositório (assim como os caches 'cache_margem_*.json').
from modulo_inadimplencia import obter_inadimplencia_rural
from modulo_juros_rural import obter_juros_rural          # <<< NOVO MÓDULO
from modulo_commodities import processar_commodities
from render_commodities import gerar_bloco_commodities, CSS_COMMODITIES
from modulo_credito_rural_deepdive import processar_credito_rural
from render_credito_rural import gerar_bloco_credito_rural, CSS_CREDITO_RURAL

# Dicionário de traduções para os textos do dashboard
# Re-adicionado português para suportar a tradução via Google Translate.
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

# ---------------------------------------------------------------------------
# Resolução do MÊS DE COMPARAÇÃO exibido no selo ("Piorando vs Junho").
#
# Por que isso existe: fontes oficiais (BCB/SGS) publicam com DEFASAGEM. Em
# setembro/2026 o dado mais recente de inadimplência e juros é de JULHO/2026 —
# logo, a comparação correta é contra JUNHO, e não contra agosto (mês do
# calendário). Antes o selo usava sempre o mês anterior do calendário, o que
# gerava o texto errado "vs Agosto" em cards cujo dado era de julho.
#
# A resolução segue esta ordem de prioridade:
#   1) Campo 'mes_comparacao' entregue pelo próprio módulo (juros) — mais confiável.
#   2) Texto "ante <Mês>" / "vs <Mês>" / "frente a <Mês>" dentro da descrição.
#   3) Referência do dado na descrição (ex.: "Jul/2026", "Julho/2026") menos 1 mês.
#   4) Fallback: mês anterior do calendário (usado pelos cards da IA).
# ---------------------------------------------------------------------------
_MESES_PT_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun",
                   "jul", "ago", "set", "out", "nov", "dez"]


def _nomes_mes_por_indice(idx0: int) -> dict:
    """Recebe índice 0-11 e devolve o nome do mês nos 3 idiomas."""
    return {
        "pt": TRANSLATIONS["pt"]["months"][idx0],
        "en": TRANSLATIONS["en"]["months"][idx0],
        "es": TRANSLATIONS["es"]["months"][idx0],
    }


def _resolver_mes_comparacao(analise, mes_anterior_calendario=None):
    """Descobre contra qual mês este card está sendo comparado (ver bloco acima)."""
    # 1) O módulo já informou explicitamente.
    mc = analise.get("mes_comparacao")
    if isinstance(mc, dict) and mc.get("pt"):
        return mc

    descricao = str(analise.get("descricao", ""))

    # 2) A própria descrição diz "ante Junho" / "vs Junho" / "frente a Junho".
    padrao_ante = re.compile(
        r"(?:ante|vs\.?|frente a)\s+(" + "|".join(TRANSLATIONS["pt"]["months"]) + r")",
        re.IGNORECASE)
    m = padrao_ante.search(descricao)
    if m:
        nome = m.group(1).lower()
        for i, mes in enumerate(TRANSLATIONS["pt"]["months"]):
            if mes.lower() == nome:
                return _nomes_mes_por_indice(i)

    # 3) A descrição traz a referência do dado (ex.: "Jul/2026") -> mês anterior a ela.
    padrao_ref = re.compile(r"\b([A-Za-zçÇãÃéÉ]{3,9})\.?/(\d{4})\b")
    m = padrao_ref.search(descricao)
    if m:
        token = m.group(1).lower()[:3]
        if token in _MESES_PT_ABREV:
            idx_ref = _MESES_PT_ABREV.index(token)      # 0-11 do mês do DADO
            return _nomes_mes_por_indice((idx_ref - 1) % 12)  # mês anterior a ele

    # 4) Fallback: mês anterior do calendário (cards gerados pela IA).
    return mes_anterior_calendario


def i18n_attrs(key):
    """Gera atributos de dados para tradução a partir de uma chave."""
    return ' '.join([f'data-{lang}="{translations.get(key, "")}"' for lang, translations in TRANSLATIONS.items()])

def get_farol_class(tendencia):
    """Retorna a classe CSS do farol com base na tendência."""
    mapa = {
        "positivo": "farol-positive",
        "negativo": "farol-critical",
        "incerto": "farol-warning",
        "estavel": "farol-warning",
        "alta": "farol-critical",
        "baixa": "farol-positive",
        "restritiva": "farol-critical",
        "expansiva": "farol-positive",
    }
    return mapa.get(str(tendencia).lower(), "farol-warning")

def get_farol_translation_key(tendencia):
    """Retorna a chave de tradução ('positive', 'critical', 'warning') com base na tendência."""
    tendencia_lower = str(tendencia).lower()
    if tendencia_lower in ["positivo", "baixa", "expansiva"]:
        return "positive"
    if tendencia_lower in ["negativo", "alta", "restritiva"]:
        return "critical"
    return "warning"

def get_direcao_badge(analise, mes_anterior_nome=None):
    """Selo de tendência (direção) do fator, comparado ao mês CORRETO.

    O mês exibido vem do DADO (ver '_resolver_mes_comparacao'), e não do
    calendário — assim um card com dado de Jul/2026 mostra "vs Junho", mesmo
    que o relatório esteja sendo gerado em setembro.
    """
    direcao = str(analise.get("direcao", "estavel")).lower()
    mapa = {
        "melhorando": ("▲", "dir-up",   {"pt": "Melhorando", "en": "Improving", "es": "Mejorando"}),
        "piorando":   ("▼", "dir-down", {"pt": "Piorando",   "en": "Worsening", "es": "Empeorando"}),
    }
    seta, css, rot = mapa.get(direcao, ("▬", "dir-stable", {"pt": "Estável", "en": "Stable", "es": "Estable"}))

    mes_ref = _resolver_mes_comparacao(analise, mes_anterior_nome)

    # Sufixo "vs <mês>" para deixar a base de comparação explícita.
    if mes_ref:
        sufixo = {
            "pt": f' vs {mes_ref["pt"]}',
            "en": f' vs {mes_ref["en"]}',
            "es": f' vs {mes_ref["es"]}',
        }
    else:
        sufixo = {"pt": "", "en": "", "es": ""}

    texto_pt = f'{rot["pt"]}{sufixo["pt"]}'
    texto_en = f'{rot["en"]}{sufixo["en"]}'
    texto_es = f'{rot["es"]}{sufixo["es"]}'

    attrs = f'data-pt="{texto_pt}" data-en="{texto_en}" data-es="{texto_es}"'
    return f'<span class="dir-pill {css}">{seta} <span {attrs}>{texto_pt}</span></span>'

def gerar_bloco_analises(analises_pais, mes_anterior_nome=None):
    """
    Gera o bloco HTML com as análises econômicas para um país específico.
    'mes_anterior_nome' (dict pt/en/es) é apenas o FALLBACK do selo de direção;
    cards com dado oficial defasado usam o mês real do próprio dado.
    """
    html_output = '<div class="analysis-grid">\n'

    if not analises_pais:
        return f'<p {i18n_attrs("no_analysis")}>{TRANSLATIONS["pt"]["no_analysis"]}</p>'

    for analise in analises_pais:
        tendencia = analise.get("tendencia", "incerto")
        mapa_tendencia = {
            "restritiva": {"classe": "tendencia-negativa", "icone": "📉"},
            "alta":       {"classe": "tendencia-negativa", "icone": "📉"},
            "negativo":   {"classe": "tendencia-negativa", "icone": "📉"},
            "incerto":    {"classe": "tendencia-neutra",   "icone": "➖"},
            "estavel":    {"classe": "tendencia-neutra",   "icone": "➖"},
            "expansiva":  {"classe": "tendencia-positiva", "icone": "📈"},
            "baixa":      {"classe": "tendencia-positiva", "icone": "📈"},
            "positivo":   {"classe": "tendencia-positiva", "icone": "📈"},
        }

        config_tendencia = mapa_tendencia.get(tendencia, {"classe": "tendencia-neutra", "icone": "➖"})
        css_class = config_tendencia["classe"]

        # Adicionando a lógica do farol, similar à seção de notícias
        farol_class = get_farol_class(tendencia)
        translation_key = get_farol_translation_key(tendencia)
        farol_text_attrs = i18n_attrs(translation_key)
        farol_html = f'<span class="farol {farol_class}"><span class="farol-dot"></span><span {farol_text_attrs}>{TRANSLATIONS["pt"][translation_key]}</span></span>'
        direcao_html = get_direcao_badge(analise, mes_anterior_nome)

        html_output += f'''
        <div class="analysis-card {css_class}">
            <div class="analysis-header">
                <span class="analysis-icon">{analise["icone"]}</span>
                <h3 class="analysis-card-title">{analise["titulo"]}</h3>
                {farol_html}
            </div>
            <div class="analysis-trend-row">{direcao_html}</div>
            <div class="analysis-body">
                <div>
                    <span class="analysis-label" {i18n_attrs("description")}>{TRANSLATIONS["pt"]["description"]}</span>
                    <p class="analysis-text">{analise["descricao"]}</p>
                </div>
                <div>
                    <span class="analysis-label" {i18n_attrs("impacts")}>{TRANSLATIONS["pt"]["impacts"]}</span>
                    <p class="analysis-text">{analise["impactos"]}</p>
                </div>
                <div>
                    <span class="analysis-label" {i18n_attrs("source")}>{TRANSLATIONS["pt"]["source"]}</span>
                    <p class="analysis-text source-text">{analise["fonte"]}</p>
                </div>
            </div>
        </div>'''

    html_output += '\n</div>'
    return html_output

def gerar_blocos_noticias(noticias_pais, codigo_pais=""):
    """
    Gera o grid HTML com os blocos de notícias e suas análises de impacto.
    """
    if not noticias_pais:
        return f'<div class="news-grid"><p {i18n_attrs("no_news")}>{TRANSLATIONS["pt"]["no_news"]}</p></div>'

    html_output = '<div class="news-grid">\n'

    # Mapeia os temas para ícones para o Brasil. A ordem é importante.
    temas_brasil = [("Soja", "🌱"), ("Milho", "🌽"), ("Café", "☕"), ("Cana", "🎋"), ("Algodão", "🧺"), ("Trigo", "🌾")]

    for i, noticia in enumerate(noticias_pais):
        tendencia_noticia = noticia.get('tendencia_noticia', 'incerto')
        farol_class = get_farol_class(tendencia_noticia)
        translation_key = get_farol_translation_key(tendencia_noticia)
        farol_text_attrs = i18n_attrs(translation_key)

        icon_html = ""
        # Adiciona ícone apenas para o Brasil, baseado na ordem das notícias
        if codigo_pais == 'br' and i < len(temas_brasil):
            tema, icone = temas_brasil[i]
            icon_html = f'<span class="news-topic-icon" title="{tema}">{icone}</span>'

        html_output += f'''
        <div class="news-block">
            <div class="news-header">
                <h3 class="news-title">{icon_html}{noticia.get('titulo_noticia', TRANSLATIONS['pt']['unavailable_title'])}</h3>
                <span class="farol {farol_class}"><span class="farol-dot"></span><span {farol_text_attrs}>{TRANSLATIONS['pt'][translation_key]}</span></span>
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
            tendencia_produto = impacto.get('tendencia', 'incerto')
            produto_farol_class = get_farol_class(tendencia_produto)
            produto_translation_key = get_farol_translation_key(tendencia_produto)
            produto_farol_text_attrs = i18n_attrs(produto_translation_key)

            # Adiciona o segmento impactado (ex: Alta Potência) se ele for retornado pela IA.
            segmento_impactado = impacto.get('segmento_impactado')
            segmento_html = f' <span class="m-segment">({segmento_impactado})</span>' if segmento_impactado and segmento_impactado.strip() else ''

            html_output += f'''
                    <div class="m-item">
                        <div class="m-header"><span class="m-name">{produto.capitalize()}{segmento_html}</span><span class="farol {produto_farol_class}"><span class="farol-dot"></span><span {produto_farol_text_attrs}>{TRANSLATIONS['pt'][produto_translation_key]}</span></span></div>
                        <div class="m-desc">{impacto.get('descricao', TRANSLATIONS['pt']['analysis_unavailable'])}</div>
                    </div>'''

        html_output += '\n                </div>\n            </div>\n        </div>'

    html_output += '\n</div>'
    return html_output

def carregar_dados_paises(caminho_json):
    """Carrega os dados de análise dos países a partir de um arquivo JSON."""
    try:
        print(f"📄 Carregando dados de '{caminho_json.name}'...")
        with open(caminho_json, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        print("✅ Dados carregados com sucesso.")
        return dados
    except FileNotFoundError:
        print(f"❌ ERRO: Arquivo de dados '{caminho_json}' não encontrado.")
        return None
    except json.JSONDecodeError:
        print(f"❌ ERRO: O arquivo '{caminho_json}' não é um JSON válido.")
        return None
    except Exception as e:
        print(f"❌ Um erro inesperado ocorreu ao carregar os dados: {e}")
        return None

def atualizar_dados_com_ia(dados_path, script_dir):
    """
    Verifica se os dados para o mês atual existem em cache.
    Se não, usa a IA para gerar novas análises e as salva em cache e no arquivo principal.
    """
    now = datetime.datetime.now()
    year, month = now.year, now.month
    cache_path = script_dir / f"cache_dados_ia_{year}_{month:02d}.json"

    if cache_path.exists():
        print(f"🧠 Usando análises em cache para {month:02d}/{year} (arquivo: {cache_path.name}).")
        try:
            with open(cache_path, 'r', encoding='utf-8') as f_cache:
                dados_cacheados = json.load(f_cache)
            with open(dados_path, 'w', encoding='utf-8') as f_dados:
                json.dump(dados_cacheados, f_dados, ensure_ascii=False, indent=2)
            print("✅ Arquivo de dados principal atualizado com o cache do mês.")
            return True
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Erro ao ler o arquivo de cache: {e}. Tentando gerar novos dados.")

    print(f"🚫 Cache para {month:02d}/{year} não encontrado. Conectando à IA para gerar novas análises...")

    fatores_base = {
      "br": [ { "titulo": "Crédito Rural", "icone": "💳" }, { "titulo": "Juros (Selic)", "icone": "💰" }, { "titulo": "Câmbio (Dólar)", "icone": "💵" }, { "titulo": "Prod. Grãos", "icone": "🚜" }, { "titulo": "Margens Produtor", "icone": "📊" } ],
      "ar": [ { "titulo": "Crédito/Financ.", "icone": "💳" }, { "titulo": "Inflação/Câmbio", "icone": "📈" }, { "titulo": "Retenciones", "icone": "⚖️" }, { "titulo": "Prod. Agrícola", "icone": "🚜" }, { "titulo": "Margens Produtor", "icone": "📊" } ],
      "cl": [ { "titulo": "Cenário Hídrico", "icone": "💧" }, { "titulo": "Export. Frutas", "icone": "🍒" }, { "titulo": "Custo de Insumos", "icone": "📦" }, { "titulo": "Reg. Ambiental", "icone": "🌿" }, { "titulo": "Margens Produtor", "icone": "📊" } ],
      "uy": [ { "titulo": "Export. Carne", "icone": "🐄" }, { "titulo": "Preço Commod.", "icone": "📉" }, { "titulo": "Atraso Cambial", "icone": "💵" }, { "titulo": "Prod. Florestal", "icone": "🌲" }, { "titulo": "Margens Produtor", "icone": "📊" } ],
      "py": [ { "titulo": "Expansão Agro", "icone": "🌱" }, { "titulo": "Logística Fluvial", "icone": "🚢" }, { "titulo": "Prod. Carne", "icone": "🥩" }, { "titulo": "Fiscal/Câmbio", "icone": "🏛️" }, { "titulo": "Margens Produtor", "icone": "📊" } ],
      "pe": [ { "titulo": "Agroexport (Costa)", "icone": "🥑" }, { "titulo": "Agro Andino", "icone": "🥔" }, { "titulo": "Irrigação", "icone": "🏞️" }, { "titulo": "Cenário Político", "icone": "⚖️" }, { "titulo": "Margens Produtor", "icone": "📊" } ],
      "bo": [ { "titulo": "Soja (Oriente)", "icone": "🌱" }, { "titulo": "Escassez de Dólar", "icone": "💸" }, { "titulo": "Biocombustíveis", "icone": "⛽" }, { "titulo": "Infra. Logística", "icone": "🛣️" }, { "titulo": "Margens Produtor", "icone": "📊" } ],
      "mx": [ { "titulo": "Export. p/ EUA", "icone": "🥑" }, { "titulo": "Escassez Hídrica", "icone": "🏜️" }, { "titulo": "Prod. Agave", "icone": "🌵" }, { "titulo": "Remessas/Agro Fam.", "icone": "👨‍👩‍👧‍👦" }, { "titulo": "Margens Produtor", "icone": "📊" } ]
    }

    prompt_json_base_obj = {}
    for pais_code, fatores in fatores_base.items():
        base_noticia_prompt = {
            "titulo_noticia": "...",
            "tendencia_noticia": "positivo|negativo|incerto",
            "corpo_noticia": "...",
            "fonte_noticia": "...",
            "impacto_produtos": {
                "tratores": {"tendencia": "positivo|negativo|incerto", "descricao": "...", "segmento_impactado": "..."},
                "colheitadeiras": {"tendencia": "positivo|negativo|incerto", "descricao": "...", "segmento_impactado": "..."},
                "pulverizadores": {"tendencia": "positivo|negativo|incerto", "descricao": "...", "segmento_impactado": "..."},
                "plantadeiras": {"tendencia": "positivo|negativo|incerto", "descricao": "...", "segmento_impactado": "..."}
            }
        }

        noticias_prompt = []
        if pais_code == 'br': # Brasil com 6 notícias temáticas
            for tema in ["Soja", "Milho", "Café", "Cana", "Algodão", "Trigo"]:
                noticias_prompt.append({**base_noticia_prompt, "tema_obrigatorio": tema})
        elif pais_code == 'ar': # Argentina com 6 notícias genéricas
            noticias_prompt = [base_noticia_prompt] * 6
        else: # Demais países com 4 notícias
            noticias_prompt = [base_noticia_prompt] * 4

        prompt_json_base_obj[pais_code] = {
            "fatores_economicos": [{**f, "tendencia": "...", "direcao": "melhorando|piorando|estavel", "descricao": "...", "impactos": "...", "fonte": "..."} for f in fatores],
            "noticias": noticias_prompt
        }
    prompt_json_base = json.dumps(prompt_json_base_obj, indent=2, ensure_ascii=False)
    meses_pt = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_nome = meses_pt[month - 1]
    # Mês anterior (base OBRIGATÓRIA de comparação das análises)
    mes_anterior_idx = (month - 2) % 12
    mes_anterior_nome = meses_pt[mes_anterior_idx]
    ano_mes_anterior = year if month > 1 else year - 1

    prompt = f"""
    Você é um Analista de Inteligência de Mercado Sênior para o setor de máquinas agrícolas na América Latina.
    Sua tarefa é gerar um relatório completo e atualizado para o mês de {mes_nome} de {year}.

    ############################################################
    # REGRA MAIS IMPORTANTE — BASE DE COMPARAÇÃO MÊS A MÊS
    ############################################################
    TODA análise de `fatores_economicos` DEVE ser feita comparando a situação
    de {mes_nome}/{year} com a de {mes_anterior_nome}/{ano_mes_anterior} (o MÊS ANTERIOR).
    NÃO compare com o ano anterior, com a safra passada, nem com uma média histórica.
    A pergunta que você responde em cada fator é SEMPRE:
        "Este fator está MELHOR ou PIOR do que estava em {mes_anterior_nome}/{ano_mes_anterior}?"

    Isso vale para todos os fatores: crédito, juros, câmbio, produção, margens etc.
    Exemplo correto para "Margens Produtor": "Margens de soja recuaram ante
    {mes_anterior_nome}, com alta de fertilizantes; café segue melhor que em {mes_anterior_nome}."
    Exemplo ERRADO (não faça): "Margens seguem comprimidas no ano" (sem base de comparação mensal).

    IMPORTANTE SOBRE DEFASAGEM DE DADOS: se para algum fator o dado oficial mais
    recente disponível for anterior a {mes_nome} (ex.: a estatística só existe até
    julho), então compare os DOIS ÚLTIMOS MESES REALMENTE DISPONÍVEIS e diga na
    descrição a que mês o número se refere (ex.: "Jul/{year}: X% ante Junho").
    NUNCA afirme uma comparação com um mês cujo dado ainda não foi publicado.

    Para cada país, preencha DUAS seções:
    1.  `fatores_economicos`: análises macroeconômicas concisas para os fatores listados.
        - "tendencia": 'positivo', 'negativo', 'incerto', 'estavel', 'alta', 'baixa', 'restritiva', 'expansiva'.
          (Representa o ESTADO ATUAL do fator em {mes_nome}/{year}.)
        - "direcao": Movimento do fator COMPARADO AO MÊS ANTERIOR.
          Use APENAS um destes valores: 'melhorando', 'piorando' ou 'estavel'.
          ATENÇÃO: 'melhorando'/'piorando' devem ser julgados do ponto de vista da
          DEMANDA POR MÁQUINAS AGRÍCOLAS (ex.: juros caindo vs mês anterior =
          'melhorando'; inadimplência subindo vs mês anterior = 'piorando').
          Este campo NÃO é projeção futura — é a variação observada contra o mês anterior.
        - "descricao": Análise curta (máx 25 palavras) que DEVE explicitar a comparação
          mensal (use expressões como "ante {mes_anterior_nome}", "vs {mes_anterior_nome}",
          "frente a {mes_anterior_nome}"), citando o número/percentual quando houver
          (ex.: "Selic estável em 15% ante {mes_anterior_nome}").
        - "impactos": **IMPACTO DIRETO E CONCRETO NO MERCADO DE MÁQUINAS AGRÍCOLAS** (máx 30 palavras).
          OBRIGATÓRIO: cite explicitamente qual(is) linha(s) de produto é(são) afetada(s)
          — tratores, colheitadeiras, pulverizadores ou plantadeiras — e, quando possível,
          o segmento (ex.: "Alta Potência >170cv", "Classes 7+", "autopropelidos").
          Diga se a demanda/decisão de compra tende a ACELERAR, ADIAR ou ficar NEUTRA
          em relação ao mês anterior.
          Exemplo bom: "Crédito mais caro que em {mes_anterior_nome} adia compra de
          colheitadeiras Classes 7+ e tratores alta potência; retrofit ganha espaço."
          Exemplo ruim (NÃO faça): "Impacto negativo no agronegócio."
        - "fonte": Fontes típicas (ex.: 'BCB/SGS', 'CONAB', 'CEPEA', 'IBGE').
        - **REGRA ESPECIAL PARA "Margens Produtor"**: Na descrição, especifique quais culturas
          tiveram margem melhor e quais piorou EM RELAÇÃO A {mes_anterior_nome}.
          Ex: "Ante {mes_anterior_nome}, margens de soja e milho comprimiram; café e cana melhoraram."
    2.  `noticias`: Um número variável de notícias REAIS e RECENTES do agronegócio do país que impactam a demanda por máquinas (6 para Brasil e Argentina, 4 para os demais).
        - **REGRA ESPECIAL PARA O BRASIL**: Para o Brasil (`br`), você DEVE retornar uma notícia para cada um dos `tema_obrigatorio` especificados no JSON (`Soja`, `Milho`, `Café`, `Cana`, `Algodão`, `Trigo`). Para os outros países, as notícias podem ser sobre quaisquer temas relevantes.
        - "titulo_noticia": Título da notícia (máx 15 palavras).
        - "tendencia_noticia": 'positivo', 'negativo' ou 'incerto'.
        - "corpo_noticia": Resumo da notícia (máx 40 palavras). Priorize fatos ocorridos
          entre {mes_anterior_nome}/{ano_mes_anterior} e {mes_nome}/{year}.
        - "fonte_noticia": A fonte da notícia (ex: 'Reuters', 'Globo Rural', 'Canal Rural').
        - "impacto_produtos": Análise de impacto para cada linha de produto.
            - "tendencia": 'positivo', 'negativo' ou 'incerto'.
            - "descricao": Justificativa curta do impacto na DEMANDA POR MÁQUINAS (máx 20 palavras),
              deixando claro se acelera, adia ou mantém a decisão de compra.
            - "segmento_impactado": Especifique o sub-segmento principal afetado.
                - Para 'tratores': Use 'Baixa Potência (<80cv)', 'Média Potência (80-170cv)' ou 'Alta Potência (>170cv)'.
                - Para 'plantadeiras': Use 'Pequeno Porte (<20 linhas)' ou 'Grande Porte (>20 linhas)'.
                - Para 'colheitadeiras': Use 'Médio Porte (Classes 4-6)' ou 'Grande Porte (Classes 7+)'.
                - Para 'pulverizadores': Use 'De Arrasto' ou 'Autopropelido'.
                - Se o impacto for geral ou não específico, retorne uma string vazia "".
    É crucial que a análise seja baseada em dados e eventos reais do mês corrente.
    Retorne a resposta EXATAMENTE no formato JSON a seguir, preenchendo os "..." com dados reais, sem adicionar nenhum comentário ou formatação extra. O campo `tema_obrigatorio` é apenas uma instrução para você e não deve ser incluído na resposta JSON final. O campo `segmento_impactado` é obrigatório.

    {prompt_json_base}
    """

    def gerar_dados_erro(mensagem):
        dados_erro = {}
        for pais_code, fatores in fatores_base.items():
            dados_erro[pais_code] = {
                "fatores_economicos": [{**f, "tendencia": "incerto", "descricao": mensagem, "impactos": "Não foi possível carregar os impactos.", "fonte": "Sistema Interno"} for f in fatores],
            "noticias": [{"titulo_noticia": "Falha ao Carregar Notícias", "tendencia_noticia": "incerto", "corpo_noticia": f"Não foi possível carregar as notícias: {mensagem}", "fonte_noticia": "Sistema Interno", "impacto_produtos": {p: {"tendencia": "incerto", "descricao": "Indisponível", "segmento_impactado": ""} for p in ["tratores", "colheitadeiras", "pulverizadores", "plantadeiras"]}}]
            }
        return dados_erro

    if not genai:
        msg = "Biblioteca 'google-genai' não instalada de forma correta."
        print(f"❌ ERRO: {msg}")
        dados_fallback = gerar_dados_erro(msg)
        with open(dados_path, 'w', encoding='utf-8') as f: json.dump(dados_fallback, f, ensure_ascii=False, indent=2)
        return False

    if not os.environ.get("GEMINI_API_KEY"):
        msg = "Chave de API 'GEMINI_API_KEY' não localizada no sistema."
        print(f"❌ ERRO: {msg}")
        dados_fallback = gerar_dados_erro(msg)
        with open(dados_path, 'w', encoding='utf-8') as f: json.dump(dados_fallback, f, ensure_ascii=False, indent=2)
        return False

    # Constante para o modelo de IA. Não alterar, pois o prompt foi otimizado para este modelo específico.
    MODELO_IA = 'gemini-2.5-flash'

    max_retries = 3
    initial_backoff = 5
    novos_dados = None

    try:
        # Configuração atualizada com o Client moderno da biblioteca genai
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

        for attempt in range(max_retries):
            try:
                print(f"🤖 Tentativa {attempt + 1}/{max_retries} de contatar a IA...")
                print(f"   📅 Base de comparação das análises: {mes_nome}/{year} vs {mes_anterior_nome}/{ano_mes_anterior}")
                response = client.models.generate_content(
                    model=MODELO_IA,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                novos_dados = json.loads(response.text.strip())
                print("✅ IA respondeu com sucesso!")
                break
            except Exception as e:
                # Se for erro de tráfego/indisponibilidade (503/Unavailable), aplica backoff progressivo
                if ("503" in str(e) or "UNAVAILABLE" in str(e)) and attempt < max_retries - 1:
                    wait_time = initial_backoff * (2 ** attempt)
                    print(f"⚠️ Servidor da IA está ocupado (503). Tentando novamente em {wait_time} segundos...")
                    time.sleep(wait_time)
                else:
                    raise

        if novos_dados is None:
            raise Exception("Todas as tentativas de comunicação com o servidor da IA falharam.")

        if "br" not in novos_dados or "ar" not in novos_dados:
            raise ValueError("A resposta estruturada do JSON não retornou a árvore de países esperada.")

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(novos_dados, f, ensure_ascii=False, indent=2)
        print(f"✅ Análises da IA salvas no cache: {cache_path.name}")

        with open(dados_path, 'w', encoding='utf-8') as f:
            json.dump(novos_dados, f, ensure_ascii=False, indent=2)
        print(f"✅ Arquivo de dados principal '{dados_path.name}' atualizado com sucesso pela IA.")

        return True

    except Exception as e:
        print(f"❌ ERRO FATAL ao contatar a IA: {e}")
        traceback.print_exc()
        dados_fallback = gerar_dados_erro(f"Falha na comunicação com a IA: {e}")
        with open(dados_path, 'w', encoding='utf-8') as f:
            json.dump(dados_fallback, f, ensure_ascii=False, indent=2)
        return False

def gerar_dashboard(template_path, output_path, dados_path):
    try:
        print(f"📄 Lendo template de '{template_path.name}'...")
        html_content = template_path.read_text(encoding="utf-8")

        dados_completos = carregar_dados_paises(dados_path)
        if not dados_completos:
            raise ValueError("Não foi possível carregar os dados dos países do arquivo JSON.")

        # ---- MÓDULO A: INADIMPLÊNCIA DO CRÉDITO RURAL (BR) ----
        # Cards com dado OFICIAL do BCB são inseridos no INÍCIO dos fatores
        # econômicos do Brasil, antes dos cards gerados pela IA.
        print("Buscando Inadimplencia do Credito Rural (BCB SGS 21148)...")
        item_inad = obter_inadimplencia_rural()
        if item_inad and "br" in dados_completos:
            dados_completos["br"].setdefault("fatores_economicos", [])
            dados_completos["br"]["fatores_economicos"].insert(0, item_inad)

        # ---- MÓDULO A2: JUROS DO CRÉDITO RURAL PF e PJ (BR) ----  <<< NOVO
        # Mesma fonte da inadimplência (BCB/SGS): séries 20771 (PF) e 20760 (PJ).
        # Retorna uma LISTA (0 a 2 cards); séries indisponíveis são omitidas.
        if "br" in dados_completos:
            cards_juros = obter_juros_rural()
            if cards_juros:
                dados_completos["br"].setdefault("fatores_economicos", [])
                # Inseridos logo após a inadimplência, mantendo a ordem PF -> PJ.
                pos = 1 if item_inad else 0
                for i, card in enumerate(cards_juros):
                    dados_completos["br"]["fatores_economicos"].insert(pos + i, card)
                print(f"   ✅ {len(cards_juros)} card(s) de juros inserido(s) nos fatores do Brasil.")

        now = datetime.datetime.now()
        year = now.year
        month_idx = now.month - 1

        # Mês anterior do CALENDÁRIO — usado apenas como FALLBACK do selo de
        # direção (cards da IA). Cards com dado oficial defasado (BCB) usam o
        # mês real do próprio dado, resolvido em '_resolver_mes_comparacao'.
        mes_anterior_idx = (now.month - 2) % 12
        mes_anterior_nome = _nomes_mes_por_indice(mes_anterior_idx)
        print(f"📅 Comparação padrão (cards da IA): "
              f"{TRANSLATIONS['pt']['months'][month_idx]} vs {mes_anterior_nome['pt']}")
        print("   ℹ Cards com dado oficial defasado (BCB) usam automaticamente o "
              "mês real do dado (ex.: dado de Jul → selo 'vs Junho').")

        # Preenche os placeholders de data com as versões em português, inglês e espanhol.
        html_content = html_content.replace("{{DATA_RELATORIO_PT}}", f"{TRANSLATIONS['pt']['months'][month_idx]} de {year}")
        html_content = html_content.replace("{{DATA_RELATORIO_EN}}", f"{TRANSLATIONS['en']['months'][month_idx]} {year}")
        html_content = html_content.replace("{{DATA_RELATORIO_ES}}", f"{TRANSLATIONS['es']['months'][month_idx]} de {year}")

        print("📊 Gerando blocos de análise e notícias para cada país...")
        for codigo_pais, dados_pais in dados_completos.items():
            print(f"   -> Gerando para o país: {codigo_pais.upper()}")

            # Gerar Fatores Econômicos (selo de direção com o mês CORRETO)
            bloco_analises_html = gerar_bloco_analises(
                dados_pais.get('fatores_economicos', []), mes_anterior_nome)
            placeholder_analises = f"{{{{BLOCO_ANALISES_{codigo_pais.upper()}}}}}"
            html_content = html_content.replace(placeholder_analises, bloco_analises_html)

            # Gerar Notícias
            bloco_noticias_html = gerar_blocos_noticias(dados_pais.get('noticias', []), codigo_pais)
            placeholder_noticias = f"{{{{BLOCO_NOTICIAS_{codigo_pais.upper()}}}}}"
            html_content = html_content.replace(placeholder_noticias, bloco_noticias_html)

        # ---- MÓDULO B: COMMODITY INTELLIGENCE ----
        print("Processando Commodity Intelligence...")
        xlsx_commodities = template_path.parent / "data" / "precos_agricolas_latest.xlsx"
        commodities, aviso_frescor = processar_commodities(xlsx_commodities)
        bloco_commodities_html = gerar_bloco_commodities(commodities, aviso_frescor)
        html_content = html_content.replace("{{BLOCO_COMMODITIES}}", bloco_commodities_html)

        # ---- MÓDULO C: CRÉDITO RURAL DEEP DIVE (Brasil) ----
        print("Processando Crédito Rural Deep Dive...")
        dados_credito = processar_credito_rural()
        bloco_credito_html = gerar_bloco_credito_rural(dados_credito)
        html_content = html_content.replace("{{BLOCO_CREDITO_RURAL}}", bloco_credito_html)
        html_content = html_content.replace("</head>", CSS_CREDITO_RURAL + "</head>")

        # ---- MÓDULO D (REMOVIDO): MARGEM & CUSTO AGRÍCOLA (CONAB) ----
        # A aba "Margem do Produtor" foi retirada do Early Signals.

        # Injeta o botão de feedback e o modal do formulário
        feedback_modal_html = f"""
<style>
    .feedback-button {{
        position: fixed; bottom: 25px; right: 25px; background-color: #CC0000; color: white;
        padding: 12px 18px; border-radius: 50px; text-decoration: none; font-family: 'Roboto', sans-serif;
        font-size: 15px; font-weight: 500; box-shadow: 0 5px 15px rgba(0,0,0,0.25); z-index: 1000;
        display: flex; align-items: center; gap: 10px; cursor: pointer;
        transition: transform 0.2s ease-in-out, background-color 0.3s;
    }}
    .feedback-button:hover {{ background-color: #A30000; transform: translateY(-3px); }}
    .feedback-button svg {{ width: 20px; height: 20px; }}

    .modal-overlay {{
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0, 0, 0, 0.6); z-index: 2000;
        display: none; align-items: center; justify-content: center;
    }}
    .modal-content {{
        background: #fff; padding: 30px; border-radius: 12px;
        width: 90%; max-width: 550px; box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        position: relative; animation: slide-down 0.4s ease-out;
    }}
    @keyframes slide-down {{ from {{ transform: translateY(-30px); opacity: 0; }} to {{ transform: translateY(0); opacity: 1; }} }}

    .modal-close {{
        position: absolute; top: 15px; right: 15px; background: none; border: none;
        font-size: 24px; color: #888; cursor: pointer; line-height: 1;
    }}
    .modal-close:hover {{ color: #333; }}

    .modal-title {{ margin-top: 0; font-size: 22px; color: #333; }}
    .form-group {{ margin-bottom: 20px; }}
    .form-group label {{ display: block; margin-bottom: 8px; font-weight: 500; color: #555; }}
    .form-group input, .form-group textarea {{
        width: 100%; padding: 10px; border: 1px solid #ccc;
        border-radius: 6px; font-family: 'Roboto', sans-serif; font-size: 15px;
    }}
    .form-group textarea {{ resize: vertical; min-height: 100px; }}
    .submit-btn {{
        background-color: #CC0000; color: white; border: none; padding: 12px 25px;
        border-radius: 6px; font-size: 16px; font-weight: 500; cursor: pointer;
        width: 100%; transition: background-color 0.3s;
    }}
    .submit-btn:hover {{ background-color: #A30000; }}
    .formspree-thanks {{ display: none; text-align: center; padding: 20px; }}
</style>

<!-- Botão Flutuante -->
<button id="openFeedbackModal" class="feedback-button">
    <svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 16 16">
      <path d="M2 6a6 6 0 1 1 10.174 4.31c-.203.196-.359.4-.453.619l-.762 1.769A.5.5 0 0 1 10.5 13h-5a.5.5 0 0 1-.46-.302l-.761-1.77a1.964 1.964 0 0 0-.453-.618A6 6 0 0 1 2 6zm6 8.5a.5.5 0 0 0 .5.5h.5a.5.5 0 0 0 0-1h-.5a.5.5 0 0 0-.5.5zM8 1a5 5 0 0 0-3.536 8.536L5.136 11.5h5.728l.672-1.964A5 5 0 0 0 8 1z"/>
    </svg>
    <span {i18n_attrs("suggest_improvement")}>{TRANSLATIONS["pt"]["suggest_improvement"]}</span>
</button>

<!-- Modal do Formulário -->
<div id="feedbackModal" class="modal-overlay">
    <div class="modal-content">
        <button id="closeFeedbackModal" class="modal-close">&times;</button>
        <h2 class="modal-title">Feedback sobre o Dashboard</h2>
        <form id="feedbackForm" action="https://formspree.io/f/mvzjaqow" method="POST">
            <div class="form-group">
                <label for="satisfaction">Em uma escala de 1 a 5, quão útil é este dashboard para você?</label>
                <input type="number" name="satisfaction" min="1" max="5" required style="width: 80px;">
            </div>
            <div class="form-group">
                <label for="suggestion">Deixe sua sugestão de melhoria ou novo indicador aqui:</label>
                <textarea id="suggestion" name="suggestion" required></textarea>
            </div>
            <div class="form-group">
                <label for="email">Seu e-mail (opcional, para entrarmos em contato)</label>
                <input type="email" id="email" name="email">
            </div>
            <button type="submit" class="submit-btn">Enviar Feedback</button>
        </form>
        <div id="formspreeThanks" class="formspree-thanks">
            <h3>Obrigado pelo seu feedback!</h3>
            <p>Sua sugestão foi enviada com sucesso.</p>
        </div>
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
    modal.addEventListener('click', (e) => {{
        if (e.target === modal) {{ modal.style.display = 'none'; }}
    }});

    form.addEventListener('submit', async (e) => {{
        e.preventDefault();
        const data = new FormData(form);
        try {{
            const response = await fetch(form.action, {{
                method: 'POST',
                body: data,
                headers: {{ 'Accept': 'application/json' }}
            }});
            if (response.ok) {{
                form.style.display = 'none';
                thanksMessage.style.display = 'block';
                setTimeout(() => {{
                    modal.style.display = 'none';
                    form.style.display = 'block';
                    thanksMessage.style.display = 'none';
                    form.reset();
                }}, 3000);
            }} else {{
                alert('Ocorreu um erro ao enviar o formulário. Tente novamente.');
            }}
        }} catch (error) {{
            alert('Ocorreu um erro de conexão. Verifique sua internet e tente novamente.');
        }}
    }});
</script>
"""
        html_content = html_content.replace("</body>", feedback_modal_html + "</body>")

        output_path.write_text(html_content, encoding="utf-8")
        print(f"✅ Dashboard '{output_path.name}' gerado com sucesso com dados de múltiplos países!")

    except FileNotFoundError:
        print(f"❌ ERRO: Arquivo de template não encontrado em '{template_path}'")
        raise
    except Exception as e:
        print(f"❌ Um erro inesperado ocorreu durante a geração do dashboard: {e}")
        traceback.print_exc()
        raise

if __name__ == "__main__":
    script_dir = Path(__file__).resolve().parent
    template_arquivo = script_dir / "dashboard_template.html"
    output_arquivo = script_dir / "index.html"
    dados_arquivo = script_dir / "dados_paises.json"

    print("🚀 Iniciando a geração do dashboard 'Early Signals'...")
    print(f"📁 Diretório do projeto: {script_dir}")
    print(f"📄 Template: {template_arquivo}")
    print(f"🌐 Saída esperada: {output_arquivo}")

    try:
        if not template_arquivo.exists():
            raise FileNotFoundError(
                f"O arquivo de template '{template_arquivo.name}' não foi encontrado no diretório '{script_dir}'"
            )

        atualizar_dados_com_ia(dados_arquivo, script_dir)
        gerar_dashboard(template_arquivo, output_arquivo, dados_arquivo)

        # Validação final: garante que o index.html foi realmente gerado e não está vazio.
        if not output_arquivo.exists():
            raise RuntimeError("O processo terminou, mas o arquivo index.html não foi criado.")

        tamanho_index = output_arquivo.stat().st_size
        if tamanho_index == 0:
            raise RuntimeError("O arquivo index.html foi criado, mas está vazio.")

        print(f"✅ index.html validado: {tamanho_index:,} bytes")
        print("\n✅ Processo concluído com sucesso!")

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ OCORREU UM ERRO E O ARQUIVO NÃO FOI GERADO")
        print("=" * 60)
        print(f"\nCausa do erro: {e}\n")
        traceback.print_exc()
        print("Por favor, verifique a mensagem acima para entender o problema.")
        print("=" * 60)

        # CRÍTICO: encerra com código de erro para que o GitHub Actions falhe (fique vermelho)
        # em vez de fazer um deploy "verde" com o index.html antigo.
        sys.exit(1)
