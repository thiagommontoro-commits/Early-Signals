import os
import re
from datetime import datetime
import google.generativeai as genai

# 1. Conecta com a Inteligência Artificial usando a chave que você salvou
CHAVE_API = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=CHAVE_API)
modelo = genai.GenerativeModel('gemini-1.5-flash')

# 2. O comando exato para extrair os dados
prompt = """
Você é um analista de inteligência de mercado focado em maquinário agrícola.
Gere as principais notícias agrícolas de hoje com foco em commodities, clima e política: 4 do Brasil, 4 da Argentina, e 4 divididas entre Paraguai, Uruguai e Chile.

Retorne APENAS código HTML puro, sem blocos de formatação markdown (não use ```html). 
Para CADA país, crie um bloco com a seguinte estrutura:

<div class="country-section">
    <h2 class="country-title">[BANDEIRA E NOME DO PAÍS] <span class="highlight-tag">4 INSIGHTS</span></h2>
    <div class="news-grid">
        <div class="news-item">
            <div class="news-header"><h3 class="news-headline">[TÍTULO DA NOTÍCIA EM MAIÚSCULO]</h3></div>
            <div class="news-content">[Resumo executivo de 2 linhas sobre o fato]</div>
            <div class="impact-box">
                <div class="impact-title">⚙️ Machinery Impact</div>
                <ul class="impact-list">
                    <li><strong>Tractors:</strong> [Impacto em vendas para <100HP, 100-200HP e >200HP]</li>
                    <li><strong>Harvesters:</strong> [Impacto em renovação de frota]</li>
                    <li><strong>Sprayers:</strong> [Impacto fitossanitário]</li>
                    <li><strong>Planters:</strong> [Impacto em janelas de plantio]</li>
                </ul>
                <a href="#" class="source-link">[NOME DA FONTE] ➔</a>
            </div>
        </div>
    </div>
</div>
"""

print("Iniciando AEM Data Receipt e análise de maquinário...")
resposta = modelo.generate_content(prompt)
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

# 6. Salva tudo e pronto!
with open('index.html', 'w', encoding='utf-8') as arquivo:
    arquivo.write(html_novo)

print("Relatório gerado com sucesso!")
