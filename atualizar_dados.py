import os
import datetime
import json
import urllib.request
import urllib.parse
import re
from google import genai
from google.genai import types

# ==========================================
# 1. DADOS DE HISTÓRICO
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

# ==========================================
# 2. FUNÇÕES DE DADOS (API & SCRAPING)
# ==========================================

def calcular_meses_rolantes():
    meses_en = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    today = datetime.datetime.now()
    m0_idx, m0_year = today.month - 1, today.year
    m1_idx, m1_year = (m0_idx - 1) if m0_idx > 0 else 11, m0_year if m0_idx > 0 else m0_year - 1
    m2_idx, m2_year = (m1_idx - 1) if m1_idx > 0 else 11, m1_year if m1_idx > 0 else m1_year - 1
    return f"{meses_en[m0_idx]}/{m0_year}", f"{meses_en[m1_idx]}/{m1_year}", f"{meses_en[m2_idx]}/{m2_year}"

def buscar_dados_oficiais():
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = {"dolar": "R$ 5,15", "selic": "14,50%", "cdi": "14,40%", "juros_agro": "19,00%", "ipca": "4,20%"}
    try:
        url_dolar = "https://economia.awesomeapi.com.br/last/USD-BRL"
        dolar_data = json.loads(urllib.request.urlopen(urllib.request.Request(url_dolar, headers=headers), timeout=8).read())
        res["dolar"] = f"R$ {float(dolar_data['USDBRL']['bid']):.2f}".replace('.', ',')
        
        url_selic = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json"
        selic_data = json.loads(urllib.request.urlopen(urllib.request.Request(url_selic, headers=headers), timeout=8).read())
        s = float(selic_data[0]["valor"])
        res["selic"], res["cdi"], res["juros_agro"] = f"{s:.2f}%".replace('.', ','), f"{(s-0.10):.2f}%".replace('.', ','), f"{(s+4.50):.2f}%".replace('.', ',')
        
        url_ipca = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados/ultimos/1?formato=json"
        ipca_data = json.loads(urllib.request.urlopen(urllib.request.Request(url_ipca, headers=headers), timeout=8).read())
        res["ipca"] = f"{float(ipca_data[0]['valor']):.2f}%".replace('.', ',')
    except: pass
    return res

def buscar_projecoes_focus(ano):
    url = f"https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais?$filter=DataReferencia%20eq%20%27{ano}%27&$orderby=Data%20desc&$top=20&$format=json"
    try:
        data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=10).read())
        m = {i['Indicador']: i['Mediana'] for i in data['value'] if i['Mediana'] is not None}
        s = float(m.get('Selic', 10.5))
        return {"selic": f"{s:.2f}%".replace('.', ','), "cdi": f"{(s-0.1):.2f}%".replace('.', ','), "juros": f"{(s+4.5):.2f}%".replace('.', ','), "dolar": f"R$ {m.get('Câmbio', 5.1):.2f}".replace('.', ','), "ipca": f"{m.get('IPCA', 4.0):.2f}%".replace('.', ','), "pib": f"{m.get('PIB Total', 2.0):.2f}%".replace('.', ',')}
    except: return {"selic": "10,50%", "cdi": "10,40%", "juros": "15,00%", "dolar": "R$ 5,10", "ipca": "4,00%", "pib": "2,00%"}

def buscar_precos_soja(dolar_proj_str, ano):
    try:
        url = "https://www.noticiasagricolas.com.br/cotacoes/soja/soja-porto-paranagua-pr"
        text = re.sub(r'<[^>]+>', ' ', urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=8).read().decode('utf-8'))
        preco = re.findall(r'R\$\s*(\d{3}[,.]\d{2})', text)[0].replace('.', ',')
        return f"R$ {preco}", f"R$ {float(preco.replace(',', '.'))*1.05:.2f}".replace('.', ',')
    except: return "R$ 138,50", "R$ 145,00"

def parse_float(valor):
    try: return float(valor.replace('%', '').replace('R$', '').replace(',', '.').strip())
    except: return 0.0

def calcular_variacao(a, b, is_cambio=False):
    d = parse_float(a) - parse_float(b)
    if d > 0: return f'<span class="macro-badge red">● +{"R$ " if is_cambio else ""}{d:.2f}{"" if is_cambio else " PP"}</span>'
    if d < 0: return f'<span class="macro-badge green">● {"R$ " if is_cambio else ""}{abs(d):.2f}{"" if is_cambio else " PP"}</span>'
    return '<span class="macro-badge yellow">● 0,00</span>'

# ==========================================
# 3. NOTÍCIAS E GERAÇÃO DO HTML
# ==========================================
def construir_card_noticia(item):
    impacts = "".join([f"<li><div class='line-title'><strong>{i['segment']}</strong><span class='farol farol-{i['status'].lower()}'><span class='farol-dot'></span>{i['status']}</span></div><div class='impact-desc'>{i['desc']}</div></li>" for i in item.get('impacts', [])])
    return f"<div class='news-item'><div class='news-header'><h3 class='news-headline'>{item['headline']}</h3><span class='farol farol-{item.get('farol_texto','warning').lower()}'><span class='farol-dot'></span>{item.get('farol_texto','Warning')}</span></div><div class='news-content'>{item['content']}</div><div class='impact-box'><div class='impact-title'>⚠️ Impacto</div><ul class='impact-list'>{impacts}</ul><a href='#' class='source-link'>Fonte: {item['source']}</a></div></div>"

def gerar_relatorio():
    m0, m1, m2 = calcular_meses_rolantes()
    atuais = buscar_dados_oficiais()
    proj_atual = buscar_projecoes_focus(str(datetime.datetime.now().year))
    proj_futuro = buscar_projecoes_focus(ANO_PROJECAO)
    soja_h, soja_f = buscar_precos_soja(proj_futuro['dolar'], ANO_PROJECAO)

    # Dicionário de substituição
    subs = {
        "DATA_HOJE_PLACEHOLDER": datetime.datetime.now().strftime("%B %d, %Y").upper(),
        "M_ATUAL_PLACEHOLDER": m0, "M_ANTERIOR_PLACEHOLDER": m1, "M_ATRAS_PLACEHOLDER": m2,
        "SELIC_M0_PLACEHOLDER": atuais['selic'], "DOLAR_M0_PLACEHOLDER": atuais['dolar'],
        "PIB_M0_PLACEHOLDER": proj_atual['pib'], "SELIC_PROJ_PLACEHOLDER": proj_futuro['selic'],
        "DOLAR_PROJ_PLACEHOLDER": proj_futuro['dolar'], "PIB_PROJ_PLACEHOLDER": proj_futuro['pib'],
        "SELIC_VAR_MES_PLACEHOLDER": calcular_variacao(atuais['selic'], HISTORICO_MACRO[m2]['selic']),
        "": "<div>Conteúdo Brasil</div>" # Adicione aqui as outras tags
    }

    # Carregar template e substituir
    with open("template.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    for chave, valor in subs.items():
        html = html.replace(chave, valor)
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    gerar_relatorio()
