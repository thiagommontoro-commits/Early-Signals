import os
import datetime
import json
import urllib.request
from google import genai

# ==========================================
# 1. O SEU MINI BANCO DE DADOS HISTÓRICO
# ==========================================
HISTORICO_MACRO = {
    "MAR/2026": {"selic": "14,75%", "cdi": "14,65%", "juros": "19,30%", "dolar": "R$ 5,02"},
    "APR/2026": {"selic": "14,50%", "cdi": "14,40%", "juros": "19,00%", "dolar": "R$ 5,08"},
    "MAY/2026": {"selic": "14,50%", "cdi": "14,40%", "juros": "19,00%", "dolar": "R$ 5,15"},
}

def calcular_meses_rolantes():
    meses_en = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    today = datetime.datetime.now()
    
    m0_idx = today.month - 1
    m0_year = today.year
    
    m1_idx = m0_idx - 1
    m1_year = m0_year
    if m1_idx < 0:
        m1_idx = 11
        m1_year -= 1
        
    m2_idx = m1_idx - 1
    m2_year = m1_year
    if m2_idx < 0:
        m2_idx = 11
        m2_year -= 1
        
    header_atual = f"{meses_en[m0_idx]}/{m0_year}"
    header_menos1 = f"{meses_en[m1_idx]}/{m1_year}"
    header_menos2 = f"{meses_en[m2_idx]}/{m2_year}"
    
    ano_projecao = str(today.year + 1)
    
    return header_atual, header_menos1, header_menos2, ano_projecao

def buscar_dados_oficiais():
    print("A procurar dados oficiais do Banco Central e do Mercado...")
    try:
        # Busca Câmbio (Dólar Comercial) em tempo real
        req_dolar = urllib.request.urlopen("https://economia.awesomeapi.com.br/last/USD-BRL")
        dados_dolar = json.loads(req_dolar.read())
        dolar_atual = float(dados_dolar["USDBRL"]["bid"])
        
        # Busca Selic Meta atualizada (SGS Banco Central)
        req_selic = urllib.request.urlopen("https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json")
        dados_selic = json.loads(req_selic.read())
        selic_atual = float(dados_selic[0]["valor"])
        
        cdi_atual = selic_atual - 0.10
        juros_agro_atual = selic_atual + 4.50
        
        dolar_str = f"R$ {dolar_atual:.2f}".replace('.', ',')
        selic_str = f"{selic_atual:.2f}%".replace('.', ',')
        cdi_str = f"{cdi_atual:.2f}%".replace('.', ',')
        juros_agro_str = f"{juros_agro_atual:.2f}%".replace('.', ',')
        
        return dolar_str, selic_str, cdi_str, juros_agro_str
        
    except Exception as e:
        print(f"Aviso: Falha ao buscar dados em tempo real. ({e})")
        return "R$ --,--", "--,--%", "--,--%", "--,--%"

def obter_dados_historicos(header):
    if header in HISTORICO_MACRO:
        return HISTORICO_MACRO[header]
    else:
        return {"selic": "--,--%", "cdi": "--,--%", "juros": "--,--%", "dolar": "R$ --,--"}

def gerar_relatorio():
    data_hoje = datetime.datetime.now().strftime("%b %d, %Y").upper()
    m_atual, m_anterior, m_atras, ano_futuro = calcular_meses_rolantes()
    
    dados_m2 = obter_dados_historicos(m_atras)
    dados_m1 = obter_dados_historicos(m_anterior)
    
    dolar_oficial, selic_oficial, cdi_oficial, juros_agro_oficial = buscar_dados_oficiais()

    # ==========================================
    # 2. O PYTHON MONTA A TABELA MACRO DIRETAMENTE
    # ==========================================
    tabela_macro_html = f"""
    <div class="macro-section">
        <h3 class="macro-title">📊 1. MACROECONOMIA & TAXAS DE JUROS <span class="tag-brasil">BRASIL</span></h3>
        <table class="macro-table">
            <thead>
                <tr>
                    <th>INDICADOR</th>
                    <th>CONSOLIDADO 2025</th>
                    <th>{m_atras}</th>
                    <th>{m_anterior}</th>
                    <th>{m_atual} (ATUAL)</th>
                    <th>VAR. MÊS</th>
                    <th>VAR. ANO</th>
                    <th>PROJ. {ano_futuro}</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Taxa Selic (Meta BCB)</td>
                    <td>15,00%</td>
                    <td>{dados_m2['selic']}</td>
                    <td>{dados_m1['selic']}</td>
                    <td>{selic_oficial}</td>
                    <td><span class="macro-badge yellow">● 0,00 PP</span></td>
                    <td><span class="macro-badge green">● -0,50 PP</span></td>
                    <td>13,50%</td>
                </tr>
                <tr>
                    <td>Taxa CDI (a.a.)</td>
                    <td>14,90%</td>
                    <td>{dados_m2['cdi']}</td>
                    <td>{dados_m1['cdi']}</td>
                    <td>{cdi_oficial}</td>
                    <td><span class="macro-badge yellow">● 0,00 PP</span></td>
                    <td><span class="macro-badge green">● -0,50 PP</span></td>
                    <td>13,40%</td>
                </tr>
                <tr>
                    <td>Juros Comerciais Agro</td>
                    <td>19,50%</td>
                    <td>{dados_m2['juros']}</td>
                    <td>{dados_m1['juros']}</td>
                    <td>{juros_agro_oficial}</td>
                    <td><span class="macro-badge yellow">● 0,00 PP</span></td>
                    <td><span class="macro-badge green">● -0,50 PP</span></td>
                    <td>17,80%</td>
                </tr>
                <tr>
                    <td>Câmbio (USD/BRL)</td>
                    <td>R$ 4,85</td>
                    <td>{dados_m2['dolar']}</td>
                    <td>{dados_m1['dolar']}</td>
                    <td>{dolar_oficial}</td>
                    <td><span class="macro-badge red">● Câmbio Real</span></td>
                    <td><span class="macro-badge green">● Monitorado</span></td>
                    <td>R$ 5,25</td>
                </tr>
            </tbody>
        </table>
        <div class="macro-source">*Fonte: API Banco Central do Brasil (SGS/Copom) e AwesomeAPI Câmbio. Processamento e injeção via Python Standard Pipeline.</div>
    </div>
    """

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    # O SEU HTML (FORMA DE BOLO INTOCÁVEL)
    layout_base = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Early warning AGCO</title>
    <style>
        :root {
            --agco-red: #cc0000;
            --agco-black: #111111;
            --agco-dark-gray: #333333;
            --agco-light-gray: #f4f4f4;
            --text-main: #222222;
            --white: #ffffff;
            --farol-verde-bg: #e2f0d9;
            --farol-verde-text: #385723;
            --farol-verde-dot: #70ad47;
            --farol-amarelo-bg: #fff2cc;
            --farol-amarelo-text: #7f6000;
            --farol-amarelo-dot: #ffc000;
            --farol-vermelho-bg: #fce4d6;
            --farol-vermelho-text: #c65911;
            --farol-vermelho-dot: #c00000;
        }
        body { font-family: 'Arial', sans-serif; background-color: #e9ecef; color: var(--text-main); margin: 0; padding: 20px; }
        body > .skiptranslate { display: none; }
        .goog-te-banner-frame.skiptranslate { display: none !important; }
        body { top: 0px !important; }
        .container { max-width: 1200px; margin: 0 auto; background-color: var(--white); box-shadow: 0 10px 25px rgba(0,0,0,0.15); }
        .header { background-color: var(--agco-black); color: var(--white); padding: 35px 40px; border-bottom: 6px solid var(--agco-red); display: flex; justify-content: space-between; align-items: center; background-image: url('https://images.unsplash.com/photo-1592982537447-7440770cbfc9?q=80&w=2000&auto=format&fit=crop'); background-size: cover; background-position: center; background-blend-mode: multiply; }
        .header-text h1 { margin: 0; font-size: 34px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 900; }
        .header-text p { margin: 5px 0 0 0; font-size: 14px; color: #d0d0d0; text-transform: uppercase; letter-spacing: 0.5px; }
        .header-controls { display: flex; flex-direction: column; align-items: flex-end; gap: 10px; }
        .date-badge { background-color: var(--agco-red); padding: 8px 16px; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 2px; text-align: center; width: 100%; box-sizing: border-box;}
        .lang-switcher { display: flex; gap: 5px; }
        .lang-switcher button { background-color: rgba(255, 255, 255, 0.1); color: var(--white); border: 1px solid rgba(255, 255, 255, 0.3); padding: 5px 10px; font-size: 11px; font-weight: bold; cursor: pointer; transition: all 0.2s; text-transform: uppercase; border-radius: 2px; }
        .lang-switcher button:hover { background-color: var(--agco-red); border-color: var(--agco-red); }
        .content-wrapper { padding: 30px 40px; }
        .alert-banner { background-color: var(--agco-light-gray); border-left: 5px solid var(--agco-red); padding: 15px 20px; margin-bottom: 35px; font-size: 13px; color: var(--agco-dark-gray); text-transform: uppercase; letter-spacing: 0.5px; font-weight: bold; }
        .country-section { margin-bottom: 50px; }
        .country-title { font-size: 24px; color: var(--agco-black); margin-top: 0; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #dddddd; display: flex; align-items: center; font-weight: 800; text-transform: uppercase; }
        .highlight-tag { display: inline-block; background-color: var(--agco-black); color: var(--white); padding: 4px 8px; font-size: 11px; margin-left: 15px; vertical-align: middle; letter-spacing: 1px; }
        .news-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 30px; }
        .news-item { background-color: var(--white); border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.02); display: flex; flex-direction: column; }
        .news-header { background-color: var(--agco-light-gray); padding: 15px 20px; border-left: 5px solid var(--agco-black); display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
        .news-headline { font-size: 15px; font-weight: bold; color: var(--agco-black); margin: 0; text-transform: uppercase; line-height: 1.4; }
        .news-content { padding: 20px; font-size: 14px; color: var(--agco-dark-gray); line-height: 1.6; flex-grow: 1; }
        .impact-box { margin: 0 20px 20px 20px; border-top: 3px solid var(--agco-red); background-color: #fafafa; padding: 15px; }
        .impact-title { font-weight: 900; color: var(--agco-red); margin-bottom: 12px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }
        .farol { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }
        .farol-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        .farol-verde { background-color: var(--farol-verde-bg); color: var(--farol-verde-text); }
        .farol-verde .farol-dot { background-color: var(--farol-verde-dot); box-shadow: 0 0 6px var(--farol-verde-dot); }
        .farol-amarelo { background-color: var(--farol-amarelo-bg); color: var(--farol-amarelo-text); }
        .farol-amarelo .farol-dot { background-color: var(--farol-amarelo-dot); box-shadow: 0 0 6px var(--farol-amarelo-dot); }
        .farol-vermelho { background-color: var(--farol-vermelho-bg); color: var(--farol-vermelho-text); }
        .farol-vermelho .farol-dot { background-color: var(--farol-vermelho-dot); box-shadow: 0 0 6px var(--farol-vermelho-dot); }
        .impact-list { list-style: none; padding: 0; margin: 0; font-size: 13px; }
        .impact-list li { margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px dashed #ddd; display: flex; flex-direction: column; gap: 5px; }
        .impact-list li:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        .line-title { display: flex; justify-content: space-between; align-items: center; }
        .impact-list strong { color: var(--agco-black); text-transform: uppercase; }
        .impact-desc { color: #555; font-size: 12.5px; padding-left: 2px; }
        .source-link { display: block; margin-top: 15px; font-size: 11px; color: var(--agco-red); text-decoration: none; font-weight: bold; text-align: right; letter-spacing: 1px; }
        .source-link:hover { color: var(--agco-black); }
        .footer { background-color: var(--agco-black); color: #777777; text-align: center; padding: 25px; font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; }
        
        /* CSS DA TABELA MACRO */
        .macro-section { margin-top: 40px; background-color: var(--white); border: 1px solid #e0e0e0; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
        .macro-title { font-size: 20px; font-weight: 900; text-transform: uppercase; margin-top: 0; margin-bottom: 20px; display: flex; align-items: center; gap: 10px; border-bottom: 2px solid #ddd; padding-bottom: 10px; color: var(--agco-black); }
        .macro-title .tag-brasil { background-color: var(--agco-black); color: var(--white); padding: 4px 8px; font-size: 12px; letter-spacing: 1px; }
        .macro-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: center; }
        .macro-table th { background-color: var(--agco-black); color: var(--white); padding: 12px 10px; font-weight: bold; border-bottom: 4px solid var(--agco-red); text-transform: uppercase; }
        .macro-table td { padding: 12px 10px; border-bottom: 1px solid #eee; color: var(--agco-dark-gray); }
        .macro-table tr:last-child td { border-bottom: none; }
        .macro-table td:first-child { text-align: left; font-weight: bold; color: var(--agco-black); }
        .macro-badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }
        .macro-badge.yellow { background-color: var(--farol-amarelo-bg); color: var(--farol-amarelo-text); }
        .macro-badge.green { background-color: var(--farol-verde-bg); color: var(--farol-verde-text); }
        .macro-badge.red { background-color: var(--farol-vermelho-bg); color: var(--farol-vermelho-text); }
        .macro-source { font-size: 11px; color: #777; margin-top: 15px; font-style: italic; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header" translate="no">
            <div class="header-text">
                <h1>Early warning AGCO</h1>
                <p>LATAM Market Intelligence & Sales Estimation</p>
            </div>
            <div class="header-controls">
                <div class="lang-switcher">
                    <button onclick="changeLanguage('en')">EN</button>
                    <button onclick="changeLanguage('pt')">PT</button>
                    <button onclick="changeLanguage('es')">ES</button>
                </div>
                <div class="date-badge">DATA DE HOJE AQUI</div>
            </div>
        </div>
        <div class="content-wrapper">
            <div class="alert-banner" translate="no">
                // AEM DATA RECEIPT: High-density daily market signals synthesized to mitigate time constraints for detailed product and market analysis.
            </div>
            </div>
        <div class="footer" translate="no">
            CONFIDENTIAL - For Internal Executive Alignment<br>
            Powered by AEM Data Receipt
        </div>
    </div>
</body>
</html>"""

    layout_com_data = layout_base.replace("DATA DE HOJE AQUI", data_hoje)

    instrucoes_iniciais = """
    Você é um analista de mercado e cientista de dados especialista no setor de maquinário agrícola da América Latina.
    Sua tarefa é gerar as notícias do relatório "Early Warning" e encaixá-las EXATAMENTE no código HTML fornecido.
    AQUI ESTÁ O CÓDIGO HTML DO PAINEL:
    """
    
    regras_finais = f"""
    INSTRUÇÕES DE LAYOUT E DENSIDADE:
    - Mantenha a estrutura HTML, CSS e cores originais.
    - REGRA DE RECHEIO: Para cada país analisado (Brasil, Argentina, Chile, Uruguai, Peru, Bolívia, Paraguai), preencha a <div class="news-grid"> contendo OBRIGATORIAMENTE 4 blocos de notícia distintos.
    - MARCADOR DO BRASIL: Dentro do bloco do Brasil, IMEDIATAMENTE após fechar a <div class="news-grid"> das 4 notícias, você DEVE escrever exatamente este texto: INSTRUÇÕES RESTRITAS DE TEMPO E QUALIDADE:
    1. CONTEXTO TEMPORAL: O momento atual é {m_atual}.
    2. PROIBIÇÃO HISTÓRICA: PROIBIDO mencionar dados de safras 23/24 ou anteriores.
    3. REGRA AGRISHOW: A intenção de negócios da Agrishow 2026 fechou em R$ 11,4 bilhões (queda de 22%). 
    
    Retorne EXCLUSIVAMENTE o código HTML completo final para gravação, sem introduções ou explicações.
    """

    prompt_completo = instrucoes_iniciais + "\n\n" + layout_com_data + "\n\n" + reglas_finais

    print("A enviar HTML blindado para o Gemini...")
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_completo,
        )
        
        html_content = response.text
        
        if html_content.startswith("```html"):
            html_content = html_content[7:]
        if html_content.endswith("```"):
            html_content = html_content[:-3]
            
        # ==========================================
        # 3. BLINDAGEM AUTOMÁTICA VIA PYTHON
        # O Python localiza o marcador e injeta a tabela
        # ==========================================
        html_content = html_content.strip()
        if "" in html_content:
            html_final = html_content.replace("", tabela_macro_html)
            print("Sucesso: Tabela injetada via Python Core no marcador da IA.")
        else:
            # Caso a IA esqueça o marcador por falta de espaço, o Python anexa no fim do Brasil
            html_final = html_content.replace("</div>\n\n            <div class=\"country-section\">\n                <h2 class=\"country-title\">🇦🇷 ARGENTINA", tabela_macro_html + "\n\n            <div class=\"country-section\">\n                <h2 class=\"country-title\">🇦🇷 ARGENTINA")
            print("Aviso: Tabela injetada via Fallback de Regex posicional antes da Argentina.")
            
        with open("index.html", "w", encoding="utf-8") as file:
            file.write(html_final)
            
        print("Sucesso Total! Painel atualizado e protegido contra cortes.")

    except Exception as e:
        print(f"Ocorreu um erro ao gerar o painel: {e}")

if __name__ == "__main__":
    gerar_relatorio()
