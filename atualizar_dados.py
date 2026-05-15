import os
from datetime import datetime
from google import genai

# 1. Configura a nova IA
CHAVE_API = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=CHAVE_API)

# 2. O Prompt Executivo
prompt = """
Atue como um analista sênior de inteligência de mercado focado em maquinário agrícola para a América Latina.
Gere um relatório denso com as principais notícias agrícolas oficiais de hoje. 

REGRAS OBRIGATÓRIAS:
1. FOCO: Soja, Milho, Cana-de-açúcar, Algodão, Café, Pecuária e Laranja.
2. VOLUME: 3 a 4 notícias separadas e aprofundadas para CADA UM dos seguintes países/blocos: Brasil, Argentina, México, Colômbia, Cone Sul & Pacífico (Uruguai, Paraguai, Peru e Chile).
3. IDIOMA: Inglês corporativo.

Retorne APENAS código HTML puro, sem blocos markdown.
Para CADA país/bloco, crie exatamente esta estrutura:

<div class="country-section">
    <h2 class="country-title">[BANDEIRA E NOME DO PAÍS/BLOCO] <span class="highlight-tag">MULTI-CROP ALERTS</span></h2>
    <div class="news-grid">
        <div class="news-item">
            <div class="news-header"><h3 class="news-headline">[CULTURA] - [TÍTULO DA NOTÍCIA EM MAIÚSCULO]</h3></div>
            <div class="news-content">[Resumo executivo de 3 linhas sobre o impacto no mercado daquela commodity específica]</div>
            <div class="impact-box">
                <div class="impact-title">⚙️ Machinery Impact</div>
                <ul class="impact-list">
                    <li><strong>Tractors:</strong> [Impact on Small <100HP, Medium 100-200HP, High >200HP]</li>
                    <li><strong>Harvesters:</strong> [Specific impact on replacement cycles or tech adoption]</li>
                    <li><strong>Sprayers:</strong> [Specific impact on application needs]</li>
                    <li><strong>Planters:</strong> [Specific impact on planting windows or precision tech]</li>
                </ul>
                <a href="[LINK REAL DA FONTE OFICIAL]" class="source-link">[NOME DA FONTE] ➔</a>
            </div>
        </div>
    </div>
</div>
"""

print("Consultando o mercado com a nova API Gemini 2.5 Flash...")
resposta = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=prompt
)
noticias_html = resposta.text.replace("```html", "").replace("```", "")

# 3. Pega a data de hoje
data_hoje = datetime.now().strftime("%b %d, %Y").upper()

# 4. Reconstrói o arquivo HTML inteiro do zero (Design + Notícias)
html_completo = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Early warning AGCO</title>
    <style>
        :root {{
            --agco-red: #cc0000;
            --agco-black: #111111;
            --agco-dark-gray: #333333;
            --agco-light-gray: #f4f4f4;
            --text-main: #222222;
            --white: #ffffff;
        }}
        body {{ font-family: 'Arial', sans-serif; background-color: #e9ecef; color: var(--text-main); margin: 0; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: var(--white); box-shadow: 0 10px 25px rgba(0,0,0,0.15); }}
        .header {{ background-color: var(--agco-black); color: var(--white); padding: 35px 40px; border-bottom: 6px solid var(--agco-red); display: flex; justify-content: space-between; align-items: center; background-image: url('https://images.unsplash.com/photo-1592982537447-7440770cbfc9?q=80&w=2000&auto=format&fit=crop'); background-size: cover; background-position: center; background-blend-mode: multiply; }}
        .header-text h1 {{ margin: 0; font-size: 34px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 900; }}
        .header-text p {{ margin: 5px 0 0 0; font-size: 14px; color: #d0d0d0; text-transform: uppercase; letter-spacing: 0.5px; }}
        .date-badge {{ background-color: var(--agco-red); padding: 10px 20px; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 2px; }}
        .content-wrapper {{ padding: 30px 40px; }}
        .alert-banner {{ background-color: var(--agco-light-gray); border-left: 5px solid var(--agco-red); padding: 15px 20px; margin-bottom: 35px; font-size: 13px; color: var(--agco-dark-gray); text-transform: uppercase; letter-spacing: 0.5px; font-weight: bold; }}
        .country-section {{ margin-bottom: 50px; }}
        .country-title {{ font-size: 24px; color: var(--agco-black); margin-top: 0; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #dddddd; display: flex; align-items: center; font-weight: 800; text-transform: uppercase; }}
        .highlight-tag {{ display: inline-block; background-color: var(--agco-black); color: var(--white); padding: 4px 8px; font-size: 11px; margin-left: 15px; vertical-align: middle; letter-spacing: 1px; }}
        .news-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 30px; }}
        .news-item {{ background-color: var(--white); border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.02); display: flex; flex-direction: column; }}
        .news-header {{ background-color: var(--agco-light-gray); padding: 15px 20px; border-left: 5px solid var(--agco-black); }}
        .news-headline {{ font-size: 16px; font-weight: bold; color: var(--agco-black); margin: 0; text-transform: uppercase; }}
        .news-content {{ padding: 20px; font-size: 14px; color: var(--agco-dark-gray); line-height: 1.6; flex-grow: 1; }}
        .impact-box {{ margin: 0 20px 20px 20px; border-top: 3px solid var(--agco-red); background-color: #fafafa; padding: 15px; }}
        .impact-title {{ font-weight: 900; color: var(--agco-red); margin-bottom: 10px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .impact-list {{ list-style: none; padding: 0; margin: 0; font-size: 13px; }}
        .impact-list li {{ margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px dashed #ddd; }}
        .impact-list li:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
        .impact-list strong {{ color: var(--agco-black); text-transform: uppercase; }}
        .source-link {{ display: block; margin-top: 15px; font-size: 11px; color: var(--agco-red); text-decoration: none; font-weight: bold; text-align: right; letter-spacing: 1px; }}
        .source-link:hover {{ color: var(--agco-black); }}
        .footer {{ background-color: var(--agco-black); color: #777777; text-align: center; padding: 25px; font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-text">
                <h1>Early warning AGCO</h1>
                <p>LATAM Market Intelligence & Sales Estimation</p>
            </div>
            <div class="date-badge">{data_hoje}</div>
        </div>

        <div class="content-wrapper">
            <div class="alert-banner">
                // EXECUTIVE ALIGNMENT: High-density daily market signals synthesized to mitigate time constraints for detailed product and market analysis.
            </div>

            {noticias_html}

        </div>

        <div class="footer">
            CONFIDENTIAL - For Internal Executive Alignment<br>
            Powered by AEM Data Receipt
        </div>
    </div>
</body>
</html>
"""

# 5. Salva o arquivo final (vai ficar sempre com ~15KB, levíssimo)
with open('index.html', 'w', encoding='utf-8') as arquivo:
    arquivo.write(html_completo)

print("AEM Data Receipt: Arquivo HTML gerado e salvo com sucesso!")
