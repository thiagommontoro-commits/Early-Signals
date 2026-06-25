import os
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
    },
    "en": {
        "positive": "Positive", "critical": "Critical", "warning": "Warning",
        "description": "Description", "impacts": "Impacts", "source": "Source",
        "no_analysis": "No analysis available for this country.", "unavailable_title": "Title Unavailable",
        "unavailable_body": "News body unavailable.", "not_informed": "Not informed",
        "product_line_impact": "Impact by Product Line", "analysis_unavailable": "Analysis unavailable.",
        "no_news": "No news available for this country.",
        "months": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    }
}

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

def gerar_bloco_analises(analises_pais):
    """
    Gera o bloco HTML com as análises econômicas para um país específico.
    """
    html_output = '<div class="analysis-grid">\n'

    if not analises_pais:
        return f'<p {i18n_attrs("no_analysis")}>{TRANSLATIONS["pt"]["no_analysis"]}</p>'

    for analise in analises_pais:
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
        
        config_tendencia = mapa_tendencia.get(analise["tendencia"], {"classe": "tendencia-neutra", "icone": "➖"})
        css_class = config_tendencia["classe"]

        html_output += f'''
        <div class="analysis-card {css_class}">
            <div class="analysis-header">
                <span class="analysis-icon">{analise["icone"]}</span>
                <h3 class="analysis-card-title">{analise["titulo"]}</h3>
            </div>
            <div class="analysis-body">
                <p class="analysis-text"><strong {i18n_attrs("description")}>{TRANSLATIONS["pt"]["description"]}:</strong> {analise["descricao"]}</p>
                <p class="analysis-text"><strong {i18n_attrs("impacts")}>{TRANSLATIONS["pt"]["impacts"]}:</strong> {analise["impactos"]}</p>
                <p class="analysis-text source-text"><strong {i18n_attrs("source")}>{TRANSLATIONS["pt"]["source"]}:</strong> {analise["fonte"]}</p>
            </div>
        </div>'''
    
    html_output += '\n</div>'
    return html_output

def gerar_blocos_noticias(noticias_pais):
    """
    Gera o grid HTML com os blocos de notícias e suas análises de impacto.
    """
    if not noticias_pais:
        return f'<div class="news-grid"><p {i18n_attrs("no_news")}>{TRANSLATIONS["pt"]["no_news"]}</p></div>'

    html_output = '<div class="news-grid">\n'
    for noticia in noticias_pais:
        tendencia_noticia = noticia.get('tendencia_noticia', 'incerto')
        farol_class = get_farol_class(tendencia_noticia)
        translation_key = get_farol_translation_key(tendencia_noticia)
        farol_text_attrs = i18n_attrs(translation_key)

        html_output += f'''
        <div class="news-block">
            <div class="news-header">
                <h3 class="news-title">{noticia.get('titulo_noticia', TRANSLATIONS['pt']['unavailable_title'])}</h3>
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
            
            html_output += f'''
                    <div class="m-item">
                        <div class="m-header"><span class="m-name">{produto.capitalize()}</span><span class="farol {produto_farol_class}"><span class="farol-dot"></span><span {produto_farol_text_attrs}>{TRANSLATIONS['pt'][produto_translation_key]}</span></span></div>
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
            print("✅ Arquivo de dados principal updated com o cache do mês.")
            return True
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Erro ao ler o arquivo de cache: {e}. Tentando gerar novos dados.")

    print(f"🚫 Cache para {month:02d}/{year} não encontrado. Conectando à IA para gerar novas análises...")

    fatores_base = {
      "br": [ { "titulo": "Crédito Rural", "icone": "💳" }, { "titulo": "Taxa de Juros (Selic)", "icone": "💰" }, { "titulo": "Câmbio (Dólar)", "icone": "💵" }, { "titulo": "Produção de Grãos", "icone": "🚜" } ],
      "ar": [ { "titulo": "Crédito e Financiamento", "icone": "💳" }, { "titulo": "Inflação e Câmbio", "icone": "📈" }, { "titulo": "Retenciones (Impostos)", "icone": "⚖️" }, { "titulo": "Produção Agrícola", "icone": "🚜" } ],
      "cl": [ { "titulo": "Cenário Hídrico", "icone": "💧" }, { "titulo": "Exportação de Frutas", "icone": "🍒" }, { "titulo": "Custo de Insumos", "icone": "📦" }, { "titulo": "Regulamentação Ambiental", "icone": "🌿" } ],
      "uy": [ { "titulo": "Exportação de Carne", "icone": "🐄" }, { "titulo": "Preço das Commodities", "icone": "📉" }, { "titulo": "Atraso Cambial", "icone": "💵" }, { "titulo": "Produção Florestal", "icone": "🌲" } ],
      "py": [ { "titulo": "Expansão da Fronteira Agrícola", "icone": "🌱" }, { "titulo": "Logística Hidroviária", "icone": "🚢" }, { "titulo": "Produção de Carne", "icone": "🥩" }, { "titulo": "Cenário Fiscal e Cambial", "icone": "🏛️" } ],
      "pe": [ { "titulo": "Agroexportação (Costa)", "icone": "🥑" }, { "titulo": "Agricultura Andina", "icone": "🥔" }, { "titulo": "Projetos de Irrigação", "icone": "🏞️" }, { "titulo": "Instabilidade Política", "icone": "⚖️" } ],
      "bo": [ { "titulo": "Produção de Soja (Oriente)", "icone": "🌱" }, { "titulo": "Escassez de Dólar", "icone": "💸" }, { "titulo": "Biocombustíveis", "icone": "⛽" }, { "titulo": "Infraestrutura Logística", "icone": "🛣️" } ],
      "mx": [ { "titulo": "Agroexportação para EUA", "icone": "🥑" }, { "titulo": "Escassez de Água (Norte)", "icone": "🏜️" }, { "titulo": "Produção de Agave", "icone": "🌵" }, { "titulo": "Remessas e Agricultura Familiar", "icone": "👨‍👩‍👧‍👦" } ]
    }
    
    prompt_json_base_obj = {}
    for pais_code, fatores in fatores_base.items():
        prompt_json_base_obj[pais_code] = {
            "fatores_economicos": [
                {**f, "tendencia": "...", "descricao": "...", "impactos": "...", "fonte": "..."} for f in fatores
            ],
            "noticias": [
                {
                    "titulo_noticia": "...",
                    "tendencia_noticia": "positivo|negativo|incerto",
                    "corpo_noticia": "...",
                    "fonte_noticia": "...",
                    "impacto_produtos": {
                        "tratores": {"tendencia": "positivo|negativo|incerto", "descricao": "..."},
                        "colheitadeiras": {"tendencia": "positivo|negativo|incerto", "descricao": "..."},
                        "pulverizadores": {"tendencia": "positivo|negativo|incerto", "descricao": "..."},
                        "plantadeiras": {"tendencia": "positivo|negativo|incerto", "descricao": "..."}
                    }
                }
            ] * 4
        }
    prompt_json_base = json.dumps(prompt_json_base_obj, indent=2, ensure_ascii=False)
    mes_nome = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"][month - 1]

    prompt = f"""
    Você é um Analista de Inteligência de Mercado Sênior para o setor de máquinas agrícolas na América Latina.
    Sua tarefa é gerar um relatório completo e atualizado para o mês de {mes_nome} de {year}.

    Para cada país, preencha DUAS seções:
    1.  `fatores_economicos`: 4 análises macroeconômicas concisas.
        - "tendencia": 'positivo', 'negativo', 'incerto', 'estavel', 'alta', 'baixa', 'restritiva', 'expansiva'.
        - "descricao": Análise curta (máx 20 palavras).
        - "impactos": Impacto direto no mercado de máquinas (máx 25 palavras).
        - "fonte": Fontes típicas.

    2.  `noticias`: 4 notícias REAIS e RECENTES do agronegócio do país que impactam a demanda por máquinas.
        - "titulo_noticia": Título da notícia (máx 15 palavras).
        - "tendencia_noticia": 'positivo', 'negativo' ou 'incerto'.
        - "corpo_noticia": Resumo da notícia (máx 40 palavras).
        - "fonte_noticia": A fonte da notícia (ex: 'Reuters', 'Globo Rural', 'Canal Rural').
        - "impacto_produtos": Análise de impacto para cada linha de produto.
            - "tendencia": 'positivo', 'negativo' ou 'incerto'.
            - "descricao": Justificativa curta do impacto (máx 20 palavras).

    É crucial que a análise seja baseada em dados e eventos reais do mês corrente.
    Retorne a resposta EXATAMENTE no formato JSON a seguir, preenchendo os "..." com dados reais, sem adicionar nenhum comentário ou formatação extra.

    {prompt_json_base}
    """

    def gerar_dados_erro(mensagem):
        dados_erro = {}
        for pais_code, fatores in fatores_base.items():
            dados_erro[pais_code] = {
                "fatores_economicos": [{**f, "tendencia": "incerto", "descricao": mensagem, "impactos": "Não foi possível carregar os impactos.", "fonte": "Sistema Interno"} for f in fatores],
                "noticias": [{"titulo_noticia": "Falha ao Carregar Notícias", "tendencia_noticia": "incerto", "corpo_noticia": f"Não foi possível carregar as notícias: {mensagem}", "fonte_noticia": "Sistema Interno", "impacto_produtos": {p: {"tendencia": "incerto", "descricao": "Indisponível"} for p in ["tratores", "colheitadeiras", "pulverizadores", "plantadeiras"]}}]
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
        
        now = datetime.datetime.now()
        year = now.year
        month_idx = now.month - 1

        date_pt = f"{TRANSLATIONS['pt']['months'][month_idx]} de {year}"
        date_en = f"{TRANSLATIONS['en']['months'][month_idx]} {year}"

        date_element_html = (
            f'<span id="report-date" '
            f'data-pt="{date_pt}" '
            f'data-en="{date_en}">'
            f'{date_pt}'
            f'</span>'
        )
        html_content = html_content.replace("{{DATA_RELATORIO}}", date_element_html)

        print("📊 Gerando blocos de análise e notícias para cada país...")
        for codigo_pais, dados_pais in dados_completos.items():
            print(f"   -> Gerando para o país: {codigo_pais.upper()}")
            
            # Gerar Fatores Econômicos
            bloco_analises_html = gerar_bloco_analises(dados_pais.get('fatores_economicos', []))
            placeholder_analises = f"{{{{BLOCO_ANALISES_{codigo_pais.upper()}}}}}"
            html_content = html_content.replace(placeholder_analises, bloco_analises_html)

            # Gerar Notícias
            bloco_noticias_html = gerar_blocos_noticias(dados_pais.get('noticias', []))
            placeholder_noticias = f"{{{{BLOCO_NOTICIAS_{codigo_pais.upper()}}}}}"
            html_content = html_content.replace(placeholder_noticias, bloco_noticias_html)

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
    script_dir = Path(__file__).parent
    template_arquivo = script_dir / "dashboard_template.html"
    output_arquivo = script_dir / "index.html"
    dados_arquivo = script_dir / "dados_paises.json"
    
    print("🚀 Iniciando a geração do dashboard 'Early Warning AGCO'...")
    
    try:
        if not template_arquivo.exists():
            raise FileNotFoundError(f"O arquivo de template '{template_arquivo.name}' não foi encontrado no diretório '{script_dir}'")
        
        atualizar_dados_com_ia(dados_arquivo, script_dir)
        gerar_dashboard(template_arquivo, output_arquivo, dados_arquivo)
        print("\n✅ Processo concluído com sucesso!")
    
    except Exception as e:
        print("\n" + "="*60)
        print("❌ OCORREU UM ERRO E O ARQUIVO NÃO FOI GERADO")
        print("="*60)
        print(f"\nCausa do erro: {e}\n")
        print("Por favor, verifique a mensagem acima para entender o problema.")
        print("="*60)
    finally:
        print("\nPressione ENTER para fechar esta janela.")
        input()