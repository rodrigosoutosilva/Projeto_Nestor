"""
helpers.py - Funções Auxiliares Compartilhadas
===============================================

Conceito de Eng. Software: DRY (Don't Repeat Yourself)
Funções utilitárias usadas em múltiplos módulos ficam aqui.
"""

import io
import csv
import pandas as pd
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Mapa de nomes de ativos da B3 (cache local para performance)
# ---------------------------------------------------------------------------
NOMES_ATIVOS = {
    # Ações — Blue Chips
    "PETR4": "Petrobras PN", "PETR3": "Petrobras ON",
    "VALE3": "Vale ON", "ITUB4": "Itaú Unibanco PN",
    "BBDC4": "Bradesco PN", "BBDC3": "Bradesco ON",
    "BBAS3": "Banco do Brasil ON", "ABEV3": "Ambev ON",
    "WEGE3": "WEG ON", "MGLU3": "Magazine Luiza ON",
    "CSNA3": "CSN ON", "CMIN3": "CSN Mineração ON",
    "B3SA3": "B3 ON", "RENT3": "Localiza ON",
    "SUZB3": "Suzano ON", "GGBR4": "Gerdau PN",
    "JBSS3": "JBS ON", "LREN3": "Lojas Renner ON",
    "TOTS3": "Totvs ON", "EQTL3": "Equatorial ON",
    "RDOR3": "Rede D'Or ON", "HAPV3": "Hapvida ON",
    "RAIL3": "Rumo ON", "KLBN11": "Klabin UNT",
    "VIVT3": "Telefônica Brasil ON", "ENGI11": "Energisa UNT",
    "PRIO3": "PetroRio ON", "CPLE6": "Copel PNB",
    "SBSP3": "Sabesp ON", "ITSA4": "Itaúsa PN",
    "EMBR3": "Embraer ON", "COGN3": "Cogna ON",
    "AZUL4": "Azul PN", "GOLL4": "GOL PN",
    # FIIs — Principais
    "HGLG11": "CSHG Logística FII", "MXRF11": "Maxi Renda FII",
    "XPML11": "XP Malls FII", "VISC11": "Vinci Shopping Centers FII",
    "KNCR11": "Kinea Rendimentos FII", "HGCR11": "CSHG Recebíveis FII",
    "KNRI11": "Kinea Renda Imob. FII", "HGBS11": "Hedge Brasil Shopping FII",
    "XPLG11": "XP Log FII", "BCFF11": "BTG Fundo de Fundos FII",
    "VILG11": "Vinci Logística FII", "BTLG11": "BTG Logística FII",
    "PVBI11": "VBI Prime Properties FII", "IRDM11": "Iridium Recebíveis FII",
    "VGIP11": "Valora IP FII",
}


def nome_ativo(ticker: str) -> str:
    """
    Retorna o nome do ativo a partir do ticker.
    Usa cache local primeiro, depois tenta yfinance como fallback.
    """
    ticker = ticker.upper().strip()
    if ticker in NOMES_ATIVOS:
        return NOMES_ATIVOS[ticker]
    # Fallback: tentar buscar via yfinance (cacheado em session_state no Streamlit)
    try:
        from services.market_data import buscar_preco_atual
        dados = buscar_preco_atual(ticker)
        if dados and dados.get("nome"):
            NOMES_ATIVOS[ticker] = dados["nome"]  # Cachear para próximas chamadas
            return dados["nome"]
    except Exception:
        pass
    return ticker  # Retorna o próprio ticker se nada funcionar


def formatar_moeda(valor) -> str:
    """Formata valor para R$ 1.234,56. Uso: st.metric() e contextos que NÃO interpretam LaTeX."""
    if valor is None:
        return "R$ 0,00"
    
    if isinstance(valor, (int, float)):
        valor_float = float(valor)
    else:
        try:
            val_str = str(valor).replace("R$", "").replace("R\\$", "").replace("R&#36;", "").strip()
            if "," in val_str and "." in val_str:
                val_str = val_str.replace(".", "").replace(",", ".")
            elif "," in val_str:
                val_str = val_str.replace(",", ".")
            valor_float = float(val_str)
        except ValueError:
            return "R$ 0,00"
            
    return f"R$ {valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_moeda_md(valor) -> str:
    """
    Formata valor para R$ 1.234,56 SEGURO para st.markdown().
    Usa HTML entity &#36; no lugar de $ para evitar que Streamlit interprete como LaTeX.
    REQUER unsafe_allow_html=True no st.markdown().
    """
    valor_float = 0.0
    if isinstance(valor, (int, float)):
        valor_float = float(valor)
    elif valor is not None:
        try:
            val_str = str(valor).replace("R$", "").replace("R\\$", "").replace("R&#36;", "").strip()
            if "," in val_str and "." in val_str:
                val_str = val_str.replace(".", "").replace(",", ".")
            elif "," in val_str:
                val_str = val_str.replace(",", ".")
            valor_float = float(val_str)
        except ValueError:
            pass

    texto_formatado = formatar_moeda(valor).replace("$", "&#36;")
    
    if valor_float < 0:
        return f"<span style='color:#FF4444'>{texto_formatado}</span>"
    return texto_formatado


def render_metric(label: str, value: float, format_str: str = "moeda", delta_pct: float = None, font_size: str = "1.82rem"):
    """
    Renderiza uma métrica customizada via st.markdown que permite
    colorir o valor principal de vermelho caso seja negativo.
    Imita o visual nativo do st.metric.
    """
    import streamlit as st
    
    if format_str == "moeda":
        val_str = formatar_moeda(value).replace("$", "&#36;")
    else:
        val_str = str(value)
        
    cor_valor = "#FF4444" if value < 0 else "inherit"
    
    delta_html = ""
    if delta_pct is not None:
        cor_delta = "#FF4444" if delta_pct < 0 else "#00C851"
        sinal_delta = "+" if delta_pct >= 0 else ""
        delta_html = f"<div style='font-size: 0.82rem; color: {cor_delta}; font-weight: 500;'>{sinal_delta}{delta_pct:.2f}%</div>"

    html = f"""
    <div style="display: flex; flex-direction: column; margin-bottom: 1rem;">
        <div style="font-size: 0.82rem; font-weight: 600; color: rgba(49, 51, 63, 0.6); margin-bottom: 0.25rem;">{label}</div>
        <div style="font-size: {font_size}; font-weight: 800; color: {cor_valor}; line-height: 1.2;">{val_str}</div>
        {delta_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def rendimento_anual_projetado(lucro: float, total_aportado: float, dias: int) -> float:
    """
    Calcula o rendimento anual projetado via regra de 3.
    Se a carteira tem 30 dias e rendeu 2%, projeta ~24.3% ao ano.
    """
    if total_aportado <= 0 or dias <= 0:
        return 0.0
    rendimento_periodo = (lucro / total_aportado) * 100
    rendimento_anual = (rendimento_periodo / dias) * 365
    return round(rendimento_anual, 2)


def render_ticker_link(ticker: str) -> str:
    """
    Retorna HTML de um ticker clicável que pode ser usado em st.markdown.
    Nota: Links reais de navegação no Streamlit precisam de st.button, 
    então retornamos o ticker em destaque com estilo de link.
    """
    return f"**{ticker}**"


def buscar_ativos_por_nome(termo: str, max_resultados: int = 10) -> list[dict]:
    """
    Busca ativos por ticker OU nome parcial (case-insensitive).
    Retorna lista de dicts com ticker e nome.
    """
    termo = termo.strip().upper()
    if not termo:
        return []
    
    resultados = []
    for ticker, nome in NOMES_ATIVOS.items():
        if termo in ticker or termo in nome.upper():
            resultados.append({"ticker": ticker, "nome": nome})
            if len(resultados) >= max_resultados:
                break
    
    return resultados


def formatar_percentual(valor) -> str:
    """Formata valor numérico para percentual."""
    if valor is None:
        return "0,00%"
    try:
        valor_float = float(str(valor).replace("%", "").strip())
    except ValueError:
        return "0,00%"
    return f"{valor_float:+.2f}%"


def formatar_data_br(data) -> str:
    """
    Formata data para o padrão brasileiro dd/mm/aaaa.
    Aceita string ISO (yyyy-mm-dd), date ou datetime.
    """
    if data is None:
        return "—"
    if isinstance(data, str):
        try:
            data = datetime.strptime(data.split(" ")[0], "%Y-%m-%d").date()
        except (ValueError, IndexError):
            return data  # Retorna como está se não conseguir parsear
    if isinstance(data, (date, datetime)):
        return data.strftime("%d/%m/%Y")
    return str(data)


def calcular_lucro_prejuizo(preco_medio: float, preco_atual: float, quantidade: int) -> dict:
    """
    Calcula lucro ou prejuízo de uma posição.
    
    Conceito de Finanças:
    - Lucro/Prejuízo = (Preço Atual - Preço Médio) × Quantidade
    - Variação % = ((Preço Atual - Preço Médio) / Preço Médio) × 100
    """
    if preco_medio <= 0:
        return {"valor": 0, "percentual": 0, "tipo": "neutro"}

    valor = (preco_atual - preco_medio) * quantidade
    percentual = ((preco_atual - preco_medio) / preco_medio) * 100

    tipo = "lucro" if valor > 0 else "prejuizo" if valor < 0 else "neutro"

    return {
        "valor": round(valor, 2),
        "percentual": round(percentual, 2),
        "tipo": tipo
    }


def calcular_meta_dividendos_auto(tolerancia_risco: int, estilo: str, objetivo_prazo: str) -> float:
    """
    Calcula automaticamente a meta de dividendos (% ao ano)
    cruzando o perfil da persona e carteira.
    
    Conceito de Finanças:
    - Conservador + dividendos + longo prazo → meta alta de DY (8-10%)
    - Arrojado + crescimento + curto prazo → meta baixa de DY (2-4%)
    - Equilibrado → faixa intermediária (5-7%)
    """
    # Base por estilo
    base = {"dividendos": 8.0, "equilibrado": 6.0, "crescimento": 3.0}.get(estilo, 6.0)
    
    # Ajuste por prazo
    ajuste_prazo = {"longo": 1.0, "medio": 0.0, "curto": -1.5}.get(objetivo_prazo, 0.0)
    
    # Ajuste por tolerância (0-10): conservador quer mais DY, arrojado menos
    ajuste_risco = (5 - tolerancia_risco) * 0.3  # -1.5 a +1.5
    
    meta = base + ajuste_prazo + ajuste_risco
    return round(max(1.0, min(15.0, meta)), 1)


def parsear_csv_ativos(conteudo: str) -> list[dict]:
    """
    Faz parse de um CSV de ativos.
    
    Formato esperado: ticker,quantidade,preco_medio,data_posicao
    """
    ativos = []
    try:
        reader = csv.reader(io.StringIO(conteudo))
        for i, row in enumerate(reader):
            if len(row) < 3:
                continue

            ticker = row[0].strip().upper()

            # Detectar cabeçalho
            if i == 0 and ticker.lower() in ("ticker", "ativo", "codigo", "código"):
                continue

            try:
                quantidade = int(row[1].strip())
                preco_medio = float(row[2].strip().replace(",", "."))
            except (ValueError, IndexError):
                continue

            data_posicao = None
            if len(row) >= 4 and row[3].strip():
                try:
                    data_posicao = date.fromisoformat(row[3].strip())
                except ValueError:
                    data_posicao = date.today()

            ativos.append({
                "ticker": ticker,
                "quantidade": quantidade,
                "preco_medio": preco_medio,
                "data_posicao": data_posicao or date.today()
            })
    except Exception as e:
        print(f"[helpers] Erro ao parsear CSV: {e}")

    return ativos


def cor_score(score: float) -> str:
    """Retorna cor CSS baseada no score (0-100)."""
    if score >= 70:
        return "#00C851"  # Verde
    elif score >= 40:
        return "#FFB300"  # Amarelo/Laranja
    else:
        return "#FF4444"  # Vermelho


def interpretar_score(score: float) -> dict:
    """
    Interpreta um score de 0 a 100 com contexto visual.
    Retorna emoji, texto descritivo e cor.
    """
    if score >= 80:
        return {"emoji": "🟢", "texto": "Excelente", "cor": "#00C851"}
    elif score >= 60:
        return {"emoji": "🔵", "texto": "Bom", "cor": "#2196F3"}
    elif score >= 40:
        return {"emoji": "🟡", "texto": "Moderado", "cor": "#FFB300"}
    elif score >= 20:
        return {"emoji": "🟠", "texto": "Fraco", "cor": "#FF9800"}
    else:
        return {"emoji": "🔴", "texto": "Muito Fraco", "cor": "#FF4444"}


def explicar_rsi(rsi: float) -> str:
    """Explica o indicador RSI em linguagem acessível."""
    if rsi is None or rsi == 0:
        return "RSI indisponível"
    if rsi > 70:
        return f"RSI {rsi:.0f}/100 — ⚠️ **Sobrecomprado**: preço pode estar caro, risco de correção"
    elif rsi < 30:
        return f"RSI {rsi:.0f}/100 — 💡 **Sobrevendido**: preço pode estar barato, possível oportunidade"
    elif rsi < 45:
        return f"RSI {rsi:.0f}/100 — 📉 **Tendência fraca**: pressão vendedora leve"
    elif rsi > 55:
        return f"RSI {rsi:.0f}/100 — 📈 **Tendência forte**: pressão compradora"
    else:
        return f"RSI {rsi:.0f}/100 — ⚖️ **Neutro**: sem pressão dominante"


def explicar_tendencia(tendencia: str, preco_atual: float, sma_20: float) -> str:
    """Explica a tendência de preço em linguagem acessível."""
    if sma_20 and sma_20 > 0:
        desvio = ((preco_atual - sma_20) / sma_20) * 100
        if tendencia == "alta":
            return f"📈 **Alta** — Preço {desvio:+.1f}% acima da média de 20 dias"
        elif tendencia == "baixa":
            return f"📉 **Baixa** — Preço {desvio:+.1f}% abaixo da média de 20 dias"
    return "⚖️ **Lateral** — Sem tendência definida"


def emoji_acao(tipo_acao: str) -> str:
    """Retorna emoji para o tipo de ação."""
    mapa = {
        "compra": "🟢",
        "venda": "🔴",
        "manter": "🟡"
    }
    return mapa.get(tipo_acao, "⚪")


def emoji_status(status: str) -> str:
    """Retorna emoji para o status da ação planejada."""
    mapa = {
        "planejado": "📋",
        "executado": "✅",
        "revisao_necessaria": "⚠️",
        "ignorado": "❌"
    }
    return mapa.get(status, "⚪")


def emoji_urgencia(urgencia: str) -> str:
    """Retorna emoji para o nível de urgência."""
    mapa = {
        "alta": "🔴",
        "media": "🟡",
        "baixa": "🟢"
    }
    return mapa.get(urgencia, "🟡")


# Setores disponíveis para preferência de carteira
SETORES_ACOES = [
    ("bancos", "🏦 Bancos (ITUB4, BBAS3, BBDC4...)"),
    ("petroleo", "🛢️ Petróleo & Gás (PETR4, PRIO3, RECV3...)"),
    ("mineracao", "⛏️ Mineração (VALE3, CMIN3...)"),
    ("energia", "⚡ Energia Elétrica (TAEE11, ENBR3, ELET3...)"),
    ("varejo", "🛒 Varejo (MGLU3, VIIA3, LREN3...)"),
    ("tecnologia", "💻 Tecnologia (TOTS3, LWSA3, POSI3...)"),
    ("saude", "🏥 Saúde (HAPV3, RDOR3, FLRY3...)"),
    ("construcao", "🏗️ Construção (MRV3, CYRE3, EZTC3...)"),
    ("saneamento", "💧 Saneamento (SAPR11, SBSP3...)"),
    ("seguros", "🛡️ Seguros (BBSE3, IRBR3, PSSA3...)"),
]

SETORES_FIIS = [
    ("tijolo", "🧱 FIIs de Tijolo (shoppings, galpões, escritórios)"),
    ("papel", "📄 FIIs de Papel (CRI, CRA, LCI)"),
    ("hibrido", "🔀 FIIs Híbridos (tijolo + papel)"),
    ("fof", "📦 Fundos de Fundos (FoFs)"),
]


def injetar_css_global():
    """Injeta CSS global para métricas, headers e dropdowns.
    DEVE ser chamada em TODAS as páginas logo após st.set_page_config()."""
    import streamlit as st

    
    st.markdown("""<style>
    /* Métricas */
    [data-testid="stMetricLabel"] { font-size: 0.82rem !important; font-weight: 600 !important; }
    [data-testid="stMetricValue"] > div { font-size: 1.82rem !important; font-weight: 800 !important; }
    [data-testid="stMetricValue"] { font-size: 1.82rem !important; font-weight: 800 !important; }
    [data-testid="stMetricDelta"] { font-size: 0.72rem !important; }
    /* Headers — tamanho original */
    h1, .main-header { font-size: 1.4rem !important; }
    h2 { font-size: 2rem !important; }
    h3 { font-size: 1rem !important; }
    h4 { font-size: 0.9rem !important; }
    /* Dropdowns não-editáveis */
    div[data-baseweb="select"] input { caret-color: transparent !important; cursor: pointer !important; pointer-events: none !important; }
    div[data-baseweb="select"] { cursor: pointer !important; }
    /* Fonte base — tamanho original */
    .stApp p, .stApp li, .stApp span { font-size: 0.88rem; }
    .stApp .stCaption, .stApp caption { font-size: 0.72rem !important; }
    hr { margin-top: 0.5rem !important; margin-bottom: 0.5rem !important; }
</style>""", unsafe_allow_html=True)

