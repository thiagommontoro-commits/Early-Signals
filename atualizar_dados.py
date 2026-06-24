import os
import datetime
import json
from google import genai
from google.genai import types

def gerar_relatorio():
    # 1. Preparar data
    data_hoje = datetime.datetime.now().strftime("%d de JUN de 2026").upper()
    
    # 2. Conectar à IA
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    prompt = """
    Analista de mercado agro: Gere um JSON contendo 4 notícias para BRASIL, ARGENTINA, CHILE, URUGUAY, PARAGUAY, PERU, BOLIVIA, MEXICO, COLOMBIA.
    Estrutura: {"PAIS": [{"headline": "...", "content": "...", "farol_texto": "Positive", "source": "...", "impacts": [{"segment": "...", "status": "Positive", "desc": "..."}]}]}
    Mantenha 6 segmentos de impacto por notícia.
    """

    print("A solicitar processamento ao Gemini...")
    response = client.models.generate_content(
        model='gemini-1.5-flash', 
        contents=prompt, 
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    dados = json.loads(response.text)

    # 3. Criar HTML
    html = f"<html><body><h1>Relatório Executivo {data_hoje}</h1>"
    for pais, noticias in dados.items():
        html += f"<h2>{pais}</h2>"
        for n in noticias:
            html += f"<h3>{n['headline']}</h3><p>{n['content']}</p>"
    html += "</body></html>"

    # 4. Gravar na pasta raiz
    caminho = os.path.join(os.getcwd(), "index.html")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Ficheiro gravado com sucesso: {caminho}")

if __name__ == "__main__":
    gerar_relatorio()
