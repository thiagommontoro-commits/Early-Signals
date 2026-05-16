import os
from datetime import datetime
from google import genai

# 1. Configura a IA
CHAVE_API = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=CHAVE_API)

# 2. O Prompt Executivo Definitivo (Com Faróis e Regra da Semana)
prompt = """
Atue como um analista sênior de inteligência de mercado focado em maquinário agrícola para a América Latina.
Gere um relatório denso com as principais notícias agrícolas oficiais.

REGRAS OBRIGATÓRIAS:
1. FOCO: Soja, Milho, Cana-de-açúcar, Algodão, Café, Pecuária e Laranja.
2. PAÍSES ALVO: Brasil, Argentina, Chile, Uruguai, Paraguai, Peru e Bolívia. Agrupe em blocos lógicos se necessário.
3. REGRA DE TEMPO: Priorize as notícias de HOJE. Caso não haja notícias suficientes de hoje para um determinado país, você é OBRIGADO a buscar as notícias mais impactantes da ÚLTIMA SEMANA para completar o volume.
4. VOLUME: Mínimo de 3 a 4 notícias separadas por país/bloco.
5. IDIOMA: Inglês corporativo.

Retorne APENAS código HTML puro, sem blocos markdown.
Para CADA notícia, você deve calcular o impacto e classificar as cores dos "faróis":
- Use 'farol-verde' e 'Positive' para impactos bons.
- Use 'farol-amarelo' e 'Warning' (ou 'Stable') para neutro/atenção.
- Use 'farol-vermelho' e 'Critical' (ou 'Negative') para impactos ruins.

Use EXATAMENTE esta estrutura de HTML para os containers:

<div class="country-section">
    <h2 class="country-title">[BANDEIRA E NOME DO PAÍS/BLOCO] <span class="highlight-tag">MULTI-CROP ALERTS</span></h2>
    <div class="news-grid">
        <div class="news-item">
            <div class="news-header">
                <h3 class="news-headline">[CULTURA] - [TÍTULO DA NOTÍCIA EM MAIÚSCULO]</h3>
                <div class="farol farol-[verde/amarelo/vermelho]"><span class="farol-dot"></span>[Positive/Warning/Critical]</div>
            </div>
            <div class="news-content">[Resumo executivo de 3 linhas sobre o fato]</div>
            <div class="impact-box">
                <div class="impact-title">⚙️ Machinery Impact Analysis</div>
                <ul class="impact-list">
                    <li>
                        <div class="line-title"><strong>Tractors</strong> <div class="farol farol-[verde/amarelo/vermelho]"><span class="farol-dot"></span>[Status]</div></div>
                        <div class="impact-desc">[Impact on Small <100HP, Medium 100-200HP, High >200HP]</div>
                    </li>
                    <li>
                        <div class="line-title"><strong>Harvesters</strong> <div class="farol farol-[verde/amarelo/vermelho]"><span class="farol-dot"></span>[Status]</div></div>
                        <div class="impact-desc">[Specific impact on replacement cycles]</div>
                    </li>
                    <li>
                        <div class="line-title"><strong>Sprayers</strong> <div class="farol farol-[verde/amarelo/vermelho]"><span class="farol-dot"></span>[Status]</div></div>
                        <div class="impact-desc">[Specific impact on application needs]</div>
                    </li>
                    <li>
                        <div class="line-title"><strong>Planters</strong> <div class="farol farol-[verde/amarelo/vermelho]"><span class="farol-dot"></span>[Status]</div></div>
                        <div class="impact-desc">[Specific impact on planting windows]</div>
                    </li>
                </ul>
                <a href="[LINK REAL DA FONTE]" class="source-link">[NOME DA FONTE] ➔</a>
            </div>
        </div>
    </div>
</div>
"""

print("Consultando o mercado (Radar expandido LATAM + Regra Semanal)...")
resposta = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=prompt
)
noticias_html = resposta.text.replace("```html", "").replace("```", "")

# 3. Data de hoje
data_hoje = datetime.now().strftime("%b %d, %Y").upper()

# 4. Reconstrói o arquivo HTML com o CSS completo (Faróis + Tradução)
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
        .lang-switcher button:hover {{ background-color: var(--agco-red); border-color: var(--agco-red);
