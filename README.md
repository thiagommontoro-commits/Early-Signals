# Early Warning AGCO LATAM

Este projeto utiliza a API do Google Gemini para gerar um dashboard de inteligência de mercado focado no setor de máquinas agrícolas na América Latina.

## 🚀 Funcionalidades

- **Análise Econômica**: Monitora fatores macroeconômicos chave para 8 países.
- **Monitoramento de Notícias**: Coleta e analisa notícias recentes do agronegócio.
- **Impacto por Produto**: Avalia o impacto das notícias em linhas de produto (tratores, colheitadeiras, etc.).
- **Dashboard Interativo**: Apresenta os dados em uma interface web com suporte a múltiplos idiomas.

## 🤖 Automação com GitHub Actions

O dashboard é atualizado automaticamente sempre que há uma alteração na branch `main` ou manualmente através da aba "Actions" do GitHub.

## ⚙️ Configuração

1.  **Chave de API**: Para que a automação funcione, adicione sua `GEMINI_API_KEY` nos "Secrets" do repositório do GitHub com o nome `GEMINI_API_KEY`.
    -   `Settings` > `Secrets and variables` > `Actions` > `New repository secret`.

2.  **Execução**: O workflow do GitHub Actions (`.github/workflows/generate_dashboard.yml`) instala as dependências e executa o script `gerador_dashboard_early_signals.py` para gerar o `index.html`.