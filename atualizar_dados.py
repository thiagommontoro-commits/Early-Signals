import os
import datetime
import json
import urllib.request
import urllib.parse
import re

# ==========================================
# 1. PAINEL DE CONTROLO DA TABELA MACRO (EDITÁVEL)
# ==========================================

HISTORICO_MACRO = {
"MAR/2026": {
"selic": "14,75%", "cdi": "14,65%", "juros": "19,30%", "dolar": "R$ 5,02",
"ipca": "4,50%", "pib": "2,10%", "soja": "R$ 134,00"
},
"APR/2026": {
"selic": "14,50%", "cdi": "14,40%", "juros": "19,00%", "dolar": "R$ 5,08",
"ipca": "4,30%", "pib": "2,20%", "soja": "R$ 138,50"
},
"MAY/2026": {
"selic": "14,50%", "cdi": "14,40%", "juros": "19,00%", "dolar": "R$ 5,15",
"ipca": "4,20%", "pib": "2,30%", "soja": "R$ 142,00"
},
}

CONSOLIDADO_2025 = {
"selic": "11,75%",
"cdi": "11,65%",
"juros": "16,25%",
"dolar": "R$ 4,85",
"ipca": "4,62%",
"pib": "2,90%",
"soja": "R$ 130,00"
}

ANO_PROJECAO = "2027"

# ==========================================
# CÓDIGO DO SISTEMA (PROCESSAMENTO DINÂMICO E SCRAPING)
# ==========================================

def calcular_meses_rolantes():
meses_en = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
today = datetime.datetime.now()
m0_idx, m0_year = today.month - 1, today.year
m1_idx = m0_idx - 1 if m0_idx > 0 else 11
m1_year = m0_year if m0_idx > 0 else m0_year - 1
m2_idx = m1_idx - 1 if m1_idx > 0 else 11
m2_year = m1_year if m1_idx > 0 else m1_year - 1
return (
f"{meses_en[m0_idx]}/{m0_year}",
f"{meses_en[m1_idx]}/{m1_year}",
f"{meses_en[m2_idx]}/{m2_year}"
)

def buscar_dados_oficiais():
print("A procurar indicadores macroeconómicos (SGS Banco Central e Câmbio)...")
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
dolar_str = "R$ 5,15"
selic_str = "14,50%"
cdi_str = "14,40%"
juros_agro_str = "19,00%"
ipca_str = "4,20%"

try:
req = urllib.request.Request(
"https://economia.awesomeapi.com.br/last/USD-BRL",
headers=headers
)
dados_dolar = json.loads(urllib.request.urlopen(req, timeout=8).read())
dolar_str = "R$ {:.2f}".format(float(dados_dolar['USDBRL']['bid'])).replace('.', ',')
except Exception:
pass

try:
req = urllib.request.Request(
"https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json",
headers=headers
)
selic_atual = float(json.loads(urllib.request.urlopen(req, timeout=8).read())[0]["valor"])
selic_str = "{:.2f}%".format(selic_atual).replace('.', ',')
cdi_str = "{:.2f}%".format(selic_atual - 0.10).replace('.', ',')
juros_agro_str = "{:.2f}%".format(selic_atual + 4.50).replace('.', ',')
except Exception:
pass

try:
req = urllib.request.Request(
"https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados/ultimos/1?formato=json",
headers=headers
)
ipca_str = "{:.2f}%".format(
float(json.loads(urllib.request.urlopen(req, timeout=8).read())[0]['valor'])
).replace('.', ',')
except Exception:
pass

return dolar_str, selic_str, cdi_str, juros_agro_str, ipca_str


def buscar_projecoes_focus(ano_alvo):
print(f"A extrair expectativas MÉDIAS de mercado (Relatório Focus BCB) para o ano de {ano_alvo}...")
selic_proj, dolar_proj, ipca_proj, pib_proj = 10.50, 5.10, 4.10, 2.00
try:
filtro = (
"(Indicador eq 'Selic' or Indicador eq 'Câmbio' or "
"Indicador eq 'IPCA' or Indicador eq 'PIB Total') "
f"and DataReferencia eq '{ano_alvo}'"
)
url = (
"https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
"ExpectativasMercadoAnuais?$filter=" + urllib.parse.quote(filtro) +
"&$orderby=Data%20desc&$top=40&$format=json"
)
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
dados = json.loads(urllib.request.urlopen(req, timeout=10).read())
for item in dados.get("value", []):
if item.get("Indicador") == "Selic" and item.get("Media"):
selic_proj = float(item["Media"])
elif item.get("Indicador") == "Câmbio" and item.get("Media"):
dolar_proj = float(item["Media"])
elif item.get("Indicador") == "IPCA" and item.get("Media"):
ipca_proj = float(item["Media"])
elif item.get("Indicador") == "PIB Total" and item.get("Media"):
pib_proj = float(item["Media"])
except Exception:
pass

return {
"selic": "{:.2f}%".format(selic_proj).replace('.', ','),
"cdi": "{:.2f}%".format(selic_proj - 0.10).replace('.', ','),
"juros": "{:.2f}%".format(selic_proj + 4.50).replace('.', ','),
"dolar": "R$ {:.2f}".format(dolar_proj).replace('.', ','),
"ipca": "{:.2f}%".format(ipca_proj).replace('.', ','),
"pib": "{:.2f}%".format(pib_proj).replace('.', ','),
}


def buscar_precos_soja(dolar_proj_str, ano_proj):
print(f"A executar Motor de Scraping: Soja Físico e Soja B3 Futuro ({ano_proj})...")
headers = {'User-Agent': 'Mozilla/5.0'}
soja_hoje_brl = "R$ 138,50"
soja_futuro_brl = "R$ 145,00"

try:
dol_proj = float(dolar_proj_str.replace('R$', '').replace(',', '.').strip())
except Exception:
dol_proj = 5.25

try:
req = urllib.request.Request(
"https://www.noticiasagricolas.com.br/cotacoes/soja/soja-porto-paranagua-pr",
headers=headers
)
text_fis = re.sub(r'<[^>]+>', ' ', urllib.request.urlopen(req, timeout=8).read().decode('utf-8'))
matches_fis = re.findall(r'R\$\s*(\d{3}[,.]\d{2})', text_fis)
if matches_fis:
soja_hoje_brl = "R$ {}".format(matches_fis[0].replace('.', ','))
except Exception:
pass

try:
req = urllib.request.Request(
"https://www.noticiasagricolas.com.br/cotacoes/soja/soja-b3",
headers=headers
)
text_b3 = re.sub(r'<[^>]+>', ' ', urllib.request.urlopen(req, timeout=8).read().decode('utf-8'))
suffix = str(ano_proj)[-2:]
matches_b3 = re.findall(r'[A-Za-z]{3}/' + suffix + r'\s+([\d]{2}[,.]\d{2})', text_b3, re.IGNORECASE)
if matches_b3:
soja_futuro_brl = "R$ {:.2f}".format(
float(matches_b3[0].replace(',', '.')) * dol_proj
).replace('.', ',')
else:
base = float(soja_hoje_brl.replace('R$', '').replace(',', '.').strip())
soja_futuro_brl = "R$ {:.2f}".format(base * 1.05).replace('.', ',')
except Exception:
pass

return soja_hoje_brl, soja_futuro_brl


def parse_float(valor_str):
try:
return float(valor_str.replace('%', '').replace('R$', '').replace(' ', '').replace(',', '.').strip())
except Exception:
return 0.0


def calcular_variacao_pp(v_atual, v_ant):
diff = parse_float(v_atual) - parse_float(v_ant)
if diff > 0:
return '<span class="macro-badge red">● +{:.2f} PP</span>'.format(diff)
elif diff < 0:
return '<span class="macro-badge green">● {:.2f} PP</span>'.format(diff)
else:
return '<span class="macro-badge yellow">● 0,00 PP</span>'


def calcular_variacao_cambio(v_atual, v_ant):
diff = parse_float(v_atual) - parse_float(v_ant)
if diff > 0:
return '<span class="macro-badge red">● +R$ {:.2f}</span>'.format(diff)
elif diff < 0:
return '<span class="macro-badge green">● -R$ {:.2f}</span>'.format(abs(diff))
else:
return '<span class="macro-badge yellow">● R$ 0,00</span>'


# ==========================================
# FIX: construir_card_noticia — função que estava em falta no original
# ==========================================
def construir_card_noticia(item):
"""Converte um dicionário de notícia em HTML de card."""
impacts_html = ""
for imp in item.get("impacts", []):
cor_raw = imp.get('cor', 'amarelo')
cor_css = (
cor_raw
.replace('verde', 'positive')
.replace('amarelo', 'warning')
.replace('vermelho', 'critical')
)
impacts_html += """
<li>
<div class="line-title">
<strong>{segment}</strong>
<span class="farol farol-{cor}"><span class="farol-dot"></span>{status}</span>
</div>
<div class="impact-desc">{desc}</div>
</li>
""".format(
segment=imp.get('segment', ''),
cor=cor_css,
status=imp.get('status', ''),
desc=imp.get('desc', '')
)

farol_texto = item.get('farol_texto', 'Warning')
return """
<div class="news-item">
<div class="news-header">
<h3 class="news-headline">{headline}</h3>
<span class="farol farol-{farol_lower}"><span class="farol-dot"></span>{farol_texto}</span>
</div>
<div class="news-content">{content}</div>
<div class="impact-box">
<div class="impact-title">⚠️ Impacto Estimado Vendas AGCO</div>
<ul class="impact-list">{impacts_html}</ul>
<a href="#" class="source-link">Fonte: {source}</a>
</div>
</div>
""".format(
headline=item.get('headline', ''),
farol_lower=farol_texto.lower(),
farol_texto=farol_texto,
content=item.get('content', ''),
impacts_html=impacts_html,
source=item.get('source', '')
)


def obter_noticias_fallback(codigo_pais):
temas = {
"BR": [
{
"headline": "SOJA E MILHO: EXPORTAÇÕES RECORDE PRESSIONAM LOGÍSTICA E CAPEX",
"content": "O escoamento das safras de Soja e Milho (Safrinha) gera congestionamentos portuários. Grandes grupos do Centro-Oeste intensificam compras de equipamentos pesados para acelerar processos internos nas fazendas e evitar perdas de janela.",
"farol_cor": "verde", "farol_texto": "Positive", "source": "Safras & Mercado",
"impacts": [
{"segment": "Tratores (<100cv)", "cor": "amarelo", "status": "Warning", "desc": "Demanda estável, focada apenas em manutenção de pátio."},
{"segment": "Tratores (100-200cv)", "cor": "verde", "status": "Positive", "desc": "Renovação acelerada para suporte de transbordo."},
{"segment": "Tratores (>200cv)", "cor": "verde", "status": "Positive", "desc": "Altíssima demanda para preparo de solo nas janelas curtas da safrinha."},
{"segment": "Colheitadeiras", "cor": "verde", "status": "Positive", "desc": "Prioridade máxima de investimento em modelos de alta capacidade (Classe 8 e 9)."},
{"segment": "Pulverizadores", "cor": "verde", "status": "Positive", "desc": "Tecnologia de corte de seção impulsiona upgrades tecnológicos."},
{"segment": "Plantadeiras", "cor": "verde", "status": "Positive", "desc": "Sementeiras multi-linha precisas em alta para o plantio da segunda safra."}
]
},
{
"headline": "CANA E ALGODÃO: EXPANSÃO DO SETOR SUCROENERGÉTICO EM SP E MT",
"content": "Usinas de Cana-de-açúcar capitalizadas pelo preço do etanol e grandes produtores de Algodão no Mato Grosso abrem robustos programas de substituição de frotas ativas submetidas a uso severo.",
"farol_cor": "verde", "farol_texto": "Positive", "source": "Conab / Asocaña",
"impacts": [
{"segment": "Tratores (<100cv)", "cor": "amarelo", "status": "Warning", "desc": "Volume de vendas focado em implementos secundários de usinas."},
{"segment": "Tratores (100-200cv)", "cor": "verde", "status": "Positive", "desc": "Essenciais para o manejo e pulverização complementar do algodão."},
{"segment": "Tratores (>200cv)", "cor": "verde", "status": "Positive", "desc": "Compra massiva por usinas para reboque de transbordos de cana."},
{"segment": "Colheitadeiras", "cor": "verde", "status": "Positive", "desc": "Renovação contínua de colhedoras de cana e de algodão."},
{"segment": "Pulverizadores", "cor": "verde", "status": "Positive", "desc": "Autopropelidos altos são essenciais para o manejo tardio do algodão."},
{"segment": "Plantadeiras", "cor": "amarelo", "status": "Warning", "desc": "Estável; usinas focam na renovação de frota de tração e colheita primeiro."}
]
},
{
"headline": "CAFÉ E LARANJA: DESAFIOS SANITÁRIOS EXIGEM RESPOSTA MECANIZADA",
"content": "O avanço do Greening nos cinturões de Laranja em SP e as necessidades de aumento de rentabilidade na colheita do Café impulsionam o uso de atomizadores acoplados e tratores super-estreitos.",
"farol_cor": "amarelo", "farol_texto": "Warning", "source": "Fundecitrus / Cepea",
"impacts": [
{"segment": "Tratores (<100cv)", "cor": "verde", "status": "Positive", "desc": "Forte demanda por modelos cabinados e estreitos (fruteiros/cafeeiros)."},
{"segment": "Tratores (100-200cv)", "cor": "vermelho", "status": "Critical", "desc": "Subutilizados neste tipo de topografia e cultura perene."},
{"segment": "Tratores (>200cv)", "cor": "vermelho", "status": "Critical", "desc": "Nenhuma aplicação direta nas culturas de café ou laranja em produção."},
{"segment": "Colheitadeiras", "cor": "amarelo", "status": "Warning", "desc": "Mercado de colhedoras de café estável; colheita de laranja segue manual."},
{"segment": "Pulverizadores", "cor": "verde", "status": "Positive", "desc": "Explosão de vendas de atomizadores turbo para controle de insetos (psilídeo)."},
{"segment": "Plantadeiras", "cor": "vermelho", "status": "Critical", "desc": "Segmento estagnado nas áreas consolidadas destas culturas."}
]
},
{
"headline": "PECUÁRIA: INTEGRAÇÃO LAVOURA-PECUÁRIA (ILP) DIVERSIFICA COMPRAS",
"content": "A recuperação dos preços da Pecuária de corte impulsiona fazendeiros a adotarem o sistema ILP (Integração Lavoura-Pecuária), introduzindo maquinário agrícola em áreas antes exclusivas para pasto.",
"farol_cor": "verde", "farol_texto": "Positive", "source": "CNA Brasil",
"impacts": [
{"segment": "Tratores (<100cv)", "cor": "verde", "status": "Positive", "desc": "Manejo de cochos, currais e pequenas roçadas mecânicas."},
{"segment": "Tratores (100-200cv)", "cor": "verde", "status": "Positive", "desc": "O cavalo de força ideal para a conversão de pastagens degradadas."},
{"segment": "Tratores (>200cv)", "cor": "amarelo", "status": "Warning", "desc": "Uso restrito a mega-projetos pecuários de altíssima escala."},
{"segment": "Colheitadeiras", "cor": "amarelo", "status": "Warning", "desc": "Adoção inicial incipiente; muitos produtores optam pela terceirização."},
{"segment": "Pulverizadores", "cor": "amarelo", "status": "Warning", "desc": "Crescimento contínuo para limpeza de pastagens e suporte ao plantio."},
{"segment": "Plantadeiras", "cor": "verde", "status": "Positive", "desc": "Sementeiras consorciadas (grãos + forrageiras) lideram as cotações."}
]
}
],
"AR": [
{
"headline": "TRIGO E SOJA: RECUPERAÇÃO HÍDRICA NA ZONA NÚCLEO",
"content": "Após ciclos de seca, a recuperação da umidade na Província de Buenos Aires acende o otimismo para a safra de Trigo e posterior plantio de Soja, destravando orçamentos de frotas.",
"farol_cor": "verde", "farol_texto": "Positive", "source": "Bolsa de Cereales",
"impacts": [
{"segment": "Tratores (<100cv)", "cor": "amarelo", "status": "Warning", "desc": "Procura orgânica limitada ao setor leiteiro periférico."},
{"segment": "Tratores (100-200cv)", "cor": "verde", "status": "Positive", "desc": "O segmento mais procurado para suporte de plantio direto de trigo."},
{"segment": "Tratores (>200cv)", "cor": "amarelo", "status": "Warning", "desc": "Grandes contratistas ainda avaliam crédito antes da compra."},
{"segment": "Colheitadeiras", "cor": "amarelo", "status": "Warning", "desc": "Espera ativa pela colheita para liberação de capital de investimento."},
{"segment": "Pulverizadores", "cor": "verde", "status": "Positive", "desc": "Altamente demandados para dessecação e manejo fitossanitário do inverno."},
{"segment": "Plantadeiras", "cor": "verde", "status": "Positive", "desc": "Air Drills para grãos finos lideram as intenções de faturamento."}
]
},
{
"headline": "FINANCIAMENTO PRIVADO: BARTER DE GRÃOS IMPULSIONA VENDAS",
"content": "Dada a volatilidade das taxas bancárias locais, concessionárias na Argentina estruturam robustas operações de troca de grãos futuros (Barter) por máquinas novas.",
"farol_cor": "amarelo", "farol_texto": "Warning", "source": "La Nación Campo",
"impacts": [
{"segment": "Tratores (<100cv)", "cor": "vermelho", "status": "Critical", "desc": "Pequenos produtores têm menor acesso a estruturas de barter."},
{"segment": "Tratores (100-200cv)", "cor": "amarelo", "status": "Warning", "desc": "Renovações cirúrgicas acontecem atreladas ao compromisso de soja."},
{"segment": "Tratores (>200cv)", "cor": "verde", "status": "Positive", "desc": "Grandes grupos utilizam alavancagem em grãos para frotas pesadas."},
{"segment": "Colheitadeiras", "cor": "amarelo", "status": "Warning", "desc": "Processo longo de aprovação financeira corporativa."},
{"segment": "Pulverizadores", "cor": "verde", "status": "Positive", "desc": "Ticket médio mais acessível facilita o encerramento do negócio em grãos."},
{"segment": "Plantadeiras", "cor": "amarelo", "status": "Warning", "desc": "Produtores privilegiam a reforma da plantadeira usada nesta modalidade."}
]
},
{
"headline": "MÁQUINAS PARADAS: DESAFIO COM PEÇAS DE REPOSIÇÃO",
"content": "Trâmites aduaneiros pontuais atrasam componentes importados vitais. O foco das fazendas passa temporariamente da compra de novos ativos para a sobrevida das máquinas atuais.",
"farol_cor": "vermelho", "farol_texto": "Critical", "source": "INTA Argentina",
"impacts": [
{"segment": "Tratores (<100cv)", "cor": "amarelo", "status": "Warning", "desc": "Uso secundário prolongado com manutenções de baixo custo."},
{"segment": "Tratores (100-200cv)", "cor": "vermelho", "status": "Critical", "desc": "Adiamento da compra; oficinas operam na capacidade máxima."},
{"segment": "Tratores (>200cv)", "cor": "vermelho", "status": "Critical", "desc": "Frotas pesadas são as mais afetadas pela retenção de investimentos CapEx."},
{"segment": "Colheitadeiras", "cor": "vermelho", "status": "Critical", "desc": "Aumento do tempo de ciclo de vida das colhedoras de 5 para 8 anos."},
{"segment": "Pulverizadores", "cor": "amarelo", "status": "Warning", "desc": "Troca apenas de módulos GPS e barras, preservando o motor."},
{"segment": "Plantadeiras", "cor": "amarelo", "status": "Warning", "desc": "Ajuste e troca de rolamentos substituem a intenção de aquisição."}
]
},
{
"headline": "MUDANÇAS FISCAIS: REDUÇÃO DE RETENCIONES ANIMA EXPORTADORES",
"content": "A sinalização governamental de alívio fiscal nas exportações de milho e soja permite que os 'pools de siembra' planejem a renovação do seu parque de máquinas a médio prazo.",
"farol_cor": "verde", "farol_texto": "Positive", "source": "Clarín Rural",
"impacts": [
{"segment": "Tratores (<100cv)", "cor": "amarelo", "status": "Warning", "desc": "Baixa correlação com os grandes pools de exportação agrícola."},
{"segment": "Tratores (100-200cv)", "cor": "verde", "status": "Positive", "desc": "Orçamentos para 2027 já em cotação nas redes de revendas."},
{"segment": "Tratores (>200cv)", "cor": "verde", "status": "Positive", "desc": "Aquisição massiva em planeamento para cobrir o déficit tecnológico recente."},
{"segment": "Colheitadeiras", "cor": "verde", "status": "Positive", "desc": "Empresas contratistas preparam renovação de frotas obsoletas."},
{"segment": "Pulverizadores", "cor": "verde", "status": "Positive", "desc": "Tecnologia verde (redução de químicos) será o foco das compras."},
{"segment": "Plantadeiras", "cor": "verde", "status": "Positive", "desc": "Busca por chassis dobráveis de alta capacidade logística."}
]
}
]
}

# Template dinâmico para os restantes países
paises_restantes = ["MX", "CO", "UY", "PE", "CL", "BO", "PY"]
nomes_paises = {
"MX": "México", "CO": "Colômbia", "UY": "Uruguai",
"PE": "Peru", "CL": "Chile", "BO": "Bolívia", "PY": "Paraguai"
}

for sigla in paises_restantes:
nome = nomes_paises[sigla]
temas[sigla] = [
{
"headline": "SOJA, MILHO E PECUÁRIA: TRANSIÇÃO TECNOLÓGICA NO {}".format(sigla),
"content": "Grandes projetos agrícolas no {} expandem sistemas automáticos de precisão no campo. As margens da soja e a intensificação da pecuária exigem eficiência de frota.".format(nome),
"farol_cor": "verde", "farol_texto": "Positive", "source": "AEM Market Intelligence",
"impacts": [
{"segment": "Tratores (<100cv)", "cor": "verde", "status": "Positive", "desc": "Forte adoção na pecuária para manejo de pastos e horticultura."},
{"segment": "Tratores (100-200cv)", "cor": "verde", "status": "Positive", "desc": "O cavalo de força principal da mecanização média de grãos."},
{"segment": "Tratores (>200cv)", "cor": "amarelo", "status": "Warning", "desc": "Adoção restrita aos maiores conglomerados corporativos locais."},
{"segment": "Colheitadeiras", "cor": "amarelo", "status": "Warning", "desc": "Substituição pontual por modelos com telemetria básica."},
{"segment": "Pulverizadores", "cor": "verde", "status": "Positive", "desc": "Uso inteligente de sensores ganha escala nas aplicações."},
{"segment": "Plantadeiras", "cor": "verde", "status": "Positive", "desc": "Migração orgânica para sistemas pneumáticos de semente."}
]
},
{
"headline": "ALTOS CUSTOS DE COMBUSTÍVEL DIRECIONAM COMPRAS NO {}".format(sigla),
"content": "O custo da energia e logística no {} obriga produtores de grãos e cana a exigirem métricas rígidas de litros consumidos por hectare cultivado antes de fechar negócio.".format(nome),
"farol_cor": "amarelo", "farol_texto": "Warning", "source": "Canais Agropecuários Nacionais",
"impacts": [
{"segment": "Tratores (<100cv)", "cor": "amarelo", "status": "Warning", "desc": "Motores utilitários econômicos garantem vendas de subsistência."},
{"segment": "Tratores (100-200cv)", "cor": "amarelo", "status": "Warning", "desc": "Clientes optam por marcas que garantem eficiência em campo."},
{"segment": "Tratores (>200cv)", "cor": "vermelho", "status": "Critical", "desc": "Retração em motores muito pesados se não houver ganho de escala claro."},
{"segment": "Colheitadeiras", "cor": "amarelo", "status": "Warning", "desc": "Manutenção preventiva do motor passa a ser prioridade diária."},
{"segment": "Pulverizadores", "cor": "amarelo", "status": "Warning", "desc": "Implementos acoplados ganham preferência sobre autopropelidos caros."},
{"segment": "Plantadeiras", "cor": "amarelo", "status": "Warning", "desc": "Sementeiras mecânicas simples, com baixa exigência de tração, são preferidas."}
]
},
{
"headline": "FRUTICULTURA E CAFÉ: EXPORTAÇÃO PREMIUM PUXA O SETOR",
"content": "A receita em dólares proveniente das culturas de alto valor (como café e frutas) capitaliza as regiões de montanha e vales irrigados no {}, puxando a modernização.".format(nome),
"farol_cor": "verde", "farol_texto": "Positive", "source": "Exportadores Locais",
"impacts": [
{"segment": "Tratores (<100cv)", "cor": "verde", "status": "Positive", "desc": "Tratores estreitos (fruteiros e cafeeiros) dominam 80% do mercado local."},
{"segment": "Tratores (100-200cv)", "cor": "vermelho", "status": "Critical", "desc": "Sem aplicação nas entrelinhas estreitas destas culturas perenes."},
{"segment": "Tratores (>200cv)", "cor": "vermelho", "status": "Critical", "desc": "Demanda nula neste estrato topográfico e de cultivo específico."},
{"segment": "Colheitadeiras", "cor": "vermelho", "status": "Critical", "desc": "Cultura intensiva em mão-de-obra manual; adoção mecânica mínima."},
{"segment": "Pulverizadores", "cor": "verde", "status": "Positive", "desc": "Atomizadores de tecnologia de precisão são indispensáveis para exportação."},
{"segment": "Plantadeiras", "cor": "vermelho", "status": "Critical", "desc": "Nenhuma influência no mercado de sementeiras de grãos."}
]
},
{
"headline": "ALIANÇAS ESTRATÉGICAS COM CONCESSIONÁRIAS NO {}".format(sigla),
"content": "Com a escassez de mecânicos qualificados nas fazendas, os produtores do {} fidelizam-se a concessionárias que oferecem contratos de manutenção (Farming as a Service).".format(nome),
"farol_cor": "verde", "farol_texto": "Positive", "source": "Agro Dealer Network",
"impacts": [
{"segment": "Tratores (<100cv)", "cor": "amarelo", "status": "Warning", "desc": "Geralmente geridos pelos próprios produtores nas propriedades."},
{"segment": "Tratores (100-200cv)", "cor": "verde", "status": "Positive", "desc": "Contratos de serviço atrelados a tratores médios sustentam a revenda."},
{"segment": "Tratores (>200cv)", "cor": "verde", "status": "Positive", "desc": "A complexidade eletrónica exige a presença do concessionário."},
{"segment": "Colheitadeiras", "cor": "verde", "status": "Positive", "desc": "Inspeções de pré-safra garantidas são a chave do negócio."},
{"segment": "Pulverizadores", "cor": "verde", "status": "Positive", "desc": "Calibração de módulos ISOBUS prestada pelo distribuidor local."},
{"segment": "Plantadeiras", "cor": "amarelo", "status": "Warning", "desc": "Menor dependência de serviços externos, reparos geralmente mecânicos."}
]
}
]

# Render cards from fallback data
html_cards = ""
for item in temas.get(codigo_pais, []):
html_cards += construir_card_noticia(item)
return html_cards


def chamar_gemini_api(prompt):
"""
Chama a API Gemini via HTTP direto (sem dependência do SDK google-genai).
Requer GEMINI_API_KEY definida como variável de ambiente.
"""
api_key = os.environ.get("GEMINI_API_KEY", "")
if not api_key:
raise ValueError("GEMINI_API_KEY não definida.")

url = (
"https://generativelanguage.googleapis.com/v1beta/models/"
"gemini-2.5-flash:generateContent?key=" + api_key
)
payload = json.dumps({
"contents": [{"parts": [{"text": prompt}]}],
"generationConfig": {"responseMimeType": "application/json"}
}).encode("utf-8")

req = urllib.request.Request(
url,
data=payload,
headers={"Content-Type": "application/json"},
method="POST"
)
response = urllib.request.urlopen(req, timeout=60)
data = json.loads(response.read())
# Extract text from first candidate
return data["candidates"][0]["content"]["parts"][0]["text"]


def gerar_relatorio():
data_hoje = datetime.datetime.now().strftime("%b %d, %Y").upper()
m_atual, m_anterior, m_atras = calcular_meses_rolantes()

dados_m2 = HISTORICO_MACRO.get(m_atras, {
"selic": "--,--%", "cdi": "--,--%", "juros": "--,--%",
"dolar": "R$ --,--", "ipca": "--,--%", "pib": "--,--%", "soja": "R$ --,--"
})
dados_m1 = HISTORICO_MACRO.get(m_anterior, {
"selic": "--,--%", "cdi": "--,--%", "juros": "--,--%",
"dolar": "R$ --,--", "ipca": "--,--%", "pib": "--,--%", "soja": "R$ --,--"
})

dolar_oficial, selic_oficial, cdi_oficial, juros_agro_oficial, ipca_oficial = buscar_dados_oficiais()
projecoes_focus = buscar_projecoes_focus(ANO_PROJECAO)
soja_hoje, soja_proj = buscar_precos_soja(projecoes_focus['dolar'], ANO_PROJECAO)
pib_oficial = "2,30%"

selic_var_mes = calcular_variacao_pp(selic_oficial, dados_m1['selic'])
selic_var_ano = calcular_variacao_pp(selic_oficial, CONSOLIDADO_2025['selic'])
cdi_var_mes = calcular_variacao_pp(cdi_oficial, dados_m1['cdi'])
cdi_var_ano = calcular_variacao_pp(cdi_oficial, CONSOLIDADO_2025['cdi'])
juros_var_mes = calcular_variacao_pp(juros_agro_oficial, dados_m1['juros'])
juros_var_ano = calcular_variacao_pp(juros_agro_oficial, CONSOLIDADO_2025['juros'])
dolar_var_mes = calcular_variacao_cambio(dolar_oficial, dados_m1['dolar'])
dolar_var_ano = calcular_variacao_cambio(dolar_oficial, CONSOLIDADO_2025['dolar'])
ipca_var_mes = calcular_variacao_pp(ipca_oficial, dados_m1['ipca'])
ipca_var_ano = calcular_variacao_pp(ipca_oficial, CONSOLIDADO_2025['ipca'])
pib_var_mes = calcular_variacao_pp(pib_oficial, dados_m1['pib'])
pib_var_ano = calcular_variacao_pp(pib_oficial, CONSOLIDADO_2025['pib'])
soja_var_mes = calcular_variacao_cambio(soja_hoje, dados_m1['soja'])
soja_var_ano = calcular_variacao_cambio(soja_hoje, CONSOLIDADO_2025['soja'])

layout_base = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Early warning AGCO - LATAM Executive Intelligence</title>
<style>
:root {
--agco-red: #cc0000;
--agco-black: #111111;
--agco-dark-gray: #333333;
--agco-light-gray: #f4f4f4;
--text-main: #222222;
--white: #ffffff;
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
.container { max-width: 1200px; margin: 0 auto; background-color: var(--white); box-shadow: 0 10px 25px rgba(0,0,0,0.15); }
.header { background-color: var(--agco-black); color: var(--white); padding: 35px 40px; border-bottom: 6px solid var(--agco-red); display: flex; justify-content: space-between; align-items: center; }
.header-text h1 { margin: 0; font-size: 34px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 900; }
.header-text p { margin: 5px 0 0 0; font-size: 14px; color: #d0d0d0; text-transform: uppercase; letter-spacing: 0.5px; }
.header-controls { display: flex; flex-direction: column; align-items: flex-end; gap: 10px; }
.date-badge { background-color: var(--agco-red); padding: 8px 16px; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 2px; text-align: center; }
.lang-switcher { display: flex; gap: 5px; }
.lang-switcher button { background-color: rgba(255,255,255,0.1); color: var(--white); border: 1px solid rgba(255,255,255,0.3); padding: 5px 10px; font-size: 11px; font-weight: bold; cursor: pointer; text-transform: uppercase; border-radius: 2px; }
.lang-switcher button:hover { background-color: var(--agco-red); }
.content-wrapper { padding: 30px 40px; }
.alert-banner { background-color: var(--agco-light-gray); border-left: 5px solid var(--agco-red); padding: 15px 20px; margin-bottom: 35px; font-size: 13px; color: var(--agco-dark-gray); text-transform: uppercase; letter-spacing: 0.5px; font-weight: bold; }
.tabs-nav { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 25px; border-bottom: 3px solid var(--agco-black); padding-bottom: 5px; }
.tab-btn { background-color: var(--agco-light-gray); color: var(--agco-dark-gray); border: none; padding: 12px 20px; font-size: 13px; font-weight: bold; cursor: pointer; text-transform: uppercase; letter-spacing: 0.5px; transition: all 0.2s; border-radius: 2px 2px 0 0; }
.tab-btn:hover { background-color: #e0e0e0; }
.tab-btn.active { background-color: var(--agco-black); color: var(--white); border-bottom: 3px solid var(--agco-red); }
.tab-content { display: none; animation: fadeIn 0.4s ease; }
.tab-content.active { display: block; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
.country-title { font-size: 24px; color: var(--agco-black); margin-top: 0; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #ddd; display: flex; align-items: center; font-weight: 800; text-transform: uppercase; }
.highlight-tag { display: inline-block; background-color: var(--agco-black); color: var(--white); padding: 4px 8px; font-size: 11px; margin-left: 15px; vertical-align: middle; letter-spacing: 1px; }
.news-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 30px; }
.news-item { background-color: var(--white); border: 1px solid #e0e0e0; box-shadow: 0 4px 6px rgba(0,0,0,0.02); display: flex; flex-direction: column; border-radius: 4px; overflow: hidden; }
.news-header { background-color: var(--agco-light-gray); padding: 18px 20px; border-left: 5px solid var(--agco-black); display: flex; justify-content: space-between; align-items: flex-start; gap: 15px; }
.news-headline { font-size: 15px; font-weight: bold; color: var(--agco-black); margin: 0; text-transform: uppercase; line-height: 1.4; }
.news-content { padding: 20px; font-size: 14px; color: var(--agco-dark-gray); line-height: 1.6; flex-grow: 1; text-align: justify; }
.impact-box { margin: 0 20px 20px 20px; border-top: 3px solid var(--agco-red); background-color: #fafafa; padding: 15px; border-radius: 0 0 4px 4px; }
.impact-title { font-weight: 900; color: var(--agco-red); margin-bottom: 12px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }
.farol { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }
.farol-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.farol-positive { background-color: var(--farol-verde-bg); color: var(--farol-verde-text); }
.farol-positive .farol-dot { background-color: var(--farol-verde-dot); box-shadow: 0 0 6px var(--farol-verde-dot); }
.farol-warning { background-color: var(--farol-amarelo-bg); color: var(--farol-amarelo-text); }
.farol-warning .farol-dot { background-color: var(--farol-amarelo-dot); box-shadow: 0 0 6px var(--farol-amarelo-dot); }
.farol-critical { background-color: var(--farol-vermelho-bg); color: var(--farol-vermelho-text); }
.farol-critical .farol-dot { background-color: var(--farol-vermelho-dot); box-shadow: 0 0 6px var(--farol-vermelho-dot); }
.impact-list { list-style: none; padding: 0; margin: 0; font-size: 13px; }
.impact-list li { margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px dashed #ddd; display: flex; flex-direction: column; gap: 5px; }
.impact-list li:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
.line-title { display: flex; justify-content: space-between; align-items: center; }
.impact-list strong { color: var(--agco-black); text-transform: uppercase; }
.impact-desc { color: #555; font-size: 12.5px; padding-left: 2px; line-height: 1.4; }
.source-link { display: block; margin-top: 15px; font-size: 11px; color: var(--agco-red); text-decoration: none; font-weight: bold; text-align: right; letter-spacing: 1px; text-transform: uppercase; }
.source-link:hover { color: var(--agco-black); }
.macro-section { margin-top: 40px; background-color: var(--white); border: 1px solid #e0e0e0; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-radius: 4px; }
.macro-title { font-size: 20px; font-weight: 900; text-transform: uppercase; margin-top: 0; margin-bottom: 20px; display: flex; align-items: center; gap: 10px; border-bottom: 2px solid #ddd; padding-bottom: 10px; color: var(--agco-black); }
.macro-title .tag-brasil { background-color: var(--agco-black); color: var(--white); padding: 4px 8px; font-size: 12px; letter-spacing: 1px; }
.macro-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: center; }
.macro-table th { background-color: var(--agco-black); color: var(--white); padding: 14px 10px; font-weight: bold; border-bottom: 4px solid var(--agco-red); text-transform: uppercase; }
.macro-table td { padding: 12px 10px; border-bottom: 1px solid #eee; color: var(--agco-dark-gray); }
.macro-table tr:last-child td { border-bottom: none; }
.macro-table td:first-child { text-align: left; font-weight: bold; color: var(--agco-black); width: 25%; }
.macro-badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; text-transform: uppercase; }
.macro-badge.yellow { background-color: var(--farol-amarelo-bg); color: var(--farol-amarelo-text); }
.macro-badge.green { background-color: var(--farol-verde-bg); color: var(--farol-verde-text); }
.macro-badge.red { background-color: var(--farol-vermelho-bg); color: var(--farol-vermelho-text); }
.macro-source { font-size: 11px; color: #777; margin-top: 15px; font-style: italic; }
.footer { background-color: var(--agco-black); color: #777777; text-align: center; padding: 25px; font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; border-top: 4px solid var(--agco-red); }
</style>
</head>
<body>
<div class="container">
<div class="header">
<div class="header-text">
<h1>Early warning AGCO</h1>
<p>LATAM Market Intelligence &amp; Sales Prediction Model</p>
</div>
<div class="header-controls">
<div class="date-badge">%%DATA_HOJE%%</div>
</div>
</div>
<div class="content-wrapper">
<div class="alert-banner">
// AEM DATA RECEIPT: SCHEDULED RUN ACTIVE. FOCUS ESTIMATES SHIFTED TO HISTORICAL MEAN TRACKING.
CROSS-RATE COMMODITY INGESTION OPERATIONAL FOR TARGET YEAR %%ANO_FUTURO%%.
</div>

<div class="tabs-nav">
<button class="tab-btn active" onclick="openCountry(event, 'brazil')">&#127463;&#127479; Brasil</button>
<button class="tab-btn" onclick="openCountry(event, 'argentina')">&#127462;&#127479; Argentina</button>
<button class="tab-btn" onclick="openCountry(event, 'chile')">&#127464;&#127473; Chile</button>
<button class="tab-btn" onclick="openCountry(event, 'uruguay')">&#127482;&#127486; Uruguai</button>
<button class="tab-btn" onclick="openCountry(event, 'paraguay')">&#127477;&#127486; Paraguai</button>
<button class="tab-btn" onclick="openCountry(event, 'peru')">&#127477;&#127466; Peru</button>
<button class="tab-btn" onclick="openCountry(event, 'bolivia')">&#127463;&#127476; Bolívia</button>
<button class="tab-btn" onclick="openCountry(event, 'mexico')">&#127474;&#127485; México</button>
<button class="tab-btn" onclick="openCountry(event, 'colombia')">&#127464;&#127476; Colômbia</button>
</div>

<div id="brazil" class="tab-content active">
<h2 class="country-title">&#127463;&#127479; BRAZIL <span class="highlight-tag">MARKET &amp; MACRO ALERTS</span></h2>
<div class="news-grid">%%NOTICIAS_BR%%</div>
<div class="macro-section">
<h3 class="macro-title">&#128202; 1. MACROECONOMIA &amp; COMMODITIES <span class="tag-brasil">BRASIL</span></h3>
<table class="macro-table">
<thead>
<tr>
<th>INDICADOR</th>
<th>CONSOLIDADO 2025</th>
<th>%%M_ATRAS%%</th>
<th>%%M_ANTERIOR%%</th>
<th>%%M_ATUAL%% (ATUAL)</th>
<th>VAR. MES</th>
<th>VAR. ANO</th>
<th>PROJ. MEDIA FOCUS %%ANO_FUTURO%%</th>
</tr>
</thead>
<tbody>
<tr>
<td>Taxa Selic (Meta BCB)</td>
<td>%%SELIC_2025%%</td><td>%%SELIC_M2%%</td><td>%%SELIC_M1%%</td><td>%%SELIC_M0%%</td>
<td>%%SELIC_VAR_MES%%</td><td>%%SELIC_VAR_ANO%%</td><td>%%SELIC_PROJ%%</td>
</tr>
<tr>
<td>Taxa CDI (a.a.)</td>
<td>%%CDI_2025%%</td><td>%%CDI_M2%%</td><td>%%CDI_M1%%</td><td>%%CDI_M0%%</td>
<td>%%CDI_VAR_MES%%</td><td>%%CDI_VAR_ANO%%</td><td>%%CDI_PROJ%%</td>
</tr>
<tr>
<td>Juros Comerciais Agro</td>
<td>%%JUROS_2025%%</td><td>%%JUROS_M2%%</td><td>%%JUROS_M1%%</td><td>%%JUROS_M0%%</td>
<td>%%JUROS_VAR_MES%%</td><td>%%JUROS_VAR_ANO%%</td><td>%%JUROS_PROJ%%</td>
</tr>
<tr>
<td>Câmbio (USD/BRL)</td>
<td>%%DOLAR_2025%%</td><td>%%DOLAR_M2%%</td><td>%%DOLAR_M1%%</td><td>%%DOLAR_M0%%</td>
<td>%%DOLAR_VAR_MES%%</td><td>%%DOLAR_VAR_ANO%%</td><td>%%DOLAR_PROJ%%</td>
</tr>
<tr>
<td>IPCA (Inflação Acum. 12m)</td>
<td>%%IPCA_2025%%</td><td>%%IPCA_M2%%</td><td>%%IPCA_M1%%</td><td>%%IPCA_M0%%</td>
<td>%%IPCA_VAR_MES%%</td><td>%%IPCA_VAR_ANO%%</td><td>%%IPCA_PROJ%%</td>
</tr>
<tr>
<td>Crescimento PIB Brasil (a.a.)</td>
<td>%%PIB_2025%%</td><td>%%PIB_M2%%</td><td>%%PIB_M1%%</td><td>%%PIB_M0%%</td>
<td>%%PIB_VAR_MES%%</td><td>%%PIB_VAR_ANO%%</td><td>%%PIB_PROJ%%</td>
</tr>
<tr>
<td>Preço da Soja (Sc 60kg - Cepea/B3)</td>
<td>%%SOJA_2025%%</td><td>%%SOJA_M2%%</td><td>%%SOJA_M1%%</td><td>%%SOJA_M0%%</td>
<td>%%SOJA_VAR_MES%%</td><td>%%SOJA_VAR_ANO%%</td><td>%%SOJA_PROJ%%</td>
</tr>
</tbody>
</table>
<div class="macro-source">*Fonte: B3 Futuros, Notícias Agrícolas, Cepea, API SGS e Relatório Focus (Média de Mercado).</div>
</div>
</div>

<div id="argentina" class="tab-content">
<h2 class="country-title">&#127462;&#127479; ARGENTINA <span class="highlight-tag">MARKET &amp; MACRO ALERTS</span></h2>
<div class="news-grid">%%NOTICIAS_AR%%</div>
</div>
<div id="chile" class="tab-content">
<h2 class="country-title">&#127464;&#127473; CHILE <span class="highlight-tag">MARKET &amp; MACRO ALERTS</span></h2>
<div class="news-grid">%%NOTICIAS_CL%%</div>
</div>
<div id="uruguay" class="tab-content">
<h2 class="country-title">&#127482;&#127486; URUGUAY <span class="highlight-tag">MARKET &amp; MACRO ALERTS</span></h2>
<div class="news-grid">%%NOTICIAS_UY%%</div>
</div>
<div id="paraguay" class="tab-content">
<h2 class="country-title">&#127477;&#127486; PARAGUAY <span class="highlight-tag">MARKET &amp; MACRO ALERTS</span></h2>
<div class="news-grid">%%NOTICIAS_PY%%</div>
</div>
<div id="peru" class="tab-content">
<h2 class="country-title">&#127477;&#127466; PERU <span class="highlight-tag">MARKET &amp; MACRO ALERTS</span></h2>
<div class="news-grid">%%NOTICIAS_PE%%</div>
</div>
<div id="bolivia" class="tab-content">
<h2 class="country-title">&#127463;&#127476; BOLIVIA <span class="highlight-tag">MARKET &amp; MACRO ALERTS</span></h2>
<div class="news-grid">%%NOTICIAS_BO%%</div>
</div>
<div id="mexico" class="tab-content">
<h2 class="country-title">&#127474;&#127485; MEXICO <span class="highlight-tag">MARKET &amp; MACRO ALERTS</span></h2>
<div class="news-grid">%%NOTICIAS_MX%%</div>
</div>
<div id="colombia" class="tab-content">
<h2 class="country-title">&#127464;&#127476; COLOMBIA <span class="highlight-tag">MARKET &amp; MACRO ALERTS</span></h2>
<div class="news-grid">%%NOTICIAS_CO%%</div>
</div>
</div>
<div class="footer">
CONFIDENTIAL &mdash; For Internal AGCO Management Alignment Only &mdash; Powered by AEM Intelligence Pipeline
</div>
</div>

<script>
function openCountry(evt, countryName) {
var i, tabcontent, tablinks;
tabcontent = document.getElementsByClassName("tab-content");
for (i = 0; i < tabcontent.length; i++) {
tabcontent[i].style.display = "none";
tabcontent[i].classList.remove("active");
}
tablinks = document.getElementsByClassName("tab-btn");
for (i = 0; i < tablinks.length; i++) {
tablinks[i].classList.remove("active");
}
document.getElementById(countryName).style.display = "block";
document.getElementById(countryName).classList.add("active");
evt.currentTarget.classList.add("active");
}
</script>
</body>
</html>"""

# ==========================================
# Substituições de placeholders (todos com %% para evitar conflito com CSS)
# ==========================================
replacements = {
"%%DATA_HOJE%%": data_hoje,
"%%ANO_FUTURO%%": ANO_PROJECAO,
"%%M_ATRAS%%": m_atras,
"%%M_ANTERIOR%%": m_anterior,
"%%M_ATUAL%%": m_atual,
# Consolidado 2025
"%%SELIC_2025%%": CONSOLIDADO_2025["selic"],
"%%CDI_2025%%": CONSOLIDADO_2025["cdi"],
"%%JUROS_2025%%": CONSOLIDADO_2025["juros"],
"%%DOLAR_2025%%": CONSOLIDADO_2025["dolar"],
"%%IPCA_2025%%": CONSOLIDADO_2025["ipca"],
"%%PIB_2025%%": CONSOLIDADO_2025["pib"],
"%%SOJA_2025%%": CONSOLIDADO_2025["soja"],
# M2
"%%SELIC_M2%%": dados_m2["selic"],
"%%CDI_M2%%": dados_m2["cdi"],
"%%JUROS_M2%%": dados_m2["juros"],
"%%DOLAR_M2%%": dados_m2["dolar"],
"%%IPCA_M2%%": dados_m2["ipca"],
"%%PIB_M2%%": dados_m2["pib"],
"%%SOJA_M2%%": dados_m2["soja"],
# M1
"%%SELIC_M1%%": dados_m1["selic"],
"%%CDI_M1%%": dados_m1["cdi"],
"%%JUROS_M1%%": dados_m1["juros"],
"%%DOLAR_M1%%": dados_m1["dolar"],
"%%IPCA_M1%%": dados_m1["ipca"],
"%%PIB_M1%%": dados_m1["pib"],
"%%SOJA_M1%%": dados_m1["soja"],
# M0 (atual)
"%%SELIC_M0%%": selic_oficial,
"%%CDI_M0%%": cdi_oficial,
"%%JUROS_M0%%": juros_agro_oficial,
"%%DOLAR_M0%%": dolar_oficial,
"%%IPCA_M0%%": ipca_oficial,
"%%PIB_M0%%": pib_oficial,
"%%SOJA_M0%%": soja_hoje,
# Variação mês
"%%SELIC_VAR_MES%%": selic_var_mes,
"%%CDI_VAR_MES%%": cdi_var_mes,
"%%JUROS_VAR_MES%%": juros_var_mes,
"%%DOLAR_VAR_MES%%": dolar_var_mes,
"%%IPCA_VAR_MES%%": ipca_var_mes,
"%%PIB_VAR_MES%%": pib_var_mes,
"%%SOJA_VAR_MES%%": soja_var_mes,
# Variação ano
"%%SELIC_VAR_ANO%%": selic_var_ano,
"%%CDI_VAR_ANO%%": cdi_var_ano,
"%%JUROS_VAR_ANO%%": juros_var_ano,
"%%DOLAR_VAR_ANO%%": dolar_var_ano,
"%%IPCA_VAR_ANO%%": ipca_var_ano,
"%%PIB_VAR_ANO%%": pib_var_ano,
"%%SOJA_VAR_ANO%%": soja_var_ano,
# Projeções Focus
"%%SELIC_PROJ%%": projecoes_focus["selic"],
"%%CDI_PROJ%%": projecoes_focus["cdi"],
"%%JUROS_PROJ%%": projecoes_focus["juros"],
"%%DOLAR_PROJ%%": projecoes_focus["dolar"],
"%%IPCA_PROJ%%": projecoes_focus["ipca"],
"%%PIB_PROJ%%": projecoes_focus["pib"],
"%%SOJA_PROJ%%": soja_proj,
}

layout_finalizado = layout_base
for placeholder, value in replacements.items():
layout_finalizado = layout_finalizado.replace(placeholder, value)

# ==========================================
# Notícias: tenta Gemini, cai no fallback
# ==========================================
mapa_paises = {
"BRASIL": "BR", "ARGENTINA": "AR", "MEXICO": "MX", "COLOMBIA": "CO",
"URUGUAY": "UY", "PERU": "PE", "CHILE": "CL", "BOLIVIA": "BO", "PARAGUAY": "PY"
}
noticias_por_pais = {code: obter_noticias_fallback(code) for code in mapa_paises.values()}

prompt = """
Você é um analista especialista em inteligência de mercado de maquinário agrícola na América Latina.
Gere um objeto JSON contendo exatamente 4 notícias recentes e analíticas para CADA UM dos seguintes países:
BRASIL, ARGENTINA, CHILE, URUGUAY, PARAGUAY, PERU, BOLIVIA, MEXICO, COLOMBIA.

INSTRUÇÕES RÍGIDAS:
1. É PROIBIDO citar dados das safras 23/24.
2. Gere EXATAMENTE 4 notícias por país e EXATAMENTE 6 impactos por notícia.
3. Os segmentos de impacto devem ser sempre: "Tratores (<100cv)", "Tratores (100-200cv)", "Tratores (>200cv)", "Colheitadeiras", "Pulverizadores", "Plantadeiras".

Estrutura JSON obrigatória:
{
"BRASIL": [
{
"headline": "MANCHETE EM MAIUSCULAS",
"content": "Análise agro detalhada.",
"farol_cor": "verde",
"farol_texto": "Positive",
"source": "Fonte confiável",
"impacts": [
{"segment": "Tratores (<100cv)", "cor": "verde", "status": "Positive", "desc": "Descrição."},
{"segment": "Tratores (100-200cv)", "cor": "amarelo", "status": "Warning", "desc": "Descrição."},
{"segment": "Tratores (>200cv)", "cor": "vermelho", "status": "Critical", "desc": "Descrição."},
{"segment": "Colheitadeiras", "cor": "verde", "status": "Positive", "desc": "Descrição."},
{"segment": "Pulverizadores", "cor": "amarelo", "status": "Warning", "desc": "Descrição."},
{"segment": "Plantadeiras", "cor": "verde", "status": "Positive", "desc": "Descrição."}
]
}
]
}
Retorne APENAS o JSON, sem markdown, sem texto adicional.
"""

try:
print("A solicitar à IA o processamento estruturado das notícias via JSON...")
resposta_texto = chamar_gemini_api(prompt)
dados_noticias = json.loads(resposta_texto)
for chave_ia, pais_code in mapa_paises.items():
lista_cards = dados_noticias.get(chave_ia, [])
if isinstance(lista_cards, list) and len(lista_cards) == 4:
noticias_por_pais[pais_code] = "".join(
[construir_card_noticia(item) for item in lista_cards]
)
print(f" ✓ IA: {chave_ia} ({len(lista_cards)} notícias)")
except Exception as e:
print(f"Aviso: Usando banco de contingência. Erro Gemini: {e}")

# Injetar notícias no HTML com placeholders únicos e seguros
for code in mapa_paises.values():
placeholder = "%%NOTICIAS_{}%%".format(code)
layout_finalizado = layout_finalizado.replace(placeholder, noticias_por_pais[code])

output_path = "index.html"
with open(output_path, "w", encoding="utf-8") as f:
f.write(layout_finalizado.strip())

print(f"\n✅ Relatório gerado com sucesso: {output_path}")


if __name__ == "__main__":
gerar_relatorio()
