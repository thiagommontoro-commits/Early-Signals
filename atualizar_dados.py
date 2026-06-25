import os
from pathlib import Path
import datetime

def gerar_dashboard(template_path, output_path):
    """
    Gera o dashboard HTML lendo de um arquivo de template e injetando
    a data de geração em múltiplos idiomas.

    Args:
        template_path (Path): Caminho para o arquivo de template HTML.
        output_path (Path): Caminho onde o arquivo HTML final será salvo.
    """
    try:
        # Lê o conteúdo do template
        print(f"📄 Lendo template de '{template_path.name}'...")
        html_content = template_path.read_text(encoding="utf-8")

        # --- INJEÇÃO DE DADOS DINÂMICOS ---
        
        # 1. Define os nomes dos meses para os idiomas suportados (pt, en, es)
        #    Isso evita a dependência da configuração de 'locale' do sistema.
        meses = {
            "pt": ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"],
            "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
            "es": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        }
        
        # 2. Gera as strings de data formatadas para cada idioma
        now = datetime.datetime.now()
        year = now.year
        month_idx = now.month - 1
        
        date_pt = f"{meses['pt'][month_idx]} de {year}"
        date_en = f"{meses['en'][month_idx]} {year}"
        date_es = f"{meses['es'][month_idx]} de {year}"

        # 3. Cria um elemento HTML que contém todas as traduções em atributos de dados.
        #    O texto inicial é em português para manter a aparência original.
        #    Um script no lado do cliente pode então trocar o texto com base no idioma selecionado.
        date_element_html = (
            f'<span id="report-date" '
            f'data-pt="{date_pt}" '
            f'data-en="{date_en}" '
            f'data-es="{date_es}">'
            f'{date_pt}'
            f'</span>'
        )

        # 4. Substitui o placeholder no HTML pelo novo elemento dinâmico
        html_content = html_content.replace("{{DATA_RELATORIO}}", date_element_html)

        # Salva o arquivo HTML final
        output_path.write_text(html_content, encoding="utf-8")
        print(f"✅ Dashboard '{output_path.name}' gerado com sucesso com suporte a múltiplos idiomas!")
        print("   -> A data agora está disponível em PT, EN e ES no elemento #report-date.")

    except FileNotFoundError:
        print(f"❌ ERRO: Arquivo de template não encontrado em '{template_path}'")
    except Exception as e:
        print(f"❌ Erro ao gerar o dashboard: {e}")

if __name__ == "__main__":
    # Define os caminhos baseados na localização do script
    script_dir = Path(__file__).parent
    template_arquivo = script_dir / "dashboard_template.html"
    output_arquivo = script_dir / "index.html"

    print("🚀 Iniciando a geração do dashboard 'Early Warning AGCO'...")

    # Verifica se o template existe antes de prosseguir
    if not template_arquivo.exists():
        print(f"❌ ERRO CRÍTICO: O arquivo de template '{template_arquivo.name}' é necessário mas não foi encontrado.")
        print("    Certifique-se de que o arquivo está na mesma pasta que o script.")
    else:
        gerar_dashboard(template_arquivo, output_arquivo)
        print("\n✅ Processo concluído.")

