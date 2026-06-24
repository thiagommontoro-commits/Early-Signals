import os
import datetime
import json
import requests

def gerar_relatorio():
    data_hoje = datetime.datetime.now().strftime("%d de JUN de 2026 às %H:%M").upper()
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Erro crítico: GEMINI_API_KEY não foi encontrada.")
        raise ValueError("Chave da API ausente.")

    prompt = """
    Você é um analista especialista em inteligência de mercado de maquinário agrícola na América Latina.
    Gere um objeto JSON contendo exatamente 4 notícias recentes e analíticas para CADA UM dos seguintes países: BRASIL, ARGENTINA, CHILE, URUGUAY, PARAGUAY, PERU, BOLIVIA, MEXICO, COLOMBIA.
    
    A estrutura do JSON gerado deve seguir estritamente o formato abaixo:
    {
      "BRASIL": [
        {
          "headline": "MANCHETE EM MAIÚSCULAS", "content": "Análise agro detalhada.", "farol_texto": "Positive", "source": "Fonte confiável",
          "impacts": [
            {"segment": "Tratores (<100cv)", "status": "Positive", "desc": "Curto desc"},
            {"segment": "Tratores (100-200cv)", "status": "Warning", "desc": "Curto desc"},
            {"segment": "Tratores (>200cv)", "status": "Critical", "desc": "Curto desc"},
            {"segment": "Colheitadeiras", "status": "Positive", "desc": "Curto desc"},
            {"segment": "Pulverizadores", "status": "Positive", "desc": "Curto desc"},
            {"segment": "Plantadeiras", "status": "Positive", "desc": "Curto desc"}
          ]
        }
      ],
      "ARGENTINA": [...]
    }
    """

    print("A solicitar processamento ao Gemini via Conexão Direta (REST API)...")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 404:
            print("Modelo Flash não encontrado, acionando modelo PRO de segurança...")
            url_pro = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
            response = requests.post(url_pro, headers=headers, json=payload)
            
        if response.status_code != 200:
            raise Exception(f"Falha na API do Google. Código: {response.status_code}. Detalhe: {response.text}")
            
        dados_api = response.json()
        texto_limpo = dados_api['candidates'][0]['content']['parts'][0]['text'].strip()
        
        if texto_limpo.startswith("```json"):
            texto_limpo = texto_limpo.split("```json")[1].split("```")[0].strip()
        elif texto_limpo.startswith("```"):
            texto_limpo = texto_limpo.split("```")[1].split("```")[0].strip()
            
        dados = json.loads(texto_limpo)
        print("Sucesso! JSON da IA recebido e interpretado.")
        
    except Exception as e:
        print(f"Erro crítico no processamento da IA: {e}")
        raise e

    noticias_html_por_pais = {}
    mapa_chaves = {
        "BRASIL": "BR", "ARGENTINA": "AR", "MEXICO": "MX", "COLOMBIA": "CO", 
        "URUGUAY": "UY", "PERU": "PE", "CHILE": "CL", "BOLIVIA": "BO", "PARAGUAY": "PY"
    }
    
    for nome_ia, sigla in mapa_chaves.items():
        lista_noticias = dados.get(nome_ia, [])
        html_cards = ""
        for item in lista_noticias:
            impacts_html = ""
            for imp in item.get("impacts", []):
                status = imp.get('status', 'Warning')
                cor_css = f"farol-{status.lower()}"
                impacts_html += f"<li><div class='line-title'><strong>{imp.get('segment')}</strong><span class='farol {cor_css}'><span class='farol-dot'></span>{status}</span></div><div class='impact-desc'>{imp.get('desc')}</div></li>"
            
            farol_noticia = item.get('farol_texto', 'Warning')
            html_cards += f"<div class='news-item'><div class='news-header'><h3 class='news-headline'>{item.get('headline')}</h3><span class='farol farol-{farol_noticia.lower()}'><span class='farol-dot'></span>{farol_noticia}</span></div><div class='news-content'>{item.get('content')}</div><div class='impact-box'><div class='impact-title'>⚠️ Impacto Estimado Vendas AGCO</div><ul class='impact-list'>{impacts_html}</ul><a href='#' class='source-link'>Fonte: {item.get('source')}</a></div></div>"
        
        noticias_html_por_pais[sigla] = html_cards

    layout_base = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Early warning AGCO - LATAM Executive Intelligence</title>
    <style>
        :root { --agco-red: #cc0000; --agco-black: #111111; --agco-dark-gray: #333333; --agco-light-gray: #f4f4f4; --text-main: #222222; --white: #ffffff; --farol-positive-bg: #e2f0d9; --farol-positive-text: #385723; --farol-positive-dot: #70ad47; --farol-warning-bg: #fff2cc; --farol-warning-text: #7f6000; --farol-warning-dot: #ffc000; --farol-critical-bg: #fce4d6; --farol-critical-text: #c65911; --farol-critical-dot: #c00000; }
        body { font-family: 'Arial', sans-serif; background-color: #e9ecef; color: var(--text-main); margin: 0; padding: 20px; }
        .container { max-width: 1350px; margin: 0 auto; background-color: var(--white); box-shadow: 0 10px 25px rgba(0,0,0,0.15); border-radius: 4px; overflow: hidden; }
        .header { background-color: var(--agco-black); color: var(--white); padding: 30px 40px; border-bottom: 6px solid var(--agco-red); display: flex; justify-content: space-between; align-items: center; }
        .header-text h1 { margin: 0; font-size: 26px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 900; }
        .header-text p { margin: 5px 0 0 0; font-size: 12px; color: #b0b0b0; text-transform: uppercase; letter-spacing: 0.5px; }
        .date-badge { background-color: var(--agco-red); padding: 8px 16px; font-weight: bold; font-size: 13px; border-radius: 2px; text-transform: uppercase; letter-spacing: 1px; }
        .content-wrapper { padding: 25px 35px; }
        .tabs-nav { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 25px; border-bottom: 3px solid var(--agco-black); padding-bottom: 5px; }
        .tab-btn { background-color: var(--agco-light-gray); color: var(--agco-dark-gray); border: none; padding: 12px 20px; font-size: 13px; font-weight: bold; cursor: pointer; text-transform: uppercase; border-radius: 4px 4px 0 0; }
        .tab-btn:hover { background-color: #e0e0e0; color: var(--agco-black); }
        .tab-btn.active { background-color: var(--agco-black); color: var(--white); border-bottom: 3px solid var(--agco-red); }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .country-title { font-size: 22px; color: var(--agco-black); margin-top: 0; margin-bottom: 25px; padding-bottom: 10px; border-bottom: 2px solid #dddddd; font-weight: 800; text-transform: uppercase; }
        .news-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 25px; }
        .news-item { background-color: var(--white); border: 1px solid #e0e0e0; border-radius: 4px; overflow: hidden; display: flex; flex-direction: column; margin-bottom: 20px; }
        .news-header { background-color: var(--agco-light-gray); padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; border-left: 5px solid var(--agco-black); gap: 15px; }
        .news-headline { font-size: 13px; font-weight: bold; color: var(--agco-black); margin: 0; text-transform: uppercase; line-height: 1.4; }
        .news-content { padding: 18px 20px; font-size: 12.5px; color: var(--agco-dark-gray); line-height: 1.5; text-align: justify; flex-grow: 1; }
        .impact-box { background-color: #fafafa; border-top: 1px solid #e0e0e0; padding: 15px 20px; }
        .impact-title { font-weight: bold; color: var(--agco-black); margin-bottom: 12px; font-size: 11px; text-transform: uppercase; border-bottom: 1px solid #e0e0e0; padding-bottom: 5px; }
        .impact-list { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; list-style: none; padding: 0; margin: 0; }
        .impact-list li { background: var(--white); border: 1px solid #eaeaea; padding: 10px; border-radius: 4px; display: flex; flex-direction: column; gap: 6px; font-size: 12px; }
        .line-title { display: flex; justify-content: space-between; align-items: center; }
        .impact-list strong { font-weight: bold; color: var(--agco-dark-gray); text-transform: uppercase; font-size: 11px; }
        .impact-desc { color: #555; line-height: 1.4; font-size: 11.5px; }
        .farol { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; font-size: 10px; font-weight: bold; border-radius: 4px; text-transform: uppercase; }
        .farol-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        .farol-positive { background-color: var(--farol-positive-bg); color: var(--farol-positive-text); }
        .farol-positive .farol-dot { background-color: var(--farol-positive-dot); }
        .farol-warning { background-color: var(--farol-warning-bg); color: var(--farol-warning-text); }
        .farol-warning .farol-dot { background-color: var(--farol-warning-dot); }
        .farol-critical { background-color: var(--farol-critical-bg); color: var(--farol-critical-text); }
        .farol-critical .farol-dot { background-color: var(--farol-critical-dot); }
        .source-link { display: block; text-align: right; margin-top: 10px; font-size: 11px; color: var(--agco-red); text-decoration: none; font-weight: bold; }
        .footer { background-color: var(--agco-black); color: #777777; text-align: center; padding: 20px; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; border-top: 4px solid var(--agco-red); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-text">
                <h1>Early Warning AGCO</h1>
                <p>LATAM Market Intelligence & Predictive Sales Demand Framework</p>
            </div>
            <div class="date-badge">""" + data_hoje + """</div>
        </div>
        <div class="content-wrapper">
            <div class="tabs-nav">
                <button class="tab-btn active" onclick="switchTab(event, 'br')">🇧🇷 Brasil</button>
                <button class="tab-btn" onclick="switchTab(event, 'ar')">🇦🇷 Argentina</button>
                <button class="tab-btn" onclick="switchTab(event, 'cl')">🇨🇱 Chile</button>
                <button class="tab-btn" onclick="switchTab(event, 'uy')">🇺🇾 Uruguai</button>
                <button class="tab-btn" onclick="switchTab(event, 'py')">🇵🇾 Paraguai</button>
                <button class="tab-btn" onclick="switchTab(event, 'pe')">🇵🇪 Peru</button>
                <button class="tab-btn" onclick="switchTab(event, 'bo')">🇧🇴 Bolívia</button>
                <button class="tab-btn" onclick="switchTab(event, 'mx')">🇲🇽 México</button>
                <button class="tab-btn" onclick="switchTab(event, 'co')">🇨🇴 Colômbia</button>
            </div>
            <div id="br" class="tab-content active"><h2 class="country-title">Brasil</h2><div class="news-grid">""" + noticias_html_por_pais.get('BR', '') + """</div></div>
            <div id="ar" class="tab-content"><h2 class="country-title">Argentina</h2><div class="news-grid">""" + noticias_html_por_pais.get('AR', '') + """</div></div>
            <div id="cl" class="tab-content"><h2 class="country-title">Chile</h2><div class="news-grid">""" + noticias_html_por_pais.get('CL', '') + """</div></div>
            <div id="uy" class="tab-content"><h2 class="country-title">Uruguai</h2><div class="news-grid">""" + noticias_html_por_pais.get('UY', '') + """</div></div>
            <div id="py" class="tab-content"><h2 class="country-title">Paraguai</h2><div class="news-grid">""" + noticias_html_por_pais.get('PY', '') + """</div></div>
            <div id="pe" class="tab-content"><h2 class="country-title">Peru</h2><div class="news-grid">""" + noticias_html_por_pais.get('PE', '') + """</div></div>
            <div id="bo" class="tab-content"><h2 class="country-title">Bolívia</h2><div class="news-grid">""" + noticias_html_por_pais.get('BO', '') + """</div></div>
            <div id="mx" class="tab-content"><h2 class="country-title">México</h2><div class="news-grid">""" + noticias_html_por_pais.get('MX', '') + """</div></div>
            <div id="co" class="tab-content"><h2 class="country-title">Colômbia</h2><div class="news-grid">""" + noticias_html_por_pais.get('CO', '') + """</div></div>
        </div>
        <div class="footer">CONFIDENCIAL — ACESSO RESTRITO — ALINHAMENTO DE GESTÃO EXECUTIVA AGCO LATAM</div>
    </div>
    <script>
        function switchTab(evt, countryId) {
            var tabcontent = document.getElementsByClassName("tab-content");
            for (var i = 0; i < tabcontent.length; i++) { tabcontent[i].style.display = "none"; tabcontent[i].classList.remove("active"); }
            var tablinks = document.getElementsByClassName("tab-btn");
            for (var i = 0; i < tablinks.length; i++) { tablinks[i].classList.remove("active"); }
            document.getElementById(countryId).style.display = "block";
            document.getElementById(countryId).classList.add("active");
            evt.currentTarget.classList.add("active");
        }
    </script>
</body>
</html>"""

    caminho_final = os.path.join(os.getcwd(), "index.html")
    with open(caminho_final, "w", encoding="utf-8") as f:
        f.write(layout_base.strip())
    print(f"Sucesso absoluto! Ficheiro index.html gravado em: {caminho_final}")

if __name__ == "__main__":
    gerar_relatorio()
