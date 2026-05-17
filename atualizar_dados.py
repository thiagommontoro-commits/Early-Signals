import os
from datetime import datetime
from google import genai

# 1. Configura a IA
CHAVE_API = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=CHAVE_API)

# 2. O Prompt Executivo Definitivo com Regra Estrita de Volume (Mínimo 3 notícias por país)
prompt = """
Atue como um analista sênior de inteligência de mercado focado em maquinário agrícola para a América Latina.
Gere um relatório denso com as principais notícias oficiais e factuais.

REGRAS OBRIGATÓRIAS DE CONTEÚDO E VOLUME:
1. VOLUME E BACKFILL (REGRA CRÍTICA): Você deve trazer OBRIGATORIAMENTE no mínimo 3 notícias separadas e profundas para CADA UM dos países/blocos listados. Se não houver notícias do dia de hoje para um determinado país, busque e utilize notícias dos dias anteriores da última semana para preencher rigorosamente a cota mínima de 3 notícias.
2. FOCO DUPLO: Cada notícia deve mesclar ou focar em:
   - COMMODITIES: Soja, Milho, Cana-de-açúcar, Algodão, Café, Pecuária e Laranja.
   - POLÍTICA E ECONOMIA: Taxas de juros, disponibilidade de crédito/subsídios, flutuações cambiais severas, barreiras comerciais, greves ou políticas governamentais que afetem o CAPEX de maquinário.
3. PAÍSES ALVO: Brasil, Argentina, México, Colômbia, Chile, Uruguai, Paraguai, Peru e Bolívia. Agrupe em blocos lógicos se necessário (ex: Cone Sur ou Região Andina), mas garanta que todos os nomes apareçam e tenham sua cota de notícias preenchida.
4. ESTRUTURA DE ANÁLISE: Para cada notícia, você deve incluir explicitamente a pergunta: 'What market segment does this information impact?' e responder analisando o impacto específico em Tractors (Small <100HP, Medium 100-200HP, High >200HP), Harvesters, Sprayers e Planters.
5. IDIOMA: Inglês corporativo (Executive Summary).

Retorne APENAS código HTML puro, sem blocos markdown.
Classifique o impacto usando as cores dos faróis: 'farol-verde' (Positive), 'farol-amarelo' (Warning/Stable), 'farol-vermelho' (Critical/Negative).

Use EXATAMENTE esta estrutura de HTML para os containers:

<div class="country-section">
    <h2 class="country-title">[BANDEIRA E NOME DO PAÍS/BLOCO] <span class="highlight-tag">MARKET & MACRO ALERTS</span></h2>
    <div class="news-grid">
        <div class="news-item">
            <div class="news-header">
                <h3 class="news-headline">[CULTURA ou MACRO/POLÍTICA] - [TÍTULO DA NOTÍCIA EM MAIÚSCULO]</h3>
                <div class="farol farol-[verde/amarelo/vermelho]"><span class="farol-dot"></span>[Positive/Warning/Critical]</div>
            </div>
            <div class="news-content">[Resumo executivo sobre o fato e as variáveis econômicas]</div>
            <div class="impact-box">
                <div class="impact-title">⚙️ Machinery Impact Analysis</div>
                <p class="impact-question" style="font-size: 12px; font-style: italic; color: #666; margin-top: -5px; margin-bottom: 10px;">What market segment does this information impact?</p>
                <ul class="impact-list">
                    <li>
                        <div class="line-title"><strong>Tractors</strong> <div class="farol farol-[verde/amarelo/vermelho]"><span class="farol-dot"></span>[Status]</div></div>
                        <div class="impact-desc">[Impact details]</div>
                    </li>
                    <li>
                        <div class="line-title"><strong>Harvesters</strong> <div class="farol farol-[verde/amarelo/vermelho]"><span class="farol-dot"></span>[Status]</div></div>
                        <div class="impact-desc">[Impact details]</div>
                    </li>
                    <li>
                        <div class="line-title"><strong>Sprayers</strong> <div class="farol farol-[verde/amarelo/vermelho]"><span class="farol-dot"></span>[Status]</div></div>
                        <div class="impact-desc">[Impact details]</div>
                    </li>
                    <li>
                        <div class="line-title"><strong>Planters</strong> <div class="farol farol-[verde/amarelo/vermelho]"><span class="farol-dot"></span>[Status]</div></div>
                        <div class="impact-desc">[Impact details]</div>
                    </li>
                </ul>
                <a href="[LINK REAL DA FONTE]" class="source-link">[NOME DA FONTE] ➔</a>
            </div>
        </div>
    </div>
</div>
"""

print("Consultando o mercado com a regra estrita de cota mínima por país...")
resposta = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=prompt
)
noticias_html = resposta.text.replace("```html", "").replace("```", "")

data_hoje = datetime.now().strftime("%b %d, %Y").upper()

html_completo = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Early warning AGCO</title>
    <style>
        :root {{
            --agco-red: #cc0000; --agco-black: #111111; --agco-dark-gray: #333333; --agco-light-gray: #f4f4f4; --text-main: #222222; --white: #ffffff;
            --farol-verde-bg: #e2f0d9; --farol-verde-text: #385723; --farol-verde-dot: #70ad47;
            --farol-amarelo-bg: #fff2cc; --farol-amarelo-text: #7f6000; --farol-amarelo-dot: #ffc000;
            --farol-vermelho-bg: #fce4d6; --farol-vermelho-text: #c65911; --farol-vermelho-dot: #c00000;
        }}
        body {{ font-family: 'Arial', sans-serif; background-color: #e9ecef; color: var(--text-main); margin: 0; padding: 20px; }}
        body > .skiptranslate {{ display: none; }}
        .goog-te-banner-frame.skiptranslate {{ display: none !important; }}
        body {{ top: 0px !important; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: var(--white); box-shadow: 0 10px 25px rgba(0,0,0,0.15); }}
        .header {{ background-color: var(--agco-black); color: var(--white); padding: 35px 40px; border-bottom: 6px solid var(--agco-red); display: flex; justify-content: space-between; align-items: center; background-image: url('https://images.unsplash.com/photo-1592982537447-7440770cbfc9?q=80&w=2000&auto=format&fit=crop'); background-size: cover; background-position: center; background-blend-mode: multiply; }}
        .header-text h1 {{ margin: 0; font-size: 34px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 900; }}
        .header-text p {{ margin: 5px 0 0 0; font-size: 14px; color: #d0d0d0; text-transform: uppercase; letter-spacing: 0.5px; }}
        .header-controls {{ display: flex; flex-direction: column; align-items: flex-end; gap: 10px; }}
        .date-badge {{ background-color: var(--agco-red); padding: 8px 16px; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 2px; text-align: center; width: 100%; box-sizing: border-box;}}
        .lang-switcher {{ display: flex; gap: 5px; }}
        .lang-switcher button {{ background-color: rgba(255, 255, 255, 0.1); color: var(--white); border: 1px solid rgba(255, 255, 255, 0.3); padding: 5px 10px; font-size: 11px; font-weight: bold; cursor: pointer; transition: all 0.2s; text-transform: uppercase; border-radius: 2px; }}
        .lang-switcher button:hover {{ background-color: var(--agco-red); border-color: var(--agco-red); }}
        .content-wrapper {{ padding: 30px 40px; }}
        .alert-banner {{ background-color: var(--agco-light-gray); border-left: 5px solid var(--agco-red); padding: 15px 20px; margin-bottom: 35px; font-size: 13px; color: var(--agco-dark-gray); text-transform: uppercase; letter-spacing: 0.5px; font-weight: bold; }}
        .country-section {{ margin-bottom: 50px; }}
        .country-title {{ font-size: 24px; color: var(--agco-black); margin-top: 0; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #dddddd; display: flex; align-items: center; font-weight: 800; text-transform: uppercase; }}
        .highlight-tag {{ display: inline-block; background-color: var(--agco-black); color: var(--white); padding: 4px 8px; font-size: 11px; margin-left: 15px; vertical-align: middle; letter-spacing: 1px; }}
        .news-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 30px; }}
        .news-item {{ background-color: var(--white); border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.02); display: flex; flex-direction: column; }}
        .news-header {{ background-color: var(--agco-light-gray); padding: 15px 20px; border-left: 5px solid var(--agco-black); display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }}
        .news-headline {{ font-size: 15px; font-weight: bold; color: var(--agco-black); margin: 0; text-transform: uppercase; line-height: 1.4; }}
        .news-content {{ padding: 20px; font-size: 14px; color: var(--agco-dark-gray); line-height: 1.6; flex-grow: 1; }}
        .impact-box {{ margin: 0 20px 20px 20px; border-top: 3px solid var(--agco-red); background-color: #fafafa; padding: 15px; }}
        .impact-title {{ font-weight: 900; color: var(--agco-red); margin-bottom: 12px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .farol {{ display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }}
        .farol-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
        .farol-verde {{ background-color: var(--farol-verde-bg); color: var(--farol-verde-text); }} .farol-verde .farol-dot {{ background-color: var(--farol-verde-dot); box-shadow: 0 0 6px var(--farol-verde-dot); }}
        .farol-amarelo {{ background-color: var(--farol-amarelo-bg); color: var(--farol-amarelo-text); }} .farol-amarelo .farol-dot {{ background-color: var(--farol-amarelo-dot); box-shadow: 0 0 6px var(--farol-amarelo-dot); }}
        .farol-vermelho {{ background-color: var(--farol-vermelho-bg); color: var(--farol-vermelho-text); }} .farol-vermelho .farol-dot {{ background-color: var(--farol-vermelho-dot); box-shadow: 0 0 6px var(--farol-vermelho-dot); }}
        .impact-list {{ list-style: none; padding: 0; margin: 0; font-size: 13px; }}
        .impact-list li {{ margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px dashed #ddd; display: flex; flex-direction: column; gap: 5px; }}
        .impact-list li:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
        .line-title {{ display: flex; justify-content: space-between; align-items: center; }}
        .impact-list strong {{ color: var(--agco-black); text-transform: uppercase; }}
        .impact-desc {{ color: #555; font-size: 12.5px; padding-left: 2px; }}
        .source-link {{ display: block; margin-top: 15px; font-size: 11px; color: var(--agco-red); text-decoration: none; font-weight: bold; text-align: right; letter-spacing: 1px; }}
        .source-link:hover {{ color: var(--agco-black); }}
        .footer {{ background-color: var(--agco-black); color: #777777; text-align: center; padding: 25px; font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; }}
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
                <div class="date-badge">{data_hoje}</div>
            </div>
        </div>

        <div class="content-wrapper">
            <div class="alert-banner" translate="no">
                // AEM DATA RECEIPT: High-density daily market signals synthesized to mitigate time constraints for detailed product and market analysis.
            </div>

            {noticias_html}

        </div>

        <div class="footer" translate="no">
            CONFIDENTIAL - For Internal Executive Alignment<br>
            Powered by AEM Data Receipt
        </div>
    </div>

    <div id="google_translate_element" style="display:none;"></div>
    <script type="text/javascript">
        function googleTranslateElementInit() {{
            new google.translate.TranslateElement({{pageLanguage: 'en', autoDisplay: false}}, 'google_translate_element');
        }}
        function changeLanguage(langCode) {{
            var selectField = document.querySelector("select.goog-te-combo");
            if (selectField) {{
                selectField.value = langCode;
                selectField.dispatchEvent(new Event('change'));
            }}
        }}
    </script>
    <script type="text/javascript" src="https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"></script>
</body>
</html>
"""

with open('index.html', 'w', encoding='utf-8') as arquivo:
    arquivo.write(html_completo)

print("Painel gerado com sucesso respeitando a cota mínima de 3 notícias por país!")
