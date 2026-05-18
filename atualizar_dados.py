import os
from google import genai

def gerar_relatorio():
    # Inicializa o cliente da IA
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    # O SEU HTML EXATO (A FORMA DO BOLO INTOCÁVEL)
    layout_base = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Early warning AGCO</title>
    <style>
        :root {
            --agco-red: #cc0000;
            --agco-black: #111111;
            --agco-dark-gray: #333333;
            --agco-light-gray: #f4f4f4;
            --text-main: #222222;
            --white: #ffffff;
            
            /* Cores dos Faróis */
            --farol-verde-bg: #e2f0d9;
            --farol-verde-text: #385723;
            --farol-verde-dot: #70ad47;
            
            --farol-amarelo-bg: #fff2cc;
            --farol-amarelo-text: #7f6000;
            --farol-amarelo-dot: #ffc000;
            
            --farol-vermelho-bg: #fce4d6;
            --farol-vermelho-text: #c65911;
            --farol-vermelho-dot: #c00000;
        }
        body { font-family: 'Arial', sans-serif; background-color: #e9ecef; color: var(--text-main); margin: 0; padding: 20px; }
        
        body > .skiptranslate { display: none; }
        .goog-te-banner-frame.skiptranslate { display: none !important; }
        body { top: 0px !important; }
        
        .container { max-width: 1200px; margin: 0 auto; background-color: var(--white); box-shadow: 0 10px 25px rgba(0,0,0,0.15); }
        
        .header { background-color: var(--agco-black); color: var(--white); padding: 35px 40px; border-bottom: 6px solid var(--agco-red); display: flex; justify-content: space-between; align-items: center; background-image: url('https://images.unsplash.com/photo-1592982537447-7440770cbfc9?q=80&w=2000&auto=format&fit=crop'); background-size: cover; background-position: center; background-blend-mode: multiply; }
        .header-text h1 { margin: 0; font-size: 34px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 900; }
        .header-text p { margin: 5px 0 0 0; font-size: 14px; color: #d0d0d0; text-transform: uppercase; letter-spacing: 0.5px; }
        
        .header-controls { display: flex; flex-direction: column; align-items: flex-end; gap: 10px; }
        .date-badge { background-color: var(--agco-red); padding: 8px 16px; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 2px; text-align: center; width: 100%; box-sizing: border-box;}
        
        .lang-switcher { display: flex; gap: 5px; }
        .lang-switcher button { background-color: rgba(255, 255, 255, 0.1); color: var(--white); border: 1px solid rgba(255, 255, 255, 0.3); padding: 5px 10px; font-size: 11px; font-weight: bold; cursor: pointer; transition: all 0.2s; text-transform: uppercase; border-radius: 2px; }
        .lang-switcher button:hover { background-color: var(--agco-red); border-color: var(--agco-red); }
        
        .content-wrapper { padding: 30px 40px; }
        .alert-banner { background-color: var(--agco-light-gray); border-left: 5px solid var(--agco-red); padding: 15px 20px; margin-bottom: 35px; font-size: 13px; color: var(--agco-dark-gray); text-transform: uppercase; letter-spacing: 0.5px; font-weight: bold; }
        
        .country-section { margin-bottom: 50px; }
        .country-title { font-size: 24px; color: var(--agco-black); margin-top: 0; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #dddddd; display: flex; align-items: center; font-weight: 800; text-transform: uppercase; }
        .highlight-tag { display: inline-block; background-color: var(--agco-black); color: var(--white); padding: 4px 8px; font-size: 11px; margin-left: 15px; vertical-align: middle; letter-spacing: 1px; }
        
        .news-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 30px; }
        .news-item { background-color: var(--white); border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.02); display: flex; flex-direction: column; }
        .news-header { background-color: var(--agco-light-gray); padding: 15px 20px; border-left: 5px solid var(--agco-black); display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
        .news-headline { font-size: 15px; font-weight: bold; color: var(--agco-black); margin: 0; text-transform: uppercase; line-height: 1.4; }
        .news-content { padding: 20px; font-size: 14px; color: var(--agco-dark-gray); line-height: 1.6; flex-grow: 1; }
        
        .impact-box { margin: 0 20px 20px 20px; border-top: 3px solid var(--agco-red); background-color: #fafafa; padding: 15px; }
        .impact-title { font-weight: 900; color: var(--agco-red); margin-bottom: 12px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }
        
        .farol { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }
        .farol-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        
        .farol-verde { background-color: var(--farol-verde-bg); color: var(--farol-verde-text); }
        .farol-verde .farol-dot { background-color: var(--farol-verde-dot); box-shadow: 0 0 6px var(--farol-verde-dot); }
        
        .farol-amarelo { background-color: var(--farol-amarelo-bg); color: var(--farol-amarelo-text); }
        .farol-amarelo .farol-dot { background-color: var(--farol-amarelo-dot); box-shadow: 0 0 6px var(--farol-amarelo-dot); }
        
        .farol-vermelho { background-color: var(--farol-vermelho-bg); color: var(--farol-vermelho-text); }
        .farol-vermelho .farol-dot { background-color: var(--farol-vermelho-dot); box-shadow: 0 0 6px var(--farol-vermelho-dot); }
        
        .impact-list { list-style: none; padding: 0; margin: 0; font-size: 13px; }
        .impact-list li { margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px dashed #ddd; display: flex; flex-direction: column; gap: 5px; }
        .impact-list li:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        .line-title { display: flex; justify-content: space-between; align-items: center; }
        .impact-list strong { color: var(--agco-black); text-transform: uppercase; }
        .impact-desc { color: #555; font-size: 12.5px; padding-left: 2px; }
        
        .source-link { display: block; margin-top: 15px; font-size: 11px; color: var(--agco-red); text-decoration: none; font-weight: bold; text-align: right; letter-spacing: 1px; }
        .source-link:hover { color: var(--agco-black); }
        
        .footer { background-color: var(--agco-black); color: #777777; text-align: center; padding: 25px; font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; }
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
                <div class="date-badge">DATA DE HOJE AQUI</div>
            </div>
        </div>

        <div class="content-wrapper">
            <div class="alert-banner" translate="no">
                // AEM DATA RECEIPT: High-density daily market signals synthesized to mitigate time constraints for detailed product and market analysis.
            </div>

            </div>

        <div class="footer" translate="no">
            CONFIDENTIAL - For Internal Executive Alignment<br>
            Powered by AEM Data Receipt
        </div>
    </div>

    <div id="google_translate_element" style="display:none;"></div>
    <script type="text/javascript">
        function googleTranslateElementInit() {
            new google.translate.TranslateElement({pageLanguage: 'en', autoDisplay: false}, 'google_translate_element');
        }
        function changeLanguage(langCode) {
            var selectField = document.querySelector("select.goog-te-combo");
            if (selectField) {
                selectField.value = langCode;
                selectField.dispatchEvent(new Event('change'));
            }
        }
    </script>
    <script type="text/javascript" src="https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"></script>

</body>
</html>"""

    # INSTRUÇÕES DE PREENCHIMENTO E REGRAS RÍGIDAS
    instrucoes_iniciais = """
    Você é um analista de mercado e cientista de dados especialista no setor de maquinário agrícola da América Latina.
    Sua tarefa é gerar as notícias do relatório "Early Warning" e encaixá-las EXATAMENTE no código HTML fornecido.

    AQUI ESTÁ O CÓDIGO HTML DO PAINEL (O SEU MOLDE INTOCÁVEL):
    """
    
    regras_finais = """
    INSTRUÇÕES DE LAYOUT (OBRIGATÓRIO):
    - Mantenha EXATAMENTE a mesma estrutura HTML, classes CSS, tags, cores e design visual do código fornecido.
    - Preencha a div <div class="content-wrapper"> com as seções <div class="country-section"> para cada país analisado (Brasil, Argentina, Chile, Uruguai, Peru, Bolívia, Paraguai).
    - Substitua "DATA DE HOJE AQUI" pela data atual formatada (Ex: MAY 18, 2026).
    - NÃO altere a estrutura do CSS (<style>) nem os scripts do final da página.

    INSTRUÇÕES RESTRITAS DE TEMPO E QUALIDADE (SIGA RIGOROSAMENTE):
    1. CONTEXTO TEMPORAL: O momento atual é maio de 2026. Considere APENAS o cenário de maio de 2026 em diante.
    2. PROIBIÇÃO HISTÓRICA: É ESTRITAMENTE PROIBIDO mencionar dados ou análises das safras 23/24, 24/25 ou anteriores. Concentre-se no agora e nas projeções para a safra 26/27.
    3. RIGOR DE NOTÍCIAS: Utilize apenas fatos e notícias dos últimos 7 a 15 dias. Se não houver movimentação crítica recente para um país, escreva apenas: "Sem alertas críticos na última semana." e use o farol Amarelo (Stable) nas categorias.
    4. REGRA AGRISHOW: Sempre que o cenário brasileiro for citado, a premissa fixa é que a intenção de negócios da Agrishow 2026 fechou em R$ 11,4 bilhões (queda de 22% em relação ao ano anterior). 
    5. REGRA DE EXCLUSÃO: Se usar o tema "fair mood: cautious optimism in a tighter market", NÃO inclua dados de vendas de tratores e colheitadeiras sob nenhuma hipótese.

    FORMATO DE SAÍDA:
    - Retorne EXCLUSIVAMENTE o código HTML completo final. Não inclua texto explicativo antes ou depois.
    """

    # Junta as partes em uma única instrução estruturada
    prompt_completo = instrucoes_iniciais + "\n\n" + layout_base + "\n\n" + regras_finais

    print("Enviando layout fixo e instruções para o Gemini...")
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_completo,
        )
        
        html_content = response.text
        
        # Limpeza de formatação caso a IA devolva em markdown
        if html_content.startswith("```html"):
            html_content = html_content[7:]
        if html_content.endswith("```"):
            html_content = html_content[:-3]
            
        # Salva o arquivo sobrescrevendo a versão antiga
        with open("index.html", "w", encoding="utf-8") as file:
            file.write(html_content.strip())
            
        print("Painel atualizado: Layout blindado e notícias purificadas para 2026!")

    except Exception as e:
        print(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    gerar_relatorio()
