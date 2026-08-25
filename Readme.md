# 🌎 Early Signals — LATAM Market Intelligence Framework

Dashboard executivo de inteligência de mercado para o agronegócio na América
Latina, publicado via GitHub Pages e atualizado automaticamente via GitHub
Actions. Desenvolvido por Thiago Medea Montoro | Global Reporting & Analytics.

**URL pública:** https://thiagommontoro-commits.github.io/Early-Signals/

---

## 📋 Índice

1. [Visão geral](#visão-geral)
2. [Arquitetura do repositório](#arquitetura-do-repositório)
3. [Módulo 1 — Market Signals (IA/Gemini)](#módulo-1--market-signals-iagemini)
4. [Módulo 2 — Inadimplência Crédito Rural (BCB)](#módulo-2--inadimplência-crédito-rural-bcb)
5. [Módulo 3 — Commodity Intelligence (planilha Cogo)](#módulo-3--commodity-intelligence-planilha-cogo)
6. [Fluxo de execução completo](#fluxo-de-execução-completo)
7. [Atualização mensal — o que fazer todo mês](#atualização-mensal--o-que-fazer-todo-mês)
8. [Troubleshooting — problemas já enfrentados](#troubleshooting--problemas-já-enfrentados)
9. [Roadmap / próximos passos](#roadmap--próximos-passos)

---

## Visão geral

O Early Signals nasceu como um agregador de notícias e fatores econômicos do
agronegócio para 8 países da América Latina (Brasil, Argentina, Chile,
Uruguai, Paraguai, Peru, Bolívia, México), gerado mensalmente por IA (Google
Gemini). Ao longo do projeto, evoluiu para incluir:

- 📊 **Commodity Intelligence**: preços internacionais (CBOT/ICE) + preços
  regionais (MT) + tendência projetada, 100% calculados de uma planilha.
- ⚠️ **Inadimplência do Crédito Rural**: indicador real do Banco Central,
  atualizado automaticamente sem depender de IA.
- 📈 **Tendência (direção)** nos Fatores Econômicos de todos os países,
  gerada pela própria IA.

Todo o pipeline roda via **GitHub Actions**, publicando um `index.html`
estático no GitHub Pages — sem servidor, sem custo de infraestrutura.

---

## Arquitetura do repositório

```
Early-Signals/
├── .github/workflows/
│   └── generate_dashboard.yml     # Workflow do GitHub Actions
├── .gitignore                     # Ignora .env, index.html, cache_dados_ia_*.json
├── .nojekyll                      # Necessário para GitHub Pages servir corretamente
├── gerador_dashboard_early_signals.py   # Script principal (orquestra tudo)
├── dashboard_template.html        # Template HTML com placeholders {{...}}
├── modulo_inadimplencia.py        # Módulo: busca BCB SGS 21148
├── modulo_commodities.py          # Módulo: lê planilha, calcula métricas
├── render_commodities.py          # Módulo: gera HTML da aba Commodities
├── requirements.txt               # google-genai, python-dotenv, openpyxl
├── data/
│   └── precos_agricolas_latest.xlsx   # Planilha do consultor (Carlos Cogo)
├── index.html                     # GERADO automaticamente (não editar manualmente)
├── dados_paises.json              # GERADO automaticamente (não versionado)
└── cache_dados_ia_AAAA_MM.json    # Cache mensal da IA (não versionado)
```

### Por que `index.html`, `dados_paises.json` e o cache não aparecem no repo
Estão no `.gitignore` — são **gerados a cada execução** do workflow. Isso é
proposital: garante que o dashboard sempre reflita a execução mais recente.

---

## Módulo 1 — Market Signals (IA/Gemini)

**Arquivo:** `gerador_dashboard_early_signals.py`, função `atualizar_dados_com_ia()`

- Para cada um dos 8 países, define uma lista de **Fatores Econômicos**
  (ex.: Crédito Rural, Juros/Selic, Câmbio, Prod. Grãos, Margens Produtor)
  e pede à IA (modelo `gemini-2.5-flash`) que gere, para cada fator:
  - `tendencia`: estado atual (positivo/negativo/incerto/estavel/alta/baixa/
    restritiva/expansiva) → controla o **farol** (🟢🟡🔴)
  - `direcao`: **NOVO** — perspectiva futura (melhorando/piorando/estavel)
    → controla o **selo de tendência** (▲/▼/▬)
  - `descricao`, `impactos`, `fonte`
- Também gera **notícias** reais e recentes (6 para Brasil/Argentina, 4 para
  os demais), com análise de impacto por linha de produto (tratores,
  colheitadeiras, pulverizadores, plantadeiras).
- **Cache mensal**: salva em `cache_dados_ia_{ano}_{mes}.json`. Se o cache do
  mês já existir, a IA **não é chamada de novo** — evita gastar a cota
  diária gratuita do Gemini (limite de 20 chamadas/dia no FreeTier).

⚠️ **Importante**: se você alterar o prompt (ex.: adicionar um campo novo),
isso só terá efeito em caches **futuros**. Um cache já existente do mês
atual precisa ser apagado manualmente para a mudança ter efeito (ver seção
de Troubleshooting).

---

## Módulo 2 — Inadimplência Crédito Rural (BCB)

**Arquivo:** `modulo_inadimplencia.py`

- Busca a série **SGS 21148** do Banco Central do Brasil: "Inadimplência da
  carteira de crédito — Recursos direcionados — Pessoas físicas — Crédito
  rural total (%)".
- API pública, **sem autenticação**, sem depender de IA nem de Power Automate:
  ```
  https://api.bcb.gov.br/dados/serie/bcdata.sgs.21148/dados/ultimos/20?formato=json
  ```
- ⚠️ **Limite da API**: o endpoint `/dados/ultimos/{N}` aceita **no máximo
  20 registros**. Pedir mais (ex.: 24) retorna erro `400 Bad Request`.
- Calcula: valor atual, Δ mês anterior (p.p.), posição vs. média histórica
  (18-20 meses), e classifica tendência (baixa=verde / alta=vermelho /
  estável=amarelo — lembrando que **menor inadimplência é melhor**).
- Retorna um dicionário no mesmo formato dos `fatores_economicos`, e é
  **inserido como primeiro item** no array do Brasil, dentro de
  `gerar_dashboard()`.
- **`descricao` e `impactos` são STRINGS SIMPLES** (não dicionários
  multilíngues) — o template renderiza esses campos como texto puro; usar
  dict aqui faz aparecer `{'pt': '...', 'en': '...'}` cru na tela (bug já
  corrigido).
- Se a API do BCB falhar, a função retorna `None` e o Brasil segue
  normalmente com os fatores da IA — nunca quebra o pipeline.

---

## Módulo 3 — Commodity Intelligence (planilha Cogo)

**Arquivos:** `modulo_commodities.py` (cálculos) + `render_commodities.py` (HTML)

### Fonte de dados
100% da planilha mensal do consultor **Carlos Cogo**, salva no repositório
como `data/precos_agricolas_latest.xlsx`. **Nenhum dado vem de API externa**
— essa foi uma decisão explícita do projeto (manter 100% Cogo). O rótulo de
fonte exibido no card ("CME Group & ICE Futures (US)") é apenas texto — não
muda de onde os dados são lidos.

### Mapa de colunas (validado contra a planilha real de Agosto/2026)

| Commodity | Aba | Coluna (benchmark) | Unidade |
|---|---|---|---|
| Soja | `Soja` | O (15) — CBOT | US$/bushel |
| Milho | `Milho` | U (21) — CBOT | US$/bushel |
| Café Arábica | `Demais AGRÍCOLAS` | F (6) — ICE NY | ¢/lb |
| Açúcar | `Cana` | F (6) — ICE NY | ¢/lb |
| Algodão | `Algodão` | H (8) — ICE NY | ¢/lb |
| Trigo | `Trigo` | K (11) — US SRW | US$/t |

### Preços regionais (US$)
| Commodity | UF | Aba | Coluna | Unidade |
|---|---|---|---|---|
| Soja | MT | `Soja` | K (11) | US$/60kg |
| Milho | MT | `Milho` | J (10) | US$/60kg |

### Métricas calculadas por commodity
- Preço atual (último mês fechado da série)
- Δ M/M (vs. mês anterior) e Δ A/A (vs. mesmo mês do ano anterior)
- Média dos últimos 5 anos (60 meses)
- Percentil histórico (posição do preço atual desde 1990/início da série)
- Farol (positivo/negativo/incerto) baseado em M/M + posição vs. média
- **Tendência projetada** (Opção C): momentum dos últimos 3 meses (peso 60%)
  + sazonalidade histórica mês-a-mês (peso 40%) → ▲ Alta / ▼ Baixa / ▬ Estável
- **Ranking de Momento**: as 6 commodities ordenadas pelo percentil histórico

### Camada de validação de frescor
A cada execução, compara o último mês encontrado na planilha com o mês/ano
corrente. Se a defasagem for maior que 1 mês, exibe um **banner amarelo de
alerta** no próprio dashboard e loga um aviso no GitHub Actions — evitando
que dados desatualizados sejam mostrados silenciosamente como atuais.

---

## Fluxo de execução completo

```
GitHub Actions dispara (push OU cron mensal)
  │
  ├─ 1. Instala dependências (requirements.txt)
  ├─ 2. Executa gerador_dashboard_early_signals.py
  │     │
  │     ├─ atualizar_dados_com_ia()
  │     │    ├─ Se cache do mês existe → usa cache (sem chamar IA)
  │     │    └─ Se não existe → chama Gemini → salva cache novo
  │     │
  │     └─ gerar_dashboard()
  │          ├─ Carrega dados_paises.json
  │          ├─ Busca Inadimplência BCB → insere no Brasil
  │          ├─ Para cada país: renderiza Fatores Econômicos + Notícias
  │          ├─ Processa Commodity Intelligence (lê planilha)
  │          ├─ Substitui todos os {{PLACEHOLDERS}} no template
  │          └─ Escreve index.html final
  │
  └─ 3. Commit do index.html atualizado → publica no GitHub Pages
```

### Gatilhos do workflow (`generate_dashboard.yml`)
- `on: push` (qualquer commit na `main`/`master`)
- `workflow_dispatch` (rodar manualmente via Actions → Run workflow)
- `schedule`: cron mensal (atualmente configurado para rodar automaticamente)

---

## Atualização mensal — o que fazer todo mês

### ✅ Automático (nada a fazer)
- **Inadimplência**: busca o BCB a cada execução, sempre atual.
- **Notícias/Fatores Econômicos**: IA gera 1x por mês (cache), sem ação manual.

### ✋ Manual (por enquanto)
- **Planilha de commodities**: quando receber o arquivo mensal do Carlos
  Cogo (`PREÇOS AGRÍCOLAS E INDICADORES {MÊS} {ANO}.xlsx`):
  1. Renomeie para `precos_agricolas_latest.xlsx`
  2. No GitHub, entre na pasta `data/`
  3. `Add file → Upload files` → arraste o arquivo (substitui o antigo)
  4. Commit changes
  5. O push já dispara o workflow automaticamente

> 💡 A automação completa dessa etapa (via Power Automate, SharePoint →
> GitHub) foi tentada mas não finalizada devido a dificuldades técnicas na
> configuração de expressões dinâmicas no Power Automate. Ver Roadmap.

---

## Troubleshooting — problemas já enfrentados

### ❌ "429 RESOURCE_EXHAUSTED" / cota do Gemini
**Causa**: FreeTier do Gemini permite ~20 chamadas/dia. Múltiplos commits no
mesmo dia (testes, correções) esgotam a cota.
**Efeito**: fatores econômicos exibem mensagem de erro em vez de conteúdo.
**Solução**: aguardar reset da cota (~24h) e evitar múltiplos commits que
disparam o workflow no mesmo dia enquanto estiver testando.

### ❌ "400 Bad Request" na API do BCB
**Causa**: pedir mais de 20 registros no endpoint `/dados/ultimos/{N}`.
**Solução**: já corrigida — `modulo_inadimplencia.py` usa `N_MESES = 20`.

### ❌ Card de inadimplência mostrando `{'pt': '...', 'en': '...'}` cru
**Causa**: `descricao`/`impactos` enviados como dicionário multilíngue, mas
o template renderiza esses campos como texto simples.
**Solução**: já corrigida — esses campos agora são strings simples em PT.

### ❌ Dashboard "sumiu" (só aparece o cabeçalho preto)
**Causa**: `dashboard_template.html` foi colado de forma corrompida (cópia
via chat/copy-paste truncou a última linha do `<script>` do Google
Translate, quebrando o HTML).
**Solução**: sempre **baixar o arquivo** e colar o conteúdo de um editor de
texto — nunca copiar diretamente de uma janela de chat/conversa, que pode
introduzir quebras de linha ou caracteres inválidos.
**Diagnóstico**: rodar o pipeline localmente (Python) e verificar se
`index.html` gerado termina com `</html>` e não tem `{{...}}` sobrando.

### ❌ Tendência dos Fatores Econômicos sempre "Estável"
**Causa**: o cache do mês (`cache_dados_ia_AAAA_MM.json`) foi gerado **antes**
do campo `direcao` ser adicionado ao prompt. Como o cache existe, a IA não é
chamada de novo, e o fallback (`direcao` ausente → Estável) é sempre usado.
**Solução**: apagar manualmente o `cache_dados_ia_AAAA_MM.json` do mês atual
no GitHub → o próximo push força a IA a gerar um cache novo, já com `direcao`.
⚠️ Consome 1 chamada da cota diária do Gemini.

### ❌ Erro "can't open file .../gerador_dashboard_early_signals.py"
**Causa**: o arquivo foi renomeado ou salvo com nome ligeiramente diferente
ao substituir conteúdo no GitHub (ex.: espaço extra, extensão duplicada).
**Solução**: conferir que o nome do arquivo na raiz do repo é **exatamente**
`gerador_dashboard_early_signals.py`.

### ❌ Power Automate: fórmulas aparecendo como texto cru no lugar de calculadas
**Causa**: fórmulas coladas diretamente no campo "Inputs" de uma ação
Compose não são interpretadas como expressão — ficam como texto literal.
**Tentativas de solução**: usar o painel "Expression" (fx) em vez de colar
direto; digitar manualmente evitando aspas curvas de copy-paste.
**Status**: não resolvido — fluxo do Power Automate foi abandonado. A
atualização da planilha permanece manual (ver seção anterior).

---

## Roadmap / próximos passos

Em ordem de prioridade sugerida:

1. **Regenerar o cache do mês** para ativar a tendência real dos Fatores
   Econômicos (ver Troubleshooting).
2. **Automatizar upload da planilha** — retomar Power Automate com mais
   tempo/calma, ou avaliar alternativa (ex.: pedir apoio de alguém com mais
   prática na ferramenta, ou script Python direto via Microsoft Graph API,
   que esbarrou antes em aprovação de TI para App Registration).
3. **Módulo Credit & Delinquency expandido** — hoje só a série 21148 (Brasil).
   Poderia incluir Argentina (BCRA) e México (Banxico/CNBV) futuramente.
4. **Módulo Climate Intelligence** — ainda não iniciado.
5. **Agricultural Momentum Index** — página executiva consolidando
   Commodities + Crédito + Clima num único índice por país (0-100).

---

## Convenções e decisões de projeto (para manter consistência)

- **Sempre 100% dados reais da planilha do Cogo** para commodities — nunca
  substituir por API pública, mesmo que o rótulo de fonte mencione bolsas
  públicas (CME/ICE).
- **Tom executivo e enxuto** nos textos gerados (ex.: inadimplência) —
  evitar parágrafos longos, preferir formato "valor + variação + contexto"
  em uma linha.
- **Fallback sempre seguro**: qualquer campo novo (ex.: `direcao`) deve ter
  um valor padrão que não quebre o dashboard se ausente (cache antigo,
  falha de API, etc.).
- **Design compacto**: cards pequenos, informação densa mas organizada,
  evitar quebras de texto feias (por isso a tendência das commodities usa
  "pill" compacta em vez de texto longo).
