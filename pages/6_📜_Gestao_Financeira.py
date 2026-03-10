"""
📜 Gestão Financeira - Histórico de Movimentações Financeiras
=====================================================

Página para visualizar todas as movimentações das carteiras:
- Começa mostrando TUDO consolidado
- Filtros opcionais por Persona e Carteira
- Formulários para registrar aportes, retiradas e dividendos (sempre pedindo a carteira)
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
from utils.helpers import formatar_moeda, formatar_data_br, formatar_moeda_md, injetar_css_global, render_metric
from datetime import date

st.set_page_config(page_title="📜 Gestão Financeira", page_icon="📜", layout="wide")
injetar_css_global()

# Verificar login
if "user" not in st.session_state or st.session_state.user is None:
    st.warning("⚠️ Faça login na página principal primeiro.")
    st.stop()

user = st.session_state.user

st.markdown("### 📜 Gestão Financeira")
st.markdown("*Acompanhe toda a movimentação financeira das suas carteiras*")
st.markdown("---")

# ---------------------------------------------------------------------------
# Exportação Global
# ---------------------------------------------------------------------------
col_ex1, col_ex2 = st.columns([3, 1])
with col_ex1:
    st.markdown("**Exportação Global:** Baixe um relatório consolidado com todas as movimentações.")
with col_ex2:
    if "excel_data" not in st.session_state:
        st.session_state.excel_data = None
        
    if st.button("📊 Gerar Relatório Excel", use_container_width=True):
        from services.excel_export import gerar_relatorio_excel
        with st.spinner("Gerando planilha..."):
            st.session_state.excel_data = gerar_relatorio_excel(user['id'])
            
    if st.session_state.get("excel_data"):
        st.download_button(
            label="📥 Baixar .xlsx",
            data=st.session_state.excel_data,
            file_name="relatorio_completo_egolab.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

st.markdown("---")

# ---------------------------------------------------------------------------
# Dados base
# ---------------------------------------------------------------------------
personas = listar_personas_usuario(user["id"])

if not personas:
    st.warning("Crie uma Persona e Carteira primeiro.")
    st.stop()

# Coletar TODOS os portfolios
todos_portfolios = []
mapa_persona = {}
for p in personas:
    ports = listar_portfolios_persona(p["id"])
    for port in ports:
        port["persona_nome"] = p["nome"]
        todos_portfolios.append(port)
        mapa_persona[port["id"]] = p["nome"]

if not todos_portfolios:
    st.warning("Nenhuma carteira encontrada. Crie uma primeiro.")
    st.stop()

# ---------------------------------------------------------------------------
# Filtros opcionais (começa mostrando tudo)
# ---------------------------------------------------------------------------
st.markdown("#### 🔍 Filtros")
col_f1, col_f2 = st.columns(2)

with col_f1:
    opcoes_persona = ["Todas as Personas"] + [p["nome"] for p in personas]
    filtro_persona = st.selectbox("Persona:", opcoes_persona)

with col_f2:
    if filtro_persona == "Todas as Personas":
        portfolios_visiveis = todos_portfolios
    else:
        persona_sel = next(p for p in personas if p["nome"] == filtro_persona)
        portfolios_visiveis = [pt for pt in todos_portfolios if pt["persona_nome"] == filtro_persona]
    
    opcoes_carteira = ["Todas as Carteiras"] + [f"{pt['nome']} ({pt['persona_nome']})" for pt in portfolios_visiveis]
    filtro_carteira = st.selectbox("Carteira:", opcoes_carteira)

# Determinar carteiras filtradas
if filtro_carteira == "Todas as Carteiras":
    carteiras_filtradas = portfolios_visiveis
else:
    carteiras_filtradas = [pt for pt in portfolios_visiveis if f"{pt['nome']} ({pt['persona_nome']})" == filtro_carteira]

st.markdown("---")

# ---------------------------------------------------------------------------
# Resumo Financeiro Consolidado
# ---------------------------------------------------------------------------
st.markdown("### 💰 Resumo Financeiro")

resumo_total = {
    "total_aportes": 0, "total_retiradas": 0,
    "total_compras": 0, "total_vendas": 0,
    "total_dividendos": 0, "num_transacoes": 0
}
caixa_total = 0

for pt in carteiras_filtradas:
    r = resumo_transacoes_portfolio(pt["id"])
    for k in resumo_total:
        resumo_total[k] += r.get(k, 0)
    caixa_total += pt.get("montante_disponivel", 0)

col1, col2, col3, col4, col5 = st.columns(5)
with col1: render_metric("💵 Caixa Total", caixa_total)
with col2: render_metric("📥 Aportes", resumo_total["total_aportes"])
with col3: render_metric("📤 Retiradas", resumo_total["total_retiradas"])
with col4: render_metric("🛒 Compras", resumo_total["total_compras"])
with col5: render_metric("💰 Dividendos", resumo_total["total_dividendos"])

st.markdown("---")

# ---------------------------------------------------------------------------
# Registrar Movimentação (sempre pede a carteira)
# ---------------------------------------------------------------------------
st.markdown("### ➕ Registrar Movimentação")

tab_compra, tab_venda, tab_aporte, tab_retirada, tab_dividendo = st.tabs(["🛒 Compra", "📉 Venda", "📥 Aporte", "📤 Retirada", "💰 Dividendo"])

# Opções de carteira para os formulários
opcoes_port_form = {pt["id"]: f"{pt['nome']} ({pt['persona_nome']})" for pt in todos_portfolios}

with tab_compra:
    port_compra = st.selectbox("Carteira destino:", list(opcoes_port_form.keys()),
                                format_func=lambda x: opcoes_port_form[x], key="port_compra")
    compra_ticker = st.text_input("Ticker do ativo (Compra):", placeholder="PETR4", help="Digite e pressione Enter para buscar a cotação", key="compra_ticker")
    
    preco_sug_c = 10.0
    if compra_ticker:
        from services.market_data import buscar_preco_atual
        cot = buscar_preco_atual(compra_ticker)
        if isinstance(cot, dict) and cot.get("preco_atual", 0) > 0:
            preco_sug_c = float(cot["preco_atual"])
            
    c1, c2, c3 = st.columns(3)
    with c1: compra_qtd = st.number_input("Quantidade:", min_value=1, value=100, step=1, key="compra_qtd")
    with c2: compra_preco = st.number_input("Preço:", min_value=0.01, value=preco_sug_c, format="%.2f", key="compra_preco")
    with c3: compra_data = st.date_input("Data:", value=date.today(), key="compra_data")
    
    compra_total = compra_qtd * compra_preco
    st.markdown(f"**Total Estimado:** {formatar_moeda_md(compra_total)}", unsafe_allow_html=True)
    
    if st.button("🛒 Registrar Compra", type="primary", use_container_width=True):
        if not compra_ticker:
            st.error("Informe o ticker do ativo!")
        else:
            ticker_upper = compra_ticker.upper().strip()
            port_info = buscar_portfolio_por_id(port_compra)
            caixa_disp = port_info.get("montante_disponivel", 0) if port_info else 0
            
            if compra_total > caixa_disp:
                st.warning(f"⚠️ Caixa insuficiente (Disponível: {formatar_moeda(caixa_disp)}). Esta compra causará saldo negativo, sujeito a cobrança diária de juros. Clique em Registrar Compra novamente para confirmar.".replace("$", r"\$"))
                if not st.session_state.get(f"conf_compra_gestao", False):
                    st.session_state[f"conf_compra_gestao"] = True
                    st.stop()
                st.session_state[f"conf_compra_gestao"] = False
                
            from database.crud import adicionar_ativo, atualizar_ativo, listar_ativos_portfolio
            ativos_cart = listar_ativos_portfolio(port_compra)
            ativo_existente = next((x for x in ativos_cart if x["ticker"] == ticker_upper), None)
            
            if ativo_existente:
                q_ant = ativo_existente["quantidade"]
                p_ant = ativo_existente["preco_medio"]
                q_nova = q_ant + compra_qtd
                p_novo = ((q_ant * p_ant) + compra_total) / q_nova
                atualizar_ativo(ativo_existente["id"], quantidade=q_nova, preco_medio=p_novo)
            else:
                adicionar_ativo(port_compra, ticker_upper, compra_preco, compra_qtd, compra_data)
                
            registrar_transacao(port_compra, "compra", compra_total, ticker_upper, compra_qtd, compra_preco, "Compra via Gestão", compra_data)
            from database.crud import atualizar_portfolio
            atualizar_portfolio(port_compra, montante_disponivel=caixa_disp - compra_total)
            st.toast(f"Compra de {compra_qtd}x {ticker_upper} registrada! 🎉")
            st.rerun()

with tab_venda:
    port_venda = st.selectbox("Carteira de origem:", list(opcoes_port_form.keys()),
                                format_func=lambda x: opcoes_port_form[x], key="port_venda")
    venda_ticker = st.text_input("Ticker do ativo (Venda):", placeholder="ITUB4", help="Digite e pressione Enter para buscar a cotação", key="venda_ticker")
    
    preco_sug_v = 10.0
    if venda_ticker:
        from services.market_data import buscar_preco_atual
        cot = buscar_preco_atual(venda_ticker)
        if isinstance(cot, dict) and cot.get("preco_atual", 0) > 0:
            preco_sug_v = float(cot["preco_atual"])
            
    c1, c2, c3 = st.columns(3)
    with c1: venda_qtd = st.number_input("Quantidade:", min_value=1, value=100, step=1, key="venda_qtd")
    with c2: venda_preco = st.number_input("Preço:", min_value=0.01, value=preco_sug_v, format="%.2f", key="venda_preco")
    with c3: venda_data = st.date_input("Data:", value=date.today(), key="venda_data")
    
    venda_total = venda_qtd * venda_preco
    st.markdown(f"**Total Recebido Estimado:** {formatar_moeda_md(venda_total)}", unsafe_allow_html=True)
    
    if st.button("📉 Registrar Venda", type="primary", use_container_width=True):
        if not venda_ticker:
            st.error("Informe o ticker do ativo!")
        else:
            ticker_upper = venda_ticker.upper().strip()
            from database.crud import deletar_ativo, atualizar_ativo, listar_ativos_portfolio
            ativos_cart = listar_ativos_portfolio(port_venda)
            ativo_existente = next((x for x in ativos_cart if x["ticker"] == ticker_upper), None)
            
            if not ativo_existente or venda_qtd > ativo_existente["quantidade"]:
                st.error("Você não possui quantidade suficiente deste ativo na carteira selecionada.")
            else:
                nova_qtd = ativo_existente["quantidade"] - venda_qtd
                if nova_qtd == 0: 
                    deletar_ativo(ativo_existente["id"])
                else: 
                    atualizar_ativo(ativo_existente["id"], quantidade=nova_qtd, preco_medio=ativo_existente["preco_medio"])
                    
                registrar_transacao(port_venda, "venda", venda_total, ticker_upper, venda_qtd, venda_preco, "Venda via Gestão", venda_data)
                st.toast(f"Venda de {venda_qtd}x {ticker_upper} registrada! 📉")
                st.rerun()

with tab_aporte:
    with st.form("form_aporte"):
        port_aporte = st.selectbox("Carteira destino:", list(opcoes_port_form.keys()),
                                    format_func=lambda x: opcoes_port_form[x], key="port_aporte")
        col1, col2 = st.columns(2)
        with col1:
            aporte_valor = st.number_input("Valor do aporte:", min_value=1.0, value=1000.0, step=100.0, key="aporte_valor")
        with col2:
            aporte_data = st.date_input("Data:", value=date.today(), key="aporte_data")
        aporte_desc = st.text_input("Descrição (opcional):", placeholder="Ex: Salário de fevereiro", key="aporte_desc")

        if st.form_submit_button("📥 Registrar Aporte", use_container_width=True):
            registrar_transacao(
                portfolio_id=port_aporte, tipo="aporte",
                valor=aporte_valor, descricao=aporte_desc or "Aporte",
                data_transacao=aporte_data
            )
            st.toast(f"Aporte de {formatar_moeda(aporte_valor)} registrado! 📥".replace("$", r"\$"))
            st.rerun()

with tab_retirada:
    with st.form("form_retirada"):
        port_ret = st.selectbox("Carteira de origem:", list(opcoes_port_form.keys()),
                                format_func=lambda x: opcoes_port_form[x], key="port_ret")
        col1, col2 = st.columns(2)
        with col1:
            ret_valor = st.number_input("Valor da retirada:", min_value=1.0, value=500.0, step=100.0, key="ret_valor")
        with col2:
            ret_data = st.date_input("Data:", value=date.today(), key="ret_data")
        ret_desc = st.text_input("Descrição (opcional):", placeholder="Ex: Emergência", key="ret_desc")

        if st.form_submit_button("📤 Registrar Retirada", use_container_width=True):
            port_info = buscar_portfolio_por_id(port_ret)
            caixa_disp = port_info.get("montante_disponivel", 0) if port_info else 0
            if ret_valor > caixa_disp:
                st.warning(f"⚠️ Caixa insuficiente (Disponível: {formatar_moeda(caixa_disp)}). Esta retirada causará saldo negativo, sujeito a cobrança diária de juros. Clique em Registrar Retirada novamente para confirmar.".replace("$", r"\$"))
                if not st.session_state.get(f"conf_retirada_gestao", False):
                    st.session_state[f"conf_retirada_gestao"] = True
                    st.stop()
                st.session_state[f"conf_retirada_gestao"] = False
                
            registrar_transacao(
                portfolio_id=port_ret, tipo="retirada",
                valor=ret_valor, descricao=ret_desc or "Retirada",
                data_transacao=ret_data
            )
            from database.crud import atualizar_portfolio
            atualizar_portfolio(port_ret, montante_disponivel=caixa_disp - ret_valor)
            st.toast(f"Retirada de {formatar_moeda(ret_valor)} registrada! 📤".replace("$", r"\$"))
            st.rerun()

with tab_dividendo:
    with st.form("form_dividendo"):
        port_div = st.selectbox("Carteira:", list(opcoes_port_form.keys()),
                                format_func=lambda x: opcoes_port_form[x], key="port_div")
        col1, col2, col3 = st.columns(3)
        with col1:
            div_ticker = st.text_input("Ticker do ativo:", placeholder="PETR4", key="div_ticker")
        with col2:
            div_valor = st.number_input("Valor recebido:", min_value=0.01, value=50.0, step=1.0, key="div_valor")
        with col3:
            div_data = st.date_input("Data:", value=date.today(), key="div_data")
        div_desc = st.text_input("Descrição (opcional):", placeholder="Ex: Dividendo trimestral", key="div_desc")

        if st.form_submit_button("💰 Registrar Dividendo", use_container_width=True):
            if not div_ticker:
                st.error("Informe o ticker do ativo!")
            else:
                registrar_transacao(
                    portfolio_id=port_div, tipo="dividendo",
                    valor=div_valor, ticker=div_ticker,
                    descricao=div_desc or f"Dividendo {div_ticker.upper()}",
                    data_transacao=div_data
                )
                st.toast(f"Dividendo de {formatar_moeda(div_valor)} de {div_ticker.upper()} registrado! 💰".replace("$", r"\$"))
                st.rerun()

st.markdown("---")

# ---------------------------------------------------------------------------
# Tabela de Transações Consolidada
# ---------------------------------------------------------------------------
st.markdown("#### 📋 Histórico de Transações")

# Filtro por tipo
filtro_tipo = st.selectbox(
    "Filtrar por tipo:",
    ["todos", "aporte", "retirada", "compra", "venda", "dividendo"],
    format_func=lambda x: {
        "todos": "📊 Todos", "aporte": "📥 Aportes",
        "retirada": "📤 Retiradas", "compra": "🟢 Compras",
        "venda": "🔴 Vendas", "dividendo": "💰 Dividendos"
    }.get(x, x)
)

tipo_filtro = None if filtro_tipo == "todos" else filtro_tipo

# Coletar transações de todas as carteiras filtradas
todas_transacoes = []
for pt in carteiras_filtradas:
    trans = listar_transacoes_portfolio(pt["id"], tipo=tipo_filtro)
    for t in trans:
        t["carteira_nome"] = f"{pt['nome']} ({pt.get('persona_nome', '')})"
    todas_transacoes.extend(trans)

# Ordenar por data (mais recente primeiro)
todas_transacoes.sort(key=lambda t: t.get("data", ""), reverse=True)

if todas_transacoes:
    tipo_emoji = {
        "aporte": "📥", "retirada": "📤",
        "compra": "🟢", "venda": "🔴", "dividendo": "💰"
    }

    for t in todas_transacoes:
        emoji = tipo_emoji.get(t["tipo"], "📊")
        ticker_txt = f" — {t['ticker']}" if t.get('ticker') else ""
        qtd_txt = f" ({t['quantidade']}x @ {formatar_moeda_md(t['preco_unitario'])})" if t.get('quantidade') and t.get('preco_unitario') else ""
        desc_txt = f" · <em>{t['descricao']}</em>" if t.get('descricao') else ""
        carteira_txt = f" | 📂 {t.get('carteira_nome', '')}"

        if t["tipo"] in ("aporte", "venda", "dividendo"):
            valor_txt = f"+{formatar_moeda_md(t['valor'])}"
            cor = "#00C851"
        else:
            valor_txt = f"-{formatar_moeda_md(t['valor'])}"
            cor = "#FF4444"

        st.markdown(
            f"{emoji} **{t['tipo'].upper()}**{ticker_txt}{qtd_txt} | "
            f"<span style='color:{cor};font-weight:700'>{valor_txt}</span> | "
            f"📅 {formatar_data_br(t['data'])}{carteira_txt}{desc_txt}",
            unsafe_allow_html=True
        )

    # Gráfico de evolução
    st.markdown("---")
    st.markdown("#### 📈 Evolução do Caixa")

    transacoes_ordenadas = sorted(todas_transacoes, key=lambda t: t.get("data", ""))
    saldo = 0
    datas = []
    saldos = []

    for t in transacoes_ordenadas:
        if t["tipo"] in ("aporte", "venda", "dividendo"):
            saldo += t["valor"]
        else:
            saldo -= t["valor"]
        datas.append(t.get("data", ""))
        saldos.append(saldo)

    if datas:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=datas, y=saldos,
            mode="lines+markers", name="Saldo",
            line=dict(color="#667eea", width=3),
            marker=dict(size=6),
            fill="tozeroy",
            fillcolor="rgba(102, 126, 234, 0.1)"
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#333"),
            xaxis=dict(title="Data", color="#333", gridcolor="rgba(0,0,0,0.06)"),
            yaxis=dict(title="Saldo", color="#333", gridcolor="rgba(0,0,0,0.06)"),
            margin=dict(t=20, b=40, l=40, r=20),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Nenhuma transação registrada ainda. Use os formulários acima para começar.")
