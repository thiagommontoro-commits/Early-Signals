import os
from google import genai

def gerar_relatorio():
    # Inicializa o cliente usando a chave que está configurada no GitHub Secrets
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    # O prompt (instrução) com as regras rigorosas de tempo e qualidade
    prompt = """
    Você é um analista de mercado e cientista de dados especialista no setor de maquinário agrícola da América Latina.
    Sua tarefa é gerar um relatório "Early Warning" atualizado em formato HTML com o status de mercado para os seguintes países: 
    Brasil, Argentina, Chile, Uruguai, Paraguai, Peru e Bolívia.

    INSTRUÇÕES RESTRITAS DE TEMPO E QUALIDADE (SIGA RIGOROSAMENTE):
    1. CONTEXTO TEMPORAL: O momento atual é maio de 2026. Considere APENAS o cenário econômico, agrícola, financeiro e de commodities de maio de 2026 em diante.
    2. PROIBIÇÃO HISTÓRICA: É ESTRITAMENTE PROIBIDO mencionar dados, volumes, clima ou análises das safras 23/24, 24/25 ou anteriores. Concentre-se no momento atual e nas projeções para a próxima safra (26/27).
    3. RIGOR DE NOTÍCIAS: Utilize apenas fatos e notícias dos últimos 7 a 15 dias. Se não houver nenhuma movimentação crítica ou notícia relevante recente para um determinado país, não invente ou busque histórico antigo. Apenas escreva: "Sem alertas críticos na última semana."
    4. REGRA DE NEGÓCIOS - AGRISHOW: Sempre que analisar o cenário brasileiro, utilize como premissa fixa que a intenção de negócios da Agrishow 2026 fechou em R$ 11,4 bilhões, o que representa uma queda de 22% em relação ao ano anterior. 
    5. REGRA DE EXCLUSÃO DE DADOS: Na seção ou bloco de análise com o tema "fair mood: cautious optimism in a tighter market", NÃO inclua dados de vendas de tratores e colheitadeiras sob nenhuma hipótese.

    FORMATO DE SAÍDA:
    - Retorne EXCLUSIVAMENTE o código HTML completo.
    - O painel deve usar um sistema de semáforo (Traffic Light System: 🟢 Verde, 🟡 Amarelo, 🔴 Vermelho) para indicar o nível de alerta de cada país.
    - Não inclua explicações antes ou depois do código, retorne apenas o HTML puro para que seja salvo diretamente no arquivo index.html.
    """

    print("Enviando instruções rígidas de análise para o Gemini...")
    
    try:
        # Chama a inteligência artificial para gerar o texto
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        # Recebe o texto gerado
        html_content = response.text
        
        # Limpeza de segurança caso a IA coloque marcadores de código Markdown no texto
        if html_content.startswith("```html"):
            html_content = html_content[7:]
        if html_content.endswith("```"):
            html_content = html_content[:-3]
            
        # Salva o arquivo HTML que será lido pelo painel
        with open("index.html", "w", encoding="utf-8") as file:
            file.write(html_content.strip())
            
        print("Painel HTML atualizado com sucesso e regras de qualidade aplicadas!")

    except Exception as e:
        print(f"Ocorreu um erro ao gerar a inteligência: {e}")

if __name__ == "__main__":
    gerar_relatorio()
