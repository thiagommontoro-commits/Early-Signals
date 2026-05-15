import os
import re
from datetime import datetime
from google import genai # Nova biblioteca oficial

# 1. Configura a Inteligência Artificial
CHAVE_API = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=CHAVE_API)

# 2. O comando exato para extrair os dados
prompt = """
Atue como um analista sênior de inteligência de mercado focado em maquinário agrícola para a América Latina.
Gere um relatório denso com as principais notícias agrícolas oficiais de hoje. 

REGRAS OBRIGATÓRIAS:
1. FOCO EM COMMODITIES: Você deve rastrear e incluir notícias especificamente sobre: Soja, Milho, Cana-de-açúcar, Algodão, Café, Pecuária e Laranja.
2. VOLUME DE NOTÍCIAS: Gere no MÍNIMO 3 a 4 notícias separadas e aprofundadas para CADA UM dos seguintes países ou blocos:
   - Brasil
   - Argentina
   - México
   - Colômbia
   - Cone Sul & Pacífico (Uruguai, Paraguai, Peru e Chile)
3. IDIOMA: Todo o conteúdo gerado deve ser em Inglês corporativo (Executive Summary).

Retorne APENAS código HTML puro, sem blocos de formatação markdown (não use ```html). 
Para CADA país/bloco, crie um container com a seguinte estrutura exata:

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

print("Iniciando AEM Data Receipt com a nova API do Gemini...")
resposta = client.models.generate_content(
    model='gemini-2.5-flash', # Motor atualizado
    contents=prompt
)
noticias_html = resposta.text.replace("```html", "").replace("```", "")

# 3. Lê o seu painel visual (index.html)
with open('index.html', 'r', encoding='utf-8') as arquivo:
    html_atual = arquivo.read()

# 4. Atualiza a data lá no topo do site para a data de hoje
data_hoje = datetime.now().strftime("%b %d, %Y").upper()
html_atual = re.sub(r'<div class="date-badge">.*?</div>', f'<div class="date-badge">{data_hoje}</div>', html_atual)

# 5. Injeta as análises novas no meio do seu site
padrao_noticias = re.compile(r'.*?', re.DOTALL)
bloco_final = f"\n{noticias_html}\n"
html_novo = padrao_noticias.sub(bloco_final, html_atual)

# 6. Salva tudo
with open('index.html', 'w', encoding='utf-8') as arquivo:
    arquivo.write(html_novo)

print("Relatório gerado com sucesso!")
