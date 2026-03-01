"""
📊 Dashboard - Visão Geral da Carteira
========================================

Esta página mostra:
- Patrimônio total e variação
- Distribuição de ativos (gráfico de pizza com legenda)
- Tabela de ativos com lucro/prejuízo
- Ações pendentes com alertas
- Datas em formato brasileiro dd/mm/aaaa
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.crud import (
    listar_personas_usuario, listar_portfolios_persona,
    listar_ativos_portfolio, listar_acoes_portfolio,
    resumo_transacoes_portfolio
)
from services.market_data import buscar_preco_atual, buscar_historico
from utils.helpers import (
    formatar_moeda, formatar_percentual, calcular_lucro_prejuizo,
    emoji_status, formatar_data_br
)
import io

st.set_page_config(page_title="📊 Dashboard", page_icon="📊", layout="wide")

# ---------------------------------------------------------------------------
# Verificar login
# ---------------------------------------------------------------------------
if "user" not in st.session_state or st.session_state.user is None:
    st.warning("⚠️ Faça login na página principal primeiro.")
    st.stop()

user = st.session_state.user

st.markdown("### 📊 Dashboard de Investimentos")
st.markdown(f"*Visão geral das carteiras de **{user['nome']}***")
st.markdown("---")

# ---------------------------------------------------------------------------
# Buscar todas as personas → portfolios → ativos
# ---------------------------------------------------------------------------
personas = listar_personas_usuario(user["id"])

if not personas:
    st.info("Você ainda não tem personas configuradas. Vá para 📥 Onboarding ou 🧑 Personas.")
    st.stop()

# Filtros de Persona e Carteira
c1, c2 = st.columns(2)

with c1:
    persona_nomes_filter = ["Todas as Personas"] + [p["nome"] for p in personas]
    filtro_persona = st.selectbox(
        "🧑 Filtrar por Persona:",
        persona_nomes_filter,
        key="filtro_persona_dash"
    )

# Filtrar personas com base na seleção
if filtro_persona == "Todas as Personas":
    personas_filtradas = personas
else:
    personas_filtradas = [p for p in personas if p["nome"] == filtro_persona]

# Coletar todas as carteiras das personas filtradas
portfolios_disponiveis = []
for p in personas_filtradas:
    ports = listar_portfolios_persona(p["id"])
    for pt in ports:
        pt["persona_nome"] = p["nome"]
        portfolios_disponiveis.append(pt)

with c2:
    if not portfolios_disponiveis:
        st.warning("Nenhuma carteira atrelada a esta persona.")
        st.stop()
        
    port_nomes_filter = ["Todas as Carteiras"] + [f"{p['nome']} ({p['persona_nome']})" for p in portfolios_disponiveis]
    filtro_portfolio = st.selectbox(
        "💼 Filtrar por Carteira:",
        port_nomes_filter,
        key="filtro_port_dash"
    )

if filtro_portfolio != "Todas as Carteiras":
    portfolios_disponiveis = [p for p in portfolios_disponiveis if f"{p['nome']} ({p['persona_nome']})" == filtro_portfolio]

# Coletar todos os ativos das carteiras filtradas
todos_ativos = []
portfolio_map = {}

for port in portfolios_disponiveis:
    portfolio_map[port["id"]] = port
    ativos = listar_ativos_portfolio(port["id"])
    for ativo in ativos:
        ativo["portfolio_nome"] = port["nome"]
        ativo["persona_nome"] = port["persona_nome"]
        todos_ativos.append(ativo)

if not todos_ativos:
    st.info("Nenhum ativo encontrado. Adicione ativos nas suas carteiras em 💼 Carteiras.")
    st.stop()

# ---------------------------------------------------------------------------
# Buscar preços atuais (com cache do Streamlit para performance)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)  # Cache de 5 minutos
def buscar_precos_cache(tickers):
    """Cache de preços para evitar múltiplas chamadas."""
    precos = {}
    for t in tickers:
        dados = buscar_preco_atual(t)
        if dados:
            precos[t] = dados
    return precos

with st.spinner("🔄 Buscando preços atuais do mercado..."):
    tickers_unicos = list(set(a["ticker"] for a in todos_ativos))
    precos = buscar_precos_cache(tuple(tickers_unicos))

# ---------------------------------------------------------------------------
# Calcular métricas Realistas (Incluem Caixa e Aportes)
# ---------------------------------------------------------------------------
patrimonio_ativos = 0 # Valor investido varrido a mercado
caixa_total = 0       # Dinheiro vivo nas carteiras
total_aportado = 0    # Dinheiro que saiu do bolso do usuário
dados_tabela = []

# Calcular o impacto dos Aportes e Caixas primeiro
for port in portfolios_disponiveis:
    caixa_total += port.get("montante_disponivel", 0)
    resumo_port = resumo_transacoes_portfolio(port["id"])
    total_aportado += resumo_port["total_aportes"]

# Somar os ativos em carteira
for ativo in todos_ativos:
    ticker = ativo["ticker"]
    preco_info = precos.get(ticker, {})
    preco_atual = preco_info.get("preco_atual", ativo["preco_medio"])

    valor_atual = preco_atual * ativo["quantidade"]
    patrimonio_ativos += valor_atual

    # LP interno de posição continuará apenas para a Tabela e pizza, não interfere no Lucro Global
    lp = calcular_lucro_prejuizo(ativo["preco_medio"], preco_atual, ativo["quantidade"])

    dados_tabela.append({
        "Ticker": ticker,
        "Carteira": ativo.get("portfolio_nome", ""),
        "Qtd": ativo["quantidade"],
        "Preço Médio": ativo["preco_medio"],
        "Preço Atual": preco_atual,
        "Variação (%)": f"{lp['percentual']:+.2f}%",
        "Lucro/Prejuízo": lp["valor"],
        "Valor Total": valor_atual,
        "_variacao_num": lp["percentual"]
    })

patrimonio_total_global = patrimonio_ativos + caixa_total
lucro_total = patrimonio_total_global - total_aportado
variacao_total = ((patrimonio_total_global - total_aportado) / total_aportado * 100) if total_aportado > 0 else 0

# ---------------------------------------------------------------------------
# Métricas no topo
# ---------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(
        "💰 Patrimônio Total",
        formatar_moeda(patrimonio_total_global),
        f"{variacao_total:+.2f}%"
    )
with col2:
    st.metric("💵 Total Investido", formatar_moeda(total_aportado))
with col3:
    st.metric(
        "📈 Lucro/Prejuízo",
        formatar_moeda(lucro_total),
        f"{variacao_total:+.2f}%",
        delta_color="normal"
    )
with col4:
    st.metric("📊 Total de Ativos", len(todos_ativos))

st.markdown("---")

# ---------------------------------------------------------------------------
# Gráficos com tema claro e legendas visíveis
# ---------------------------------------------------------------------------
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("#### 🍕 Distribuição por Ativo")
    df_dist = pd.DataFrame([{
        "Ticker": d["Ticker"],
        "Valor (R$)": d["Valor Total"]
    } for d in dados_tabela])

    if not df_dist.empty:
        fig = px.pie(
            df_dist, values="Valor (R$)", names="Ticker",
            color_discrete_sequence=px.colors.qualitative.Set2,
            hole=0.4
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#333"),
            legend=dict(
                title="Ativos",
                font=dict(color="#333", size=12),
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="rgba(0,0,0,0.1)",
                borderwidth=1
            ),
            margin=dict(t=20, b=20, l=20, r=20)
        )
        fig.update_traces(
            textposition='inside',
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>Valor: R$ %{value:,.2f}<br>%{percent}<extra></extra>'
        )
        st.plotly_chart(fig, use_container_width=True)

with col_chart2:
    st.markdown("#### 📊 Lucro/Prejuízo por Ativo")
    df_lp = pd.DataFrame([{
        "Ticker": d["Ticker"],
        "L/P (R$)": d["Lucro/Prejuízo"]
    } for d in dados_tabela])

    if not df_lp.empty:
        cores = ["#00C851" if v >= 0 else "#FF4444" for v in df_lp["L/P (R$)"]]
        fig2 = go.Figure(go.Bar(
            x=df_lp["Ticker"],
            y=df_lp["L/P (R$)"],
            marker_color=cores,
            text=[formatar_moeda(v) for v in df_lp["L/P (R$)"]],
            textposition="outside",
            name="Lucro/Prejuízo"
        ))
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#333"),
            xaxis=dict(
                title="Ativo",
                color="#333",
                gridcolor="rgba(0,0,0,0.06)"
            ),
            yaxis=dict(
                title="Lucro/Prejuízo (R$)",
                color="#333",
                gridcolor="rgba(0,0,0,0.06)"
            ),
            legend=dict(
                font=dict(color="#333"),
                bgcolor="rgba(255,255,255,0.8)"
            ),
            margin=dict(t=20, b=40, l=40, r=20),
            showlegend=True
        )
        st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Tabela de Ativos
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------
st.markdown("#### 📋 Detalhamento de Ativos")

col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
with col_f1:
    busca_ticker = st.text_input("🔍 Buscar ticker:", placeholder="Ex: PETR4", key="busca_ticker")
with col_f2:
    carteiras_disponiveis = ["Todas"] + list(set(d["Carteira"] for d in dados_tabela))
    filtro_carteira = st.selectbox("Filtrar por carteira:", carteiras_disponiveis)
with col_f3:
    st.markdown("")
    st.markdown("")

df_display = pd.DataFrame(dados_tabela)
if not df_display.empty:
    df_show = df_display.drop(columns=["_variacao_num"], errors="ignore")

    # Aplicar filtros
    if busca_ticker:
        df_show = df_show[df_show["Ticker"].str.contains(busca_ticker.upper().strip(), case=False, na=False)]
    if filtro_carteira != "Todas":
        df_show = df_show[df_show["Carteira"] == filtro_carteira]

    st.dataframe(
        df_show.style.format({
            "Preço Médio": "R$ {:.2f}",
            "Preço Atual": "R$ {:.2f}",
            "Lucro/Prejuízo": "R$ {:.2f}",
            "Valor Total": "R$ {:.2f}"
        }).apply(
            lambda x: [
                "color: #00C851" if isinstance(v, (int, float)) and v > 0
                else "color: #FF4444" if isinstance(v, (int, float)) and v < 0
                else ""
                for v in x
            ],
            subset=["Lucro/Prejuízo"]
        ),
        use_container_width=True,
        hide_index=True
    )

    # Export CSV
    csv_data = df_show.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📤 Exportar tabela para CSV",
        csv_data,
        "investbr_ativos.csv",
        "text/csv",
        key="export_dashboard_csv"
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# Gráfico de Histórico (selecionar ativo)
# ---------------------------------------------------------------------------
st.markdown("#### 📈 Histórico de Preço")

ticker_selecionado = st.selectbox(
    "Selecione um ativo para ver o histórico:",
    tickers_unicos,
    key="hist_ticker"
)

col_p1, col_p2 = st.columns([3, 1])
with col_p2:
    periodo = st.selectbox(
        "Período:",
        ["1mo", "3mo", "6mo", "1y", "2y"],
        index=2,
        key="hist_periodo"
    )

with st.spinner(f"Buscando histórico de {ticker_selecionado}..."):
    hist = buscar_historico(ticker_selecionado, periodo)

if hist is not None and not hist.empty:
    fig3 = go.Figure()
    fig3.add_trace(go.Candlestick(
        x=hist.index,
        open=hist["Open"],
        high=hist["High"],
        low=hist["Low"],
        close=hist["Close"],
        name=ticker_selecionado,
        increasing_line_color='#00C851',
        decreasing_line_color='#FF4444'
    ))
    fig3.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#333"),
        xaxis=dict(
            title="Data",
            color="#333",
            gridcolor="rgba(0,0,0,0.06)"
        ),
        yaxis=dict(
            title="Preço (R$)",
            color="#333",
            gridcolor="rgba(0,0,0,0.06)"
        ),
        xaxis_rangeslider_visible=False,
        margin=dict(t=20, b=40, l=40, r=20),
        legend=dict(
            font=dict(color="#333"),
            bgcolor="rgba(255,255,255,0.8)"
        ),
        showlegend=True
    )
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info(f"Não foi possível obter dados históricos de {ticker_selecionado}.")

# ---------------------------------------------------------------------------
# Ações Pendentes
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("#### 📋 Ações Planejadas Pendentes")

has_actions = False
for port_id, port_info in portfolio_map.items():
    acoes = listar_acoes_portfolio(port_id, status="planejado")
    acoes_rev = listar_acoes_portfolio(port_id, status="revisao_necessaria")
    todas = acoes + acoes_rev

    if todas:
        has_actions = True
        st.markdown(f"**{port_info['nome']}** ({port_info['persona_nome']})")
        for a in todas:
            status_icon = emoji_status(a["status"])
            st.markdown(
                f"{status_icon} **{a['asset_ticker']}** — "
                f"{a['tipo_acao'].upper()} | "
                f"Data: {formatar_data_br(a['data_planejada'])} | "
                f"Score: {a['pontuacao']:.0f}/100"
            )

if not has_actions:
    st.info("Nenhuma movimentação pendente.")
