"""
📜 Extrato - Histórico de Movimentações Financeiras
=====================================================

Página para visualizar todas as movimentações da carteira:
- Aportes, retiradas, compras, vendas, dividendos
- Resumo financeiro com totais
- Gráfico de evolução do caixa
- Formulários para registrar aportes, retiradas e dividendos
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.crud import (
    listar_personas_usuario, listar_portfolios_persona,
    listar_transacoes_portfolio, resumo_transacoes_portfolio,
    registrar_transacao, buscar_portfolio_por_id
)
from utils.helpers import formatar_moeda, formatar_data_br
from datetime import date

st.set_page_config(page_title="📜 Extrato", page_icon="📜", layout="wide")

# Verificar login
if "user" not in st.session_state or st.session_state.user is None:
    st.warning("⚠️ Faça login na página principal primeiro.")
    st.stop()

user = st.session_state.user

st.markdown("# 📜 Extrato de Movimentações")
st.markdown("*Acompanhe toda a movimentação financeira das suas carteiras*")
st.markdown("---")

# ---------------------------------------------------------------------------
# Seleção de Persona e Carteira
# ---------------------------------------------------------------------------
personas = listar_personas_usuario(user["id"])

if not personas:
    st.warning("Crie uma Persona e Carteira primeiro.")
    st.stop()

col_sel1, col_sel2 = st.columns(2)

with col_sel1:
    persona_nomes = [p["nome"] for p in personas]
    persona_idx = st.selectbox("Persona:", range(len(personas)),
                               format_func=lambda i: persona_nomes[i])
    persona = personas[persona_idx]

portfolios = listar_portfolios_persona(persona["id"])

if not portfolios:
    st.warning(f"A persona '{persona['nome']}' não tem carteiras.")
    st.stop()

with col_sel2:
    port_nomes = [p["nome"] for p in portfolios]
    port_idx = st.selectbox("Carteira:", range(len(portfolios)),
                            format_func=lambda i: port_nomes[i])
    portfolio = portfolios[port_idx]

st.markdown("---")

# ---------------------------------------------------------------------------
# Resumo Financeiro
# ---------------------------------------------------------------------------
st.markdown("### 💰 Resumo Financeiro")

resumo = resumo_transacoes_portfolio(portfolio["id"])
caixa_atual = portfolio.get("montante_disponivel", 0)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("💵 Caixa Disponível", formatar_moeda(caixa_atual))
with col2:
    st.metric("📥 Total Aportes", formatar_moeda(resumo["total_aportes"]))
with col3:
    st.metric("📤 Total Retiradas", formatar_moeda(resumo["total_retiradas"]))
with col4:
    st.metric("🛒 Total Compras", formatar_moeda(resumo["total_compras"]))
with col5:
    st.metric("💰 Total Dividendos", formatar_moeda(resumo["total_dividendos"]))

col_extra1, col_extra2 = st.columns(2)
with col_extra1:
    st.metric("📈 Total Vendas", formatar_moeda(resumo["total_vendas"]))
with col_extra2:
    st.metric("📊 Nº Transações", resumo["num_transacoes"])

st.markdown("---")

# ---------------------------------------------------------------------------
# Registrar Movimentação
# ---------------------------------------------------------------------------
st.markdown("### ➕ Registrar Movimentação")

tab_aporte, tab_retirada, tab_dividendo = st.tabs(["📥 Aporte", "📤 Retirada", "💰 Dividendo"])

with tab_aporte:
    with st.form("form_aporte"):
        st.markdown("*Adicionar dinheiro novo à carteira*")
        col1, col2 = st.columns(2)
        with col1:
            aporte_valor = st.number_input(
                "Valor do aporte (R$):",
                min_value=1.0, max_value=10_000_000.0, value=1000.0, step=100.0,
                key="aporte_valor"
            )
        with col2:
            aporte_data = st.date_input("Data:", value=date.today(), key="aporte_data")
        aporte_desc = st.text_input("Descrição (opcional):", placeholder="Ex: Salário de fevereiro", key="aporte_desc")

        if st.form_submit_button("📥 Registrar Aporte", use_container_width=True):
            registrar_transacao(
                portfolio_id=portfolio["id"],
                tipo="aporte",
                valor=aporte_valor,
                descricao=aporte_desc or "Aporte",
                data_transacao=aporte_data
            )
            st.toast(f"Aporte de {formatar_moeda(aporte_valor)} registrado! 📥")
            st.rerun()

with tab_retirada:
    with st.form("form_retirada"):
        st.markdown("*Retirar dinheiro da carteira*")
        col1, col2 = st.columns(2)
        with col1:
            ret_valor = st.number_input(
                "Valor da retirada (R$):",
                min_value=1.0, max_value=10_000_000.0, value=500.0, step=100.0,
                key="ret_valor"
            )
        with col2:
            ret_data = st.date_input("Data:", value=date.today(), key="ret_data")
        ret_desc = st.text_input("Descrição (opcional):", placeholder="Ex: Emergência", key="ret_desc")

        if st.form_submit_button("📤 Registrar Retirada", use_container_width=True):
            if ret_valor > caixa_atual:
                st.error(f"Caixa insuficiente! Disponível: {formatar_moeda(caixa_atual)}")
            else:
                registrar_transacao(
                    portfolio_id=portfolio["id"],
                    tipo="retirada",
                    valor=ret_valor,
                    descricao=ret_desc or "Retirada",
                    data_transacao=ret_data
                )
                st.toast(f"Retirada de {formatar_moeda(ret_valor)} registrada! 📤")
                st.rerun()

with tab_dividendo:
    with st.form("form_dividendo"):
        st.markdown("*Registrar provento recebido de um ativo*")
        col1, col2, col3 = st.columns(3)
        with col1:
            div_ticker = st.text_input("Ticker do ativo:", placeholder="PETR4", key="div_ticker")
        with col2:
            div_valor = st.number_input(
                "Valor recebido (R$):",
                min_value=0.01, max_value=1_000_000.0, value=50.0, step=1.0,
                key="div_valor"
            )
        with col3:
            div_data = st.date_input("Data:", value=date.today(), key="div_data")
        div_desc = st.text_input("Descrição (opcional):", placeholder="Ex: Dividendo trimestral", key="div_desc")

        if st.form_submit_button("💰 Registrar Dividendo", use_container_width=True):
            if not div_ticker:
                st.error("Informe o ticker do ativo!")
            else:
                registrar_transacao(
                    portfolio_id=portfolio["id"],
                    tipo="dividendo",
                    valor=div_valor,
                    ticker=div_ticker,
                    descricao=div_desc or f"Dividendo {div_ticker.upper()}",
                    data_transacao=div_data
                )
                st.toast(f"Dividendo de {formatar_moeda(div_valor)} de {div_ticker.upper()} registrado! 💰")
                st.rerun()

st.markdown("---")

# ---------------------------------------------------------------------------
# Tabela de Transações
# ---------------------------------------------------------------------------
st.markdown("### 📋 Histórico de Transações")

# Filtros
col_ft1, col_ft2 = st.columns(2)
with col_ft1:
    filtro_tipo = st.selectbox(
        "Filtrar por tipo:",
        ["todos", "aporte", "retirada", "compra", "venda", "dividendo"],
        format_func=lambda x: {
            "todos": "📊 Todos",
            "aporte": "📥 Aportes",
            "retirada": "📤 Retiradas",
            "compra": "🟢 Compras",
            "venda": "🔴 Vendas",
            "dividendo": "💰 Dividendos"
        }.get(x, x)
    )

tipo_filtro = None if filtro_tipo == "todos" else filtro_tipo
transacoes = listar_transacoes_portfolio(portfolio["id"], tipo=tipo_filtro)

if transacoes:
    # Emojis por tipo
    tipo_emoji = {
        "aporte": "📥", "retirada": "📤",
        "compra": "🟢", "venda": "🔴", "dividendo": "💰"
    }

    for t in transacoes:
        emoji = tipo_emoji.get(t["tipo"], "📊")
        ticker_txt = f" — {t['ticker']}" if t['ticker'] else ""
        qtd_txt = f" ({t['quantidade']}x @ {formatar_moeda(t['preco_unitario'])})" if t.get('quantidade') and t.get('preco_unitario') else ""
        desc_txt = f" · _{t['descricao']}_" if t.get('descricao') else ""

        # Valor com sinal
        if t["tipo"] in ("aporte", "venda", "dividendo"):
            valor_txt = f"+{formatar_moeda(t['valor'])}"
            cor = "green"
        else:
            valor_txt = f"-{formatar_moeda(t['valor'])}"
            cor = "red"

        st.markdown(
            f"{emoji} **{t['tipo'].upper()}**{ticker_txt}{qtd_txt} | "
            f"**:{cor}[{valor_txt}]** | "
            f"📅 {formatar_data_br(t['data'])}{desc_txt}"
        )

    # Gráfico de evolução do caixa
    st.markdown("---")
    st.markdown("### 📈 Evolução do Caixa")

    # Ordenar do mais antigo para o mais recente
    transacoes_ordenadas = sorted(transacoes, key=lambda t: t["data"])
    saldo = 0
    datas = []
    saldos = []

    for t in transacoes_ordenadas:
        if t["tipo"] in ("aporte", "venda", "dividendo"):
            saldo += t["valor"]
        else:
            saldo -= t["valor"]
        datas.append(t["data"])
        saldos.append(saldo)

    if datas:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=datas, y=saldos,
            mode="lines+markers",
            name="Saldo Caixa",
            line=dict(color="#667eea", width=3),
            marker=dict(size=6),
            fill="tozeroy",
            fillcolor="rgba(102, 126, 234, 0.1)"
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#333"),
            xaxis=dict(title="Data", color="#333", gridcolor="rgba(0,0,0,0.06)"),
            yaxis=dict(title="Saldo (R$)", color="#333", gridcolor="rgba(0,0,0,0.06)"),
            margin=dict(t=20, b=40, l=40, r=20),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Nenhuma transação registrada ainda. Use os formulários acima para começar.")
