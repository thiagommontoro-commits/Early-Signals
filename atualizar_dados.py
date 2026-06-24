import os
import datetime
import json
from google import genai
from google.genai import types

# Configuração da API
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def gerar_relatorio():
    data_hoje = datetime.datetime.now().strftime("%d de JUN de 2026").upper()
    
    # Prompt otimizado para garantir 4 notícias por país e o modelo correto
    prompt = """
    Você é um analista sênior de agronegócio. Gere um JSON com 4 notícias curtas e analíticas para CADA um dos 9 países: 
    BRASIL, ARGENTINA, CHILE, URUGUAY, PARAGUAY, PERU, BOLIVIA, MEXICO, COLOMBIA.
    Estrutura obrigatória: JSON com chaves dos nomes dos países em maiúsculo. 
    Cada país deve ter uma lista de 4 objetos contendo: "headline", "content", "farol_texto" (Positive/Warning/Critical), "source" e uma lista "impacts" com 6 segmentos de máquinas.
    Use dados reais e atuais.
    """

    print("Processando inteligência com Gemini 1.5 Flash...")
    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash', 
            contents=prompt, 
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        dados = json.loads(response.text)
    except Exception as e:
        print(f"Erro na IA: {e}")
        return

    # Template HTML simplificado e eficiente
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Early Warning AGCO</title></head>
<body>
    <h1>Relatório Executivo - {data_hoje}</h1>
    <div id="content">
"""
    
    for pais, noticias in dados.items():
        html += f"<h2>{pais}</h2>"
        for n in noticias:
            html += f"<h3>{n['headline']}</h3><p>{n['content']}</p>"
            # Aqui o script insere os dados da IA no seu template
    
    html += "</div></body></html>"

    # GARANTIA: Grava sempre na raiz do repositório
    caminho_arquivo = os.path.join(os.getcwd(), "index.html")
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Arquivo gravado com sucesso em: {caminho_arquivo}")

if __name__ == "__main__":
    gerar_relatorio()
