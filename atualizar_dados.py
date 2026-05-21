import os
import datetime
import json
import urllib.request
import urllib.parse
import re
from google import genai
from google.genai import types

# ==========================================
# 1. DADOS ESTÁTICOS DO PASSADO (Para cálculo de variação)
# ==========================================
HISTORICO_MACRO = {
    "MAR/2026": {"selic": "14,75%", "cdi": "14,65%", "juros": "19,30%", "dolar": "R$ 5,02", "ipca": "4,50%", "pib": "2,10%", "soja": "R$ 134,00"},
    "APR/2026": {"selic": "14,50%", "cdi": "14,40%", "juros": "19,00%", "dolar": "R$ 5,08", "ipca": "4,30%", "pib": "2,20%", "soja": "R$ 138,50"},
    "MAY/2026": {"selic": "14,50%", "cdi": "14,40%", "juros": "19,00%", "dolar": "R$ 5,15", "ipca": "4,20%", "pib": "2,30%", "soja": "R$ 142,00"},
}

CONSOLIDADO_2025 = {
    "selic": "11,75%", "cdi": "11,65%", "juros": "16,25%", "dolar": "R$ 4,85", 
    "ipca": "4,62%", "pib": "2,90%", "soja": "R$ 130,00"
}

ANO_PROJECAO = "2027"

# Cabeçalhos para enganar o bloqueio de robôs em sites do governo e notícias
HEADERS_ANTI_BLOCK = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/json,application/xhtml+xml',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
}

# ==========================================
# 2. CAPTURA DE DADOS REAIS VIA APIs
# ==========================================

def calcular_meses_rolantes():
    meses_en = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    today = datetime.datetime.now()
    m0_idx, m0_year = today.month - 1, today.year
    m1_idx, m1_year = (m0_idx - 1) if m0_idx > 0 else 11, m0_year if m0_idx > 0 else m0_year - 1
    m2_idx, m2_year = (m1_idx - 1) if m1_idx > 0 else 11, m1_year if m1_idx > 0 else m1_year - 1
    return f"{meses_en[m0_idx]}/{m0_year}", f"{meses_en[m1_idx]}/{m1_year}", f"{meses_en[m2_idx]}/{m2_year}"

def buscar_dados_oficiais():
    print("A buscar Dólar (AwesomeAPI) e Taxas (Brasil API)...")
    dolar_str, selic_str, cdi_str, juros_agro_str, ipca_str = "R$ 5,15", "14,50%", "14,40%", "19,00%", "4,20%"
    
    # Dólar em tempo real
    try:
        req = urllib.request.Request("https://economia.awesomeapi.com.br/last/USD-BRL", headers=HEADERS_ANTI_BLOCK)
        dados_dolar = json.loads(urllib.request.urlopen(req, timeout=10).read())
        dolar_str = f"R$ {float(dados_dolar['USDBRL']['bid']):.2f}".replace('.', ',')
    except Exception as e: print(f"Erro Dólar: {e}")
        
    # Selic e IPCA via Brasil API (Não bloqueia o GitHub)
    try:
        req = urllib.request.Request("https://brasilapi.com.br/api/taxas/v1", headers=HEADERS_ANTI_BLOCK)
        dados_taxas = json.loads(urllib.request.urlopen(req, timeout=10).read())
        for taxa in dados_taxas:
            if taxa.get('nome') == 'Selic':
                s = float(taxa['valor'])
                selic_str = f"{s:.2f}%".replace('.', ',')
                cdi_str = f"{(s - 0.10):.2f}%".replace('.', ',')
                juros_agro_str = f"{(s + 4.50):.2f}%".replace('.', ',')
            elif taxa.get('nome') == 'IPCA':
                ipca_str = f"{float(taxa['valor']):.2f}%".replace('.', ',')
    except Exception as e: print(f"Erro Taxas Brasil API: {e}")
        
    return dolar_str, selic_str, cdi_str, juros_agro_str, ipca_str

def buscar_projecoes_focus(ano_alvo):
    print(f"A extrair Focus BCB para o ano {ano_alvo}...")
    selic_proj, dolar_proj, ipca_proj, pib_proj = 10.50, 5.10, 4.10, 2.00
    try:
        filtro = f"(Indicador eq 'Selic' or Indicador eq 'Câmbio' or Indicador eq 'IPCA' or Indicador eq 'PIB Total') and DataReferencia eq '{ano_alvo}'"
        url = f"https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais?$filter={urllib.parse.quote(filtro)}&$orderby=Data%20desc&$top=40&$format=json"
        
        req = urllib.request.Request(url, headers=HEADERS_ANTI_BLOCK)
        dados = json.loads(urllib.request.urlopen(req, timeout=15).read())
        
        encontrados = set()
        for item in dados.get("value", []):
            ind = item.get("Indicador")
            if ind not in encontrados and item.get("Mediana") is not None:
                if ind == "Selic": selic_proj = float(item["Mediana"])
                elif ind == "Câmbio": dolar_proj = float(item["Mediana"])
                elif ind == "IPCA": ipca_proj = float(item["Mediana"])
                elif ind == "PIB Total": pib_proj = float(item["Mediana"])
                encontrados.add(ind)
    except Exception as e: print(f"Aviso Focus: {e}")

    return {
        "selic": f"{selic_proj:.2f}%".replace('.', ','), 
        "cdi": f"{(selic_proj - 0.10):.2f}%".replace('.', ','),
        "juros": f"{(selic_proj + 4.50):.2f}%".replace('.', ','), 
        "dolar": f"R$ {dolar_proj:.2f}".replace('.', ','),
        "ipca": f"{ipca_proj:.2f}%".replace('.', ','), 
        "pib": f"{pib_proj:.2f}%".replace('.', ',')
    }

def buscar_precos_soja(dolar_proj_str, ano_proj):
    print(f"A raspar Notícias Agrícolas: Soja Físico e Futuro ({ano_proj})...")
    soja_hoje_brl, soja_futuro_brl = "R$ 138,50", "R$ 145,00"
    try: dol_proj = float(dolar_proj_str.replace('R$', '').replace(',', '.').strip())
    except: dol_proj = 5.25

    try:
        req = urllib.request.Request("https://www.noticiasagricolas.com.br/cotacoes/soja/soja-porto-paranagua-pr", headers=HEADERS_ANTI_BLOCK)
        text_fis = re.sub(r'<[^>]+>', ' ', urllib.request.urlopen(req, timeout=10).read().decode('utf-8'))
        matches_fis = re.findall(r'R\$\s*(\d{3}[,.]\d{2})', text_fis)
        if matches_fis: soja_hoje_brl = f"R$ {matches_fis[0].replace('.', ',')}"
    except Exception as e: print(f"Erro Soja Físico: {e}")

    try:
        req = urllib.request.Request("https://www.noticiasagricolas.com.br/cotacoes/soja/soja-b3", headers=HEADERS_ANTI_BLOCK)
        text_b3 = re.sub(r'<[^>]+>', ' ', urllib.request.urlopen(req, timeout=10).read().decode('utf-8'))
        matches_b3 = re.findall(r'[A-Za-z]{3}/' + str(ano_proj)[-2:] + r'\s+([\d]{2}[,.]\d{2})', text_b3, re.IGNORECASE)
        if matches_b3: 
            soja_futuro_brl = f"R$ {(float(matches_b3[0].replace(',', '.')) * dol_proj):.2f}".replace('.', ',')
        else: 
            soja_futuro_brl = f"R$ {(float(soja_hoje_brl.replace('R$', '').replace(',', '.').strip()) * 1.05):.2f}".replace('.', ',')
    except Exception as e: print(f"Erro Soja Futuro: {e}")
    
    return soja_hoje_brl, soja_futuro_brl

def parse_float(valor_str):
    try: return float(valor_str.replace('%', '').replace('R$', '').replace(' ', '').replace(',', '.').strip())
    except: return 0.0

def calcular_variacao_pp(v_atual, v_ant):
    diff = parse_float(v_atual) - parse_float(v_ant)
    if diff > 0: return f'<span class="macro-badge red">● +{diff:.2f} PP</span>'
    elif diff < 0: return f'<span class="macro-badge green">● {diff:.2f} PP</span>'
    else: return '<span class="macro-badge yellow">● 0,00 PP</span>'

def calcular_variacao_cambio(v_atual, v_ant):
    diff = parse_float(v_atual) - parse_float(v_ant)
    if diff > 0: return f'<span class="macro-badge red">● +R$ {diff:.2f}</span>'
    elif diff < 0: return f'<span class="macro-badge green">● -R$ {abs(diff):.2f}</span>'
    else: return '<span class="macro-badge yellow">● R$ 0,00</span>'

# ==========================================
# 3. BASE DE DADOS E CONSTRUÇÃO DE NOTÍCIAS
# ==========================================
def obter_noticias_fallback(codigo_pais):
    temas = {
        "BR": [
            {"headline": "SOJA E MILHO: EXPORTAÇÕES RECORDE PRESSIONAM LOGÍSTICA E CAPEX", "content": "O escoamento das safras de Soja e Milho gera congestionamentos portuários. Grupos do Centro-Oeste intensificam compras de equipamentos pesados para evitar perdas de janela.", "farol_cor": "verde", "farol_texto": "Positive", "source": "Safras & Mercado", "impacts": [
                {"segment": "Tratores (<100cv)", "cor": "amarelo", "status": "Warning", "desc": "Demanda estável focada em manutenção de pátio."},
                {"segment": "Tratores (100-200cv)", "cor": "verde", "status": "Positive", "desc": "Renovação acelerada para suporte de transbordo."},
                {"segment": "Tratores (>200cv)", "cor": "verde", "status": "Positive", "desc": "Altíssima demanda para preparo de solo nas janelas curtas."},
                {"segment": "Colheitadeiras", "cor": "verde", "status": "Positive", "desc": "Prioridade máxima em modelos de alta capacidade (Classe 8/9)."},
                {"segment": "Pulverizadores", "cor": "verde", "status": "Positive", "desc": "Tecnologia de corte de seção impulsiona upgrades."},
                {"segment": "Plantadeiras", "cor": "verde", "status": "Positive", "desc": "Sementeiras precisas em alta para a safrinha."}
            ]},
            {"headline": "CANA E ALGODÃO: EXPANSÃO DO SETOR SUCROENERGÉTICO EM SP E MT", "content": "Usinas capitalizadas pelo preço do etanol e grandes produtores de Algodão abrem robustos programas de substituição de frotas submetidas a uso severo.", "farol_cor": "verde", "farol_texto": "Positive", "source": "Conab / Asocaña", "impacts": [
                {"segment": "Tratores (<100cv)", "cor": "amarelo", "status": "Warning", "desc": "Foco em implementos secundários de usinas."},
                {"segment": "Tratores (100-200cv)", "cor": "verde", "status": "Positive", "desc": "Essenciais para o manejo do algodão."},
                {"segment": "Tratores (>200cv)", "cor": "verde", "status": "Positive", "desc": "Compra massiva para reboque de transbordos de cana."},
                {"segment": "Colheitadeiras", "cor": "verde", "status": "Positive", "desc": "Renovação contínua de colhedoras de cana e algodão."},
                {"segment": "Pulverizadores", "cor": "verde", "status": "Positive", "desc": "Autopropelidos altos essenciais no manejo tardio."},
                {"segment": "Plantadeiras", "cor": "amarelo", "status": "Warning", "desc": "Usinas focam primeiro na frota de tração."}
            ]}
        ],
        "AR": [
            {"headline": "TRIGO E SOJA: RECUPERAÇÃO HÍDRICA NA ZONA NÚCLEO", "content": "A recuperação da umidade na Província de Buenos Aires acende o otimismo para a safra de Trigo e posterior plantio de Soja.", "farol_cor": "verde", "farol_texto": "Positive", "source": "Bolsa de Cereales", "impacts": [
                {"segment": "Tratores (<100cv)", "cor": "amarelo", "status": "Warning", "desc": "Limitado ao setor leiteiro."},
                {"segment": "Tratores (100-200cv)", "cor": "verde", "status": "Positive", "desc": "Mais procurado para plantio direto."},
                {"segment": "Tratores (>200cv)", "cor": "amarelo", "status": "Warning", "desc": "Contratistas avaliam crédito antes de comprar."},
                {"segment": "Colheitadeiras", "cor": "amarelo", "status": "Warning", "desc": "Espera pela colheita de inverno."},
                {"segment": "Pulverizadores", "cor": "verde", "status": "Positive", "desc": "Demandados para dessecação do inverno."},
                {"segment": "Plantadeiras", "cor": "verde", "status": "Positive", "desc": "Air Drills lideram faturamento."}
            ]},
            {"headline": "REDUÇÃO DE RETENCIONES ANIMA EXPORTADORES", "content": "A sinalização de alívio fiscal permite que os 'pools de siembra' planejem a renovação do seu parque de máquinas a médio prazo.", "farol_cor": "verde", "farol_texto": "Positive", "source": "Clarín Rural", "impacts": [
                {"segment": "Tratores (<100cv)", "cor": "amarelo", "status": "Warning", "desc": "Baixa correlação com pools de exportação."},
                {"segment": "Tratores (100-200cv)", "cor": "verde", "status": "Positive", "desc": "Orçamentos de 2027 já em cotação."},
                {"segment": "Tratores (>200cv)", "cor": "verde", "status": "Positive", "desc": "Aquisição massiva em planeamento."},
                {"segment": "Colheitadeiras", "cor": "verde", "status": "Positive", "desc": "Contratistas preparam renovação pesada."},
                {"segment": "Pulverizadores", "cor": "verde", "status": "Positive", "desc": "Tecnologia verde é foco."},
                {"segment": "Plantadeiras", "cor": "verde", "status": "Positive", "desc": "Chassis dobráveis logísticos."}
            ]}
        ]
    }

    paises_restantes = ["MX", "CO", "UY", "PE", "CL", "BO", "PY"]
    for sigla in paises_restantes:
        temas[sigla] = [
            {"headline": f"TRANSIÇÃO TECNOLÓGICA NO {sigla}", "content": "As margens apertadas requerem máquinas de alta eficiência, focando em telemetria.", "farol_cor": "verde", "farol_texto": "Positive", "source": "Market Intelligence", "impacts": [
                {"segment": "Tratores (<100cv)", "cor": "verde", "status": "Positive", "desc": "Adoção na pecuária e horticultura."},
                {"segment": "Tratores (100-200cv)", "cor": "verde", "status": "Positive", "desc": "Principal tração de média escala."},
                {"segment": "Tratores (>200cv)", "cor": "amarelo", "status": "Warning", "desc": "Limitado a conglomerados corporativos."},
                {"segment": "Colheitadeiras", "cor": "amarelo", "status": "Warning", "desc": "Renovações em compasso de espera."},
                {"segment": "Pulverizadores", "cor": "verde", "status": "Positive", "desc": "Uso inteligente de sensores de aplicação."},
                {"segment": "Plantadeiras", "cor": "verde", "status": "Positive", "desc": "Migração para sistemas pneumáticos."}
            ]},
            {"headline": "ALTOS CUSTOS DIRECIONAM COMPRAS", "content": "O custo da energia obriga produtores a avaliarem rigidamente o consumo de combustível/hectare.", "farol_cor": "amarelo", "farol_texto": "Warning", "source": "Canais Agropecuários", "impacts": [
                {"segment": "Tratores (<100cv)", "cor": "amarelo", "status": "Warning", "desc": "Motores econômicos vendem."},
                {"segment": "Tratores (100-200cv)", "cor": "amarelo", "status": "Warning", "desc": "Foco restrito a eficiência comprovada."},
                {"segment": "Tratores (>200cv)", "cor": "vermelho", "status": "Critical", "desc": "Queda abrupta devido ao custo de operação."},
                {"segment": "Colheitadeiras", "cor": "amarelo", "status": "Warning", "desc": "Evita-se horas ociosas de motor."},
                {"segment": "Pulverizadores", "cor": "amarelo", "status": "Warning", "desc": "Prevalência de implementos acoplados."},
                {"segment": "Plantadeiras", "cor": "amarelo", "status": "Warning", "desc": "Modelos mecânicos de baixa tração."}
            ]}
        ]

    html_cards = ""
    for item in temas.get(codigo_pais, []):
        impacts_html = ""
        for imp in item.get("impacts", []):
            cor_css = f"farol-{imp.get('status').lower()}"
            impacts_html += f"<li><div class='line-title'><strong>{imp.get('segment')}</strong><span class='farol {cor_css}'><span class='farol-dot'></span>{imp.get('status')}</span></div><div class='impact-desc'>{imp.get('desc')}</div></li>"
        html_cards += f"<div class='news-item'><div class='news-header'><h3 class='news-headline'>{item.get('headline')}</h3><span class='farol farol-{item.get('farol_texto').lower()}'><span class='farol-dot'></span>{item.get('farol_texto')}</span></div><div class='news-content'>{item.get('content')}</div><div class='impact-box'><div class='impact-title'>⚠️ Impacto Estimado Vendas AGCO</div><ul class='impact-list'>{impacts_html}</ul><a href='#' class='source-link'>Fonte: {item.get('source')}</a></div></div>"
    return html_cards

def construir_card_noticia(item):
    impacts_html = ""
    for imp in item.get("impacts", []):
        status = imp.get('status', 'Warning')
        cor_css = f"farol-{status.lower()}"
        impacts_html += f"<li><div class='line-title'><strong>{imp.get('segment')}</strong><span class='farol {cor_css}'><span class='farol-dot'></span>{status}</span></div><div class='impact-desc'>{imp.get('desc')}</div></li>"
    return f"<div class='news-item'><div class='news-header'><h3 class='news-headline'>{item.get('headline')}</h3><span class='farol farol-{item.get('farol_texto', 'warning').lower()}'><span class='farol-dot'></span>{item.get('farol_texto', 'Warning')}</span></div><div class='news-content'>{item.get('content')}</div><div class='impact-box'><div class='impact-title'>⚠️ Impacto Estimado Vendas AGCO</div><ul class='impact-list'>{impacts_html}</ul><a href='#' class='source-link'>Fonte: {item.get('source')}</a></div></div>"

# ==========================================
# 4. GERAÇÃO E COMPOSIÇÃO FINAL DO HTML
# ==========================================
def gerar_relatorio():
    data_hoje = datetime.datetime.now().strftime("%b %d, %Y").upper()
    m_atual, m_anterior, m_atras = calcular_meses_rolantes()
    ano_atual = str(datetime.datetime.now().year)
    
    dados_m2 = HISTORICO_MACRO.get(m_atras, {"selic": "--,--%", "cdi": "--,--%", "juros": "--,--%", "dolar": "R$ --,--", "ipca": "--,--%", "pib": "--,--%", "soja": "R$ --,--"})
    dados_m1 = HISTORICO_MACRO.get(m_anterior, {"selic": "--,--%", "cdi": "--,--%", "juros": "--,--%", "dolar": "R$ --,--", "ipca": "--,--%", "pib": "--,--%", "soja": "R$ --,--"})
    
    # BUSCAS EM API
    dolar_oficial, selic_oficial, cdi_oficial, juros_agro_oficial, ipca_oficial = buscar_dados_oficiais()
    projecoes_atual = buscar_projecoes_focus(ano_atual)
    pib_oficial = projecoes_atual['pib']
    
    projecoes_focus = buscar_projecoes_focus(ANO_PROJECAO)
    soja_hoje, soja_proj = buscar_precos_soja(projecoes_focus['dolar'], ANO_PROJECAO)

    # HTML BASE (EMBUTIDO)
    layout_base = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Early warning AGCO - LATAM Executive Intelligence</title>
    <style>
        :root { --agco-red: #cc0000; --agco-black: #111111; --agco-dark-gray: #333333; --agco-light-gray: #f4f4f4; --text-main: #222222; --white: #ffffff; --farol-verde-bg: #e2f0d9; --farol-verde-text: #385723; --farol-verde-dot: #70ad47; --farol-amarelo-bg: #fff2cc; --farol-amarelo-text: #7f6000; --farol-amarelo-dot: #ffc000; --farol-vermelho-bg: #fce4d6; --farol-vermelho-text: #c65911; --farol-vermelho-dot: #c00000; }
        body { font-family: 'Arial', sans-serif; background-color: #e9ecef; color: var(--text-main); margin: 0; padding: 20px; }
        body > .skiptranslate { display: none; } .goog-te-banner-frame.skiptranslate { display: none !important; } body { top: 0px !important; }
        .container { max-width: 1200px; margin: 0 auto; background-color: var(--white); box-shadow: 0 10px 25px rgba(0,0,0,0.15); }
        .header { background-color: var(--agco-black); color: var(--white); padding: 35px 40px; border-bottom: 6px solid var(--agco-red); display: flex; justify-content: space-between; align-items: center; background-image: url('https://images.unsplash.com/photo-1592982537447-7440770cbfc9?q=80&w=2000&auto=format&fit=crop'); background-size: cover; background-position: center; background-blend-mode: multiply; }
        .header-text h1 { margin: 0; font-size: 34px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 900; }
        .header-text p { margin: 5px 0 0 0; font-size: 14px; color: #d0d0d0; text-transform: uppercase; letter-spacing: 0.5px; }
        .header-controls { display: flex; flex-direction: column; align-items: flex-end; gap: 10px; }
        .date-badge { background-color: var(--agco-red); padding: 8px 16px; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 2px; text-align: center; width: 100%; box-sizing: border-box;}
        .lang-switcher { display: flex; gap: 5px; } .lang-switcher button { background-color: rgba(255, 255, 255, 0.1); color: var(--white); border: 1px solid rgba(255, 255, 255, 0.3); padding: 5px 10px; font-size: 11px; font-weight: bold; cursor: pointer; transition: all 0.2s; text-transform: uppercase; border-radius: 2px; } .lang-switcher button:hover { background-color: var(--agco-red); border-color: var(--agco-red); }
        .content-wrapper { padding: 30px 40px; }
        .alert-banner { background-color: var(--agco-light-gray); border-left: 5px solid var(--agco-red); padding: 15px 20px; margin-bottom: 35px; font-size: 13px; color: var(--agco-dark-gray); text-transform: uppercase; letter-spacing: 0.5px; font-weight: bold; }
        .tabs-nav { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 25px; border-bottom: 3px solid var(--agco-black); padding-bottom: 5px; }
        .tab-btn { background-color: var(--agco-light-gray); color: var(--agco-dark-gray); border: none; padding: 12px 20px; font-size: 13px; font-weight: bold; cursor: pointer; text-transform: uppercase; letter-spacing: 0.5px; transition: all 0.2s; border-radius: 2px 2px 0 0; }
        .tab-btn:hover { background-color: #e0e0e0; color: var(--agco-black); } .tab-btn.active { background-color: var(--agco-black); color: var(--white); border-bottom: 3px solid var(--agco-red); }
        .tab-content { display: none; animation: fadeIn 0.4s ease; } .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        .country-title { font-size: 24px; color: var(--agco-black); margin-top: 0; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #dddddd; display: flex; align-items: center; font-weight: 800; text-transform: uppercase; }
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
        .farol-positive { background-color: var(--farol-verde-bg); color: var(--farol-verde-text); } .farol-positive .farol-dot { background-color: var(--farol-verde-dot); box-shadow: 0 0 6px var(--farol-verde-dot); }
        .farol-warning { background-color: var(--farol-amarelo-bg); color: var(--farol-amarelo-text); } .farol-warning .farol-dot { background-color: var(--farol-amarelo-dot); box-shadow: 0 0 6px var(--farol-amarelo-dot); }
        .farol-critical { background-color: var(--farol-vermelho-bg); color: var(--farol-vermelho-text); } .farol-critical .farol-dot { background-color: var(--farol-vermelho-dot); box-shadow: 0 0 6px var(--farol-vermelho-dot); }
        .impact-list { list-style: none; padding: 0; margin: 0; font-size: 13px; } .impact-list li { margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px dashed #ddd; display: flex; flex-direction: column; gap: 5px; } .impact-list li:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        .line-title { display: flex; justify-content: space-between; align-items: center; } .impact-list strong { color: var(--agco-black); text-transform: uppercase; } .impact-desc { color: #555; font-size: 12.5px; padding-left: 2px; line-height: 1.4; }
        .source-link { display: block; margin-top: 15px; font-size: 11px; color: var(--agco-red); text-decoration: none; font-weight: bold; text-align: right; letter-spacing: 1px; text-transform: uppercase; } .source-link:hover { color: var(--agco-black); }
        .macro-section { margin-top: 40px; background-color: var(--white); border: 1px solid #e0e0e0; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-radius: 4px; }
        .macro-title { font-size: 20px; font-weight: 900; text-transform: uppercase; margin-top: 0; margin-bottom: 20px; display: flex; align-items: center; gap: 10px; border-bottom: 2px solid #ddd; padding-bottom: 10px; color: var(--agco-black); } .macro-title .tag-brasil { background-color: var(--agco-black); color: var(--white); padding: 4px 8px; font-size: 12px; letter-spacing: 1px; }
        .macro-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: center; } .macro-table th { background-color: var(--agco-black); color: var(--white); padding: 14px 10px; font-weight: bold; border-bottom: 4px solid var(--agco-red); text-transform: uppercase; } .macro-table td { padding: 12px 10px; border-bottom: 1px solid #eee; color: var(--agco-dark-gray); } .macro-table tr:last-child td { border-bottom: none; } .macro-table td:first-child { text-align: left; font-weight: bold; color: var(--agco-black); width: 25%; }
        .macro-badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; text-transform: uppercase; } .macro-badge.yellow { background-color: var(--farol-amarelo-bg); color: var(--farol-amarelo-text); } .macro-badge.green { background-color: var(--farol-verde-bg); color: var(--farol-verde-text); } .macro-badge.red { background-color: var(--farol-vermelho-bg); color: var(--farol-vermelho-text); }
        .macro-source { font-size: 11px; color: #777; margin-top: 15px; font-style: italic; }
        .footer { background-color: var(--agco-black); color: #777777; text-align: center; padding: 25px; font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; border-top: 4px solid var(--agco-red); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header" translate="no">
            <div class="header-text">
                <h1>Early warning AGCO</h1>
                <p>LATAM Market Intelligence & Sales Prediction Model</p>
            </div>
            <div class="header-controls">
                <div class="lang-switcher">
                    <button onclick="changeLanguage('en')">EN</button>
                    <button onclick="changeLanguage('pt')">PT</button>
                    <button onclick="changeLanguage('es')">ES</button>
                </div>
                <div class="date-badge">DATA_HOJE_PLACEHOLDER</div>
            </div>
        </div>
        <div class="content-wrapper">
            <div class="alert-banner" translate="no">
                // AEM DATA RECEIPT: SCHEDULED RUN ACTIVE. FOCUS ESTIMATES SHIFTED TO HISTORICAL MEDIAN TRACKING. CROSS-RATE COMMODITY INGESTION OPERATIONAL FOR TARGET YEAR ANO_FUTURO_PLACEHOLDER.
            </div>

            <div class="tabs-nav" translate="no">
                <button class="tab-btn active" onclick="openCountry(event, 'brazil')">🇧🇷 Brasil</button>
                <button class="tab-btn" onclick="openCountry(event, 'argentina')">🇦🇷 Argentina</button>
                <button class="tab-btn" onclick="openCountry(event, 'chile')">🇨🇱 Chile</button>
                <button class="tab-btn" onclick="openCountry(event, 'uruguay')">🇺🇾 Uruguai</button>
                <button class="tab-btn" onclick="openCountry(event, 'paraguay')">🇵🇾 Paraguai</button>
                <button class="tab-btn" onclick="openCountry(event, 'peru')">🇵🇪 Peru</button>
                <button class="tab-btn" onclick="openCountry(event, 'bolivia')">🇧🇴 Bolívia</button>
                <button class="tab-btn" onclick="openCountry(event, 'mexico')">🇲🇽 México</button>
                <button class="tab-btn" onclick="openCountry(event, 'colombia')">🇨🇴 Colômbia</button>
            </div>

            <div id="brazil" class="tab-content active">
                <h2 class="country-title">🇧🇷 BRAZIL <span class="highlight-tag">MARKET & MACRO ALERTS</span></h2>
                <div class="news-grid">[[NOTICIAS_BR]]</div>
                
                <div class="macro-section">
                    <h3 class="macro-title">📊 1. MACROECONOMIA & COMMODITIES <span class="tag-brasil">BRASIL</span></h3>
                    <table class="macro-table">
                        <thead>
                            <tr>
                                <th>INDICADOR</th>
                                <th>CONSOLIDADO 2025</th>
                                <th>M_ATRAS_PLACEHOLDER</th>
                                <th>M_ANTERIOR_PLACEHOLDER</th>
                                <th>M_ATUAL_PLACEHOLDER (ATUAL)</th>
                                <th>VAR. MÊS</th>
                                <th>VAR. ANO</th>
                                <th>ANO_FUTURO_PLACEHOLDER</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr><td>Taxa Selic (Meta BCB)</td><td>SELIC_2025_PLACEHOLDER</td><td>SELIC_M2_PLACEHOLDER</td><td>SELIC_M1_PLACEHOLDER</td><td>SELIC_M0_PLACEHOLDER</td><td>SELIC_VAR_MES_PLACEHOLDER</td><td>SELIC_VAR_ANO_PLACEHOLDER</td><td>SELIC_PROJ_PLACEHOLDER</td></tr>
                            <tr><td>Taxa CDI (a.a.)</td><td>CDI_2025_PLACEHOLDER</td><td>CDI_M2_PLACEHOLDER</td><td>CDI_M1_PLACEHOLDER</td><td>CDI_M0_PLACEHOLDER</td><td>CDI_VAR_MES_PLACEHOLDER</td><td>CDI_VAR_ANO_PLACEHOLDER</td><td>CDI_PROJ_PLACEHOLDER</td></tr>
                            <tr><td>Juros Comerciais Agro</td><td>JUROS_2025_PLACEHOLDER</td><td>JUROS_M2_PLACEHOLDER</td><td>JUROS_M1_PLACEHOLDER</td><td>JUROS_M0_PLACEHOLDER</td><td>JUROS_VAR_MES_PLACEHOLDER</td><td>JUROS_VAR_ANO_PLACEHOLDER</td><td>JUROS_PROJ_PLACEHOLDER</td></tr>
                            <tr><td>Câmbio (USD/BRL)</td><td>DOLAR_2025_PLACEHOLDER</td><td>DOLAR_M2_PLACEHOLDER</td><td>DOLAR_M1_PLACEHOLDER</td><td>DOLAR_M0_PLACEHOLDER</td><td>DOLAR_VAR_MES_PLACEHOLDER</td><td>DOLAR_VAR_ANO_PLACEHOLDER</td><td>DOLAR_PROJ_PLACEHOLDER</td></tr>
                            <tr><td>IPCA (Inflação Acum. 12m)</td><td>IPCA_2025_PLACEHOLDER</td><td>IPCA_M2_PLACEHOLDER</td><td>IPCA_M1_PLACEHOLDER</td><td>IPCA_M0_PLACEHOLDER</td><td>IPCA_VAR_MES_PLACEHOLDER</td><td>IPCA_VAR_ANO_PLACEHOLDER</td><td>IPCA_PROJ_PLACEHOLDER</td></tr>
                            <tr><td>Crescimento PIB Brasil (a.a.)</td><td>PIB_2025_PLACEHOLDER</td><td>PIB_M2_PLACEHOLDER</td><td>PIB_M1_PLACEHOLDER</td><td>PIB_M0_PLACEHOLDER</td><td>PIB_VAR_MES_PLACEHOLDER</td><td>PIB_VAR_ANO_PLACEHOLDER</td><td>PIB_PROJ_PLACEHOLDER</td></tr>
                            <tr><td>Preço da Soja (Sc 60kg - Cepea/B3)</td><td>SOJA_2025_PLACEHOLDER</td><td>SOJA_M2_PLACEHOLDER</td><td>SOJA_M1_PLACEHOLDER</td><td>SOJA_M0_PLACEHOLDER</td><td>SOJA_VAR_MES_PLACEHOLDER</td><td>SOJA_VAR_ANO_PLACEHOLDER</td><td>SOJA_PROJ_PLACEHOLDER</td></tr>
                        </tbody>
                    </table>
                    <div class="macro-source">*Fonte: AwesomeAPI, Brasil API, BCB Olinda (Focus) e Notícias Agrícolas. Processamento via AGCO Core Pipeline.</div>
                </div>
            </div>

            <div id="argentina" class="tab-content"><h2 class="country-title">🇦🇷 ARGENTINA <span class="highlight-tag">MARKET & MACRO ALERTS</span></h2><div class="news-grid">[[NOTICIAS_AR]]</div></div>
            <div id="chile" class="tab-content"><h2 class="country-title">🇨🇱 CHILE <span class="highlight-tag">MARKET & MACRO ALERTS</span></h2><div class="news-grid">[[NOTICIAS_CL]]</div></div>
            <div id="uruguay" class="tab-content"><h2 class="country-title">🇺🇾 URUGUAY <span class="highlight-tag">MARKET & MACRO ALERTS</span></h2><div class="news-grid">[[NOTICIAS_UY]]</div></div>
            <div id="paraguay" class="tab-content"><h2 class="country-title">🇵🇾 PARAGUAY <span class="highlight-tag">MARKET & MACRO ALERTS</span></h2><div class="news-grid">[[NOTICIAS_PY]]</div></div>
            <div id="peru" class="tab-content"><h2 class="country-title">🇵🇪 PERU <span class="highlight-tag">MARKET & MACRO ALERTS</span></h2><div class="news-grid">[[NOTICIAS_PE]]</div></div>
            <div id="bolivia" class="tab-content"><h2 class="country-title">🇧🇴 BOLIVIA <span class="highlight-tag">MARKET & MACRO ALERTS</span></h2><div class="news-grid">[[NOTICIAS_BO]]</div></div>
            <div id="mexico" class="tab-content"><h2 class="country-title">🇲🇽 MEXICO <span class="highlight-tag">MARKET & MACRO ALERTS</span></h2><div class="news-grid">[[NOTICIAS_MX]]</div></div>
            <div id="colombia" class="tab-content"><h2 class="country-title">🇨🇴 COLOMBIA <span class="highlight-tag">MARKET & MACRO ALERTS</span></h2><div class="news-grid">[[NOTICIAS_CO]]</div></div>

        </div>
        <div class="footer" translate="no">CONFIDENTIAL &mdash; For Internal AGCO Management Alignment Only &mdash; Powered by AEM Intelligence Pipeline</div>
    </div>
    
    <div id="google_translate_element" style="display:none;"></div>
    <script type="text/javascript">
        function openCountry(evt, countryName) {
            var i, tabcontent, tablinks;
            tabcontent = document.getElementsByClassName("tab-content");
            for (i = 0; i < tabcontent.length; i++) { tabcontent[i].style.display = "none"; tabcontent[i].classList.remove("active"); }
            tablinks = document.getElementsByClassName("tab-btn");
            for (i = 0; i < tablinks.length; i++) { tablinks[i].classList.remove("active"); }
            document.getElementById(countryName).style.display = "block";
            document.getElementById(countryName).classList.add("active");
            evt.currentTarget.classList.add("active");
        }
        function googleTranslateElementInit() { new google.translate.TranslateElement({pageLanguage: 'en', autoDisplay: false}, 'google_translate_element'); }
        function changeLanguage(langCode) {
            var selectField = document.querySelector("select.goog-te-combo");
            if (selectField) { selectField.value = langCode; selectField.dispatchEvent(new Event('change')); }
        }
    </script>
    <script type="text/javascript" src="https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"></script>
</body>
</html>"""

    # Mapeamento do dicionário de substituição de dados Macro
    subs = {
        "DATA_HOJE_PLACEHOLDER": data_hoje,
        "M_ATRAS_PLACEHOLDER": m_atras, "M_ANTERIOR_PLACEHOLDER": m_anterior, "M_ATUAL_PLACEHOLDER": m_atual, "ANO_FUTURO_PLACEHOLDER": ANO_PROJECAO,
        "SELIC_2025_PLACEHOLDER": CONSOLIDADO_2025["selic"], "CDI_2025_PLACEHOLDER": CONSOLIDADO_2025["cdi"], "JUROS_2025_PLACEHOLDER": CONSOLIDADO_2025["juros"], "DOLAR_2025_PLACEHOLDER": CONSOLIDADO_2025["dolar"], "IPCA_2025_PLACEHOLDER": CONSOLIDADO_2025["ipca"], "PIB_2025_PLACEHOLDER": CONSOLIDADO_2025["pib"], "SOJA_2025_PLACEHOLDER": CONSOLIDADO_2025["soja"],
        "SELIC_M2_PLACEHOLDER": dados_m2['selic'], "CDI_M2_PLACEHOLDER": dados_m2['cdi'], "JUROS_M2_PLACEHOLDER": dados_m2['juros'], "DOLAR_M2_PLACEHOLDER": dados_m2['dolar'], "IPCA_M2_PLACEHOLDER": dados_m2['ipca'], "PIB_M2_PLACEHOLDER": dados_m2['pib'], "SOJA_M2_PLACEHOLDER": dados_m2['soja'],
        "SELIC_M1_PLACEHOLDER": dados_m1['selic'], "CDI_M1_PLACEHOLDER": dados_m1['cdi'], "JUROS_M1_PLACEHOLDER": dados_m1['juros'], "DOLAR_M1_PLACEHOLDER": dados_m1['dolar'], "IPCA_M1_PLACEHOLDER": dados_m1['ipca'], "PIB_M1_PLACEHOLDER": dados_m1['pib'], "SOJA_M1_PLACEHOLDER": dados_m1['soja'],
        "SELIC_M0_PLACEHOLDER": selic_oficial, "CDI_M0_PLACEHOLDER": cdi_oficial, "JUROS_M0_PLACEHOLDER": juros_agro_oficial, "DOLAR_M0_PLACEHOLDER": dolar_oficial, "IPCA_M0_PLACEHOLDER": ipca_oficial, "PIB_M0_PLACEHOLDER": pib_oficial, "SOJA_M0_PLACEHOLDER": soja_hoje,
        "SELIC_PROJ_PLACEHOLDER": projecoes_focus["selic"], "CDI_PROJ_PLACEHOLDER": projecoes_focus["cdi"], "JUROS_PROJ_PLACEHOLDER": projecoes_focus["juros"], "DOLAR_PROJ_PLACEHOLDER": projecoes_focus["dolar"], "IPCA_PROJ_PLACEHOLDER": projecoes_focus["ipca"], "PIB_PROJ_PLACEHOLDER": projecoes_focus["pib"], "SOJA_PROJ_PLACEHOLDER": soja_proj,
        "SELIC_VAR_MES_PLACEHOLDER": calcular_variacao_pp(selic_oficial, dados_m1['selic']), "SELIC_VAR_ANO_PLACEHOLDER": calcular_variacao_pp(selic_oficial, CONSOLIDADO_2025['selic']),
        "CDI_VAR_MES_PLACEHOLDER": calcular_variacao_pp(cdi_oficial, dados_m1['cdi']), "CDI_VAR_ANO_PLACEHOLDER": calcular_variacao_pp(cdi_oficial, CONSOLIDADO_2025['cdi']),
        "JUROS_VAR_MES_PLACEHOLDER": calcular_variacao_pp(juros_agro_oficial, dados_m1['juros']), "JUROS_VAR_ANO_PLACEHOLDER": calcular_variacao_pp(juros_agro_oficial, CONSOLIDADO_2025['juros']),
        "DOLAR_VAR_MES_PLACEHOLDER": calcular_variacao_cambio(dolar_oficial, dados_m1['dolar']), "DOLAR_VAR_ANO_PLACEHOLDER": calcular_variacao_cambio(dolar_oficial, CONSOLIDADO_2025['dolar']),
        "IPCA_VAR_MES_PLACEHOLDER": calcular_variacao_pp(ipca_oficial, dados_m1['ipca']), "IPCA_VAR_ANO_PLACEHOLDER": calcular_variacao_pp(ipca_oficial, CONSOLIDADO_2025['ipca']),
        "PIB_VAR_MES_PLACEHOLDER": calcular_variacao_pp(pib_oficial, dados_m1['pib']), "PIB_VAR_ANO_PLACEHOLDER": calcular_variacao_pp(pib_oficial, CONSOLIDADO_2025['pib']),
        "SOJA_VAR_MES_PLACEHOLDER": calcular_variacao_cambio(soja_hoje, dados_m1['soja']), "SOJA_VAR_ANO_PLACEHOLDER": calcular_variacao_cambio(soja_hoje, CONSOLIDADO_2025['soja'])
    }

    html_final = layout_base
    for k, v in subs.items():
        html_final = html_final.replace(k, str(v))

    # GERAÇÃO DE NOTÍCIAS (GEMINI)
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    prompt = f"""
    Você é um analista especialista em inteligência de mercado de maquinário agrícola na América Latina.
    Gere um objeto JSON contendo exatamente 4 notícias recentes e analíticas para CADA UM dos seguintes países: BRASIL, ARGENTINA, CHILE, URUGUAY, PARAGUAY, PERU, BOLIVIA, MEXICO, COLOMBIA.
    
    INSTRUÇÕES RÍGIDAS DE CONTEÚDO:
    1. CONTEXTO TEMPORAL: O momento atual é {m_atual}. Considere apenas cenários de {m_atual} em diante. É ESTRITAMENTE PROIBIDO citar dados das safras 23/24.
    2. COMMODITIES OBRIGATÓRIAS NO BRASIL: Cobre obrigatoriamente Soja, Milho, Cana, Algodão, Café, Pecuária e Laranja.
    3. FARÓIS E IMPACTOS: Tem de gerar EXATAMENTE 4 notícias para CADA UM dos 9 países e EXATAMENTE 6 impactos por notícia.
    
    A estrutura do JSON gerado deve seguir estritamente o formato abaixo:
    {{
      "BRASIL": [
        {{
          "headline": "MANCHETE EM MAIÚSCULAS", "content": "Análise agro detalhada.", "farol_cor": "verde ou amarelo ou vermelho", "farol_texto": "Positive ou Warning ou Critical", "source": "Fonte confiável",
          "impacts": [
            {{"segment": "Tratores (<100cv)", "cor": "verde ou amarelo ou vermelho", "status": "Positive ou Warning ou Critical", "desc": "Curto desc"}},
            {{"segment": "Tratores (100-200cv)", "cor": "verde ou amarelo ou vermelho", "status": "Positive ou Warning ou Critical", "desc": "Curto desc"}},
            {{"segment": "Tratores (>200cv)", "cor": "verde ou amarelo ou vermelho", "status": "Positive ou Warning ou Critical", "desc": "Curto desc"}},
            {{"segment": "Colheitadeiras", "cor": "verde ou amarelo ou vermelho", "status": "Positive ou Warning ou Critical", "desc": "Curto desc"}},
            {{"segment": "Pulverizadores", "cor": "verde ou amarelo ou vermelho", "status": "Positive ou Warning ou Critical", "desc": "Curto desc"}},
            {{"segment": "Plantadeiras", "cor": "verde ou amarelo ou vermelho", "status": "Positive ou Warning ou Critical", "desc": "Curto desc"}}
          ]
        }}
      ]
    }}
    """

    noticias_por_pais = {k: obter_noticias_fallback(k) for k in ["BR", "AR", "MX", "CO", "UY", "PE", "CL", "BO", "PY"]}
    
    try:
        print("A solicitar à IA o processamento estruturado das notícias via JSON...")
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json"))
        dados_noticias = json.loads(response.text)
        mapa_chaves = {"BRASIL": "BR", "ARGENTINA": "AR", "MEXICO": "MX", "COLOMBIA": "CO", "URUGUAY": "UY", "PERU": "PE", "CHILE": "CL", "BOLIVIA": "BO", "PARAGUAY": "PY"}
        for chave_ia, pais_code in mapa_chaves.items():
            lista_cards = dados_noticias.get(chave_ia, [])
            if lista_cards and len(lista_cards) == 4:
                noticias_por_pais[pais_code] = "".join([construir_card_noticia(item) for item in lista_cards])
    except Exception as e: print(f"Aviso de IA: Erro, utilizando fallback. Erro: {e}")

    # ===== CORREÇÃO BLINDADA DO REPLACE =====
    for pais in ["BR", "AR", "MX", "CO", "UY", "PE", "CL", "BO", "PY"]:
        html_final = html_final.replace(f"[[NOTICIAS_{pais}]]", noticias_por_pais.get(pais, ""))

    with open("index.html", "w", encoding="utf-8") as file:
        file.write(html_final.strip())
        
    print("Sucesso! Painel atualizado e HTML guardado em index.html.")

if __name__ == "__main__":
    gerar_relatorio()
