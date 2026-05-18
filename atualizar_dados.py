import os
from google import genai

def gerar_relatorio():
    # Inicializa o cliente usando a chave do GitHub Secrets
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    # 1. Lê o layout atual do seu painel para não perder o design
    try:
        with open("index.html", "r", encoding="utf-8") as file:
            layout_atual = file.read()
    except FileNotFoundError:
        layout_atual = "Crie um layout básico de HTML, pois o arquivo original não foi encontrado."

    # 2. O prompt com o layout fixo e as regras rigorosas
    prompt = f"""
    Você é um analista de mercado e cientista de dados especialista no setor de maquinário agrícola da América Latina.
    Sua tarefa é atualizar os dados do relatório "Early Warning" abaixo.

    AQUI ESTÁ O CÓDIGO HTML ATUAL DO PAINEL (O SEU MOLDE):
    {layout_atual}

    INSTRUÇÕES DE LAYOUT (OBRIGATÓRIO):
    - Mantenha EXATAMENTE a mesma estrutura HTML, classes CSS, cores e design visual do código acima.
    - Atualize APENAS os textos das análises, os semáforos e as datas. NÃO altere o estilo, as tags ou a estrutura da página.

    INSTRUÇÕES RESTRITAS DE TEMPO E QUALIDADE (SIGA RIGOROSAMENTE):
    1. CONTEXTO TEMPORAL: O momento atual é maio de 2026. Considere APENAS o cenário de maio de 2026 em diante.
    2. PROIBIÇÃO HISTÓRICA: É ESTRITAMENTE PROIBIDO mencionar dados ou análises das safras 23/24, 24/25 ou anteriores. Concentre-se no agora e nas projeções para a safra 26/27.
    3. RIGOR DE NOTÍCIAS: Utilize apenas fatos e notícias dos últimos 7 a 15 dias. Se não houver movimentação crítica recente, escreva apenas: "Sem alertas críticos na última semana."
    4. REGRA AGRISHOW: Sempre que o cenário brasileiro for citado, a premissa fixa é que a intenção de negócios da Agrishow 2026 fechou em R$ 11,4 bilhões (queda de 22% em relação ao ano anterior). 
    5. REGRA DE EXCLUSÃO: No bloco de análise "fair mood: cautious optimism in a tighter market", NÃO inclua dados de vendas de tratores e colheitadeiras sob nenhuma hipótese.

    FORMATO DE SAÍDA:
    - Retorne EXCLUSIVAMENTE o código HTML completo. Não inclua texto antes ou depois.
    """

    print("Enviando layout e instruções rígidas para o Gemini...")
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        html_content = response.text
        
        # Limpeza de formatação
        if html_content.startswith("```html"):
            html_content = html_content[7:]
        if html_content.endswith("```"):
            html_content = html_content[:-3]
            
        # Salva mantendo o mesmo arquivo
        with open("index.html", "w", encoding="utf-8") as file:
            file.write(html_content.strip())
            
        print("Painel atualizado: Layout mantido e notícias refinadas!")

    except Exception as e:
        print(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    gerar_relatorio()
