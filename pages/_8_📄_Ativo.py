import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database.crud import (
    listar_personas_usuario, listar_portfolios_persona, listar_ativos_portfolio,
    adicionar_watchlist, buscar_portfolio_por_id, buscar_persona_por_id
)
from services.market_data import buscar_preco_atual, buscar_historico
import importlib
import services.market_data as _md
importlib.reload(_md)
buscar_dados_fundamentalistas = _md.buscar_dados_fundamentalistas
from services.news_scraper import buscar_noticias_ticker
from services.scoring import pontuar_ativo, gerar_texto_resumo
from services.recommendation import gerar_recomendacao_completa
from utils.helpers import formatar_moeda, formatar_moeda_md, formatar_percentual, nome_ativo, injetar_css_global

st.set_page_config(page_title="Detalhes do Ativo", page_icon="📄", layout="wide")
injetar_css_global()

if "user" not in st.session_state or st.session_state.user is None:
    st.warning("⚠️ Faça login.")
    st.stop()

ticker = st.session_state.get("view_asset_ticker", None)
if not ticker:
    st.error("Nenhum ativo selecionado.")
    if st.button("⬅️ Ir para Início"): st.switch_page("app.py")
    st.stop()

voltar_para = st.session_state.get("voltar_para_pagina", "app.py")
if st.button("⬅️ Voltar"):
    st.switch_page(voltar_para)

st.header(f"📄 {ticker} — {nome_ativo(ticker)}")

# --- DADOS DE MERCADO ---
with st.spinner("Buscando dados do mercado..."):
    cotacao = buscar_preco_atual(ticker)
    fundamentos = buscar_dados_fundamentalistas(ticker)
    
if not cotacao:
    st.error(f"Erro ao buscar cotação para o ativo {ticker}.")
    st.stop()
    
preco = cotacao.get("preco_atual", 0)
variacao = cotacao.get("variacao_dia", 0)

# Métricas principais em 1 linha
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Preço Atual", formatar_moeda(preco), f"{variacao:+.2f}%", help="Variação em relação ao fechamento do último pregão")
if fundamentos.get("pl"):
    col2.metric("P/L", f"{fundamentos['pl']:.1f}", help="Preço/Lucro: quanto o mercado paga por cada R\\$1 de lucro. Menor = mais barato")
if fundamentos.get("pvp"):
    col3.metric("P/VP", f"{fundamentos['pvp']:.2f}", help="Preço/Valor Patrimonial: relação entre preço de mercado e patrimônio líquido. Abaixo de 1 = negocia abaixo do patrimônio")
if fundamentos.get("dy"):
    col4.metric("Div. Yield", f"{fundamentos['dy']:.1f}%", help="Dividend Yield: rendimento anual estimado em dividendos")
if fundamentos.get("setor"):
    col5.metric("Setor", fundamentos["setor"][:20])

# --- REFERÊNCIA DO SETOR (P/VP, P/L, DY) ---
st.markdown("---")
st.markdown("#### 📊 Referência do Setor")

with st.spinner("Buscando dados de referência do setor..."):
    from services.market_data import buscar_referencia_setor
    ref = buscar_referencia_setor(ticker, fundamentos.get("setor"))

if ref and ref.get("peers_analisados", 0) > 0:
    st.caption(f"Setor: **{ref['setor']}** — {ref['peers_analisados']} peers analisados")
    
    # Montar tabela de referência
    indicadores_ref = []
    
    # Valores do ativo atual
    ativo_pvp = fundamentos.get("pvp")
    ativo_pl = fundamentos.get("pl")
    ativo_dy = fundamentos.get("dy")
    
    for nome_ind, dados_ref, val_ativo in [
        ("P/VP", ref.get("pvp", {}), ativo_pvp),
        ("P/L", ref.get("pl", {}), ativo_pl),
        ("DY (%)", ref.get("dy", {}), ativo_dy),
    ]:
        if dados_ref and dados_ref.get("min") is not None:
            indicadores_ref.append({
                "Indicador": nome_ind,
                f"{ticker}": f"{val_ativo:.2f}" if val_ativo else "—",
                "Mínimo": f"{dados_ref['min']:.2f}",
                "Máximo": f"{dados_ref['max']:.2f}",
                "Média": f"{dados_ref['media']:.2f}",
                "Moda": f"{dados_ref['moda']:.2f}",
            })
    
    if indicadores_ref:
        import pandas as pd
        df_ref = pd.DataFrame(indicadores_ref)
        st.dataframe(df_ref, use_container_width=True, hide_index=True)
    else:
        st.info("Dados de referência não disponíveis para este setor.")
else:
    st.info("Não foi possível obter dados de referência. Setor não identificado ou sem peers cadastrados.")

# --- AÇÕES RÁPIDAS ---
with st.expander("⚡ Ações Rápidas (Operações e Monitoramento)", expanded=True):
    personas = listar_personas_usuario(st.session_state.user['id'])
    if personas:
        opcoes_p = {p["id"]: p["nome"] for p in personas}
        
        # Tentar herdar a carteira que o usuario estava vendo
        port_id_herdados = st.session_state.get("view_portfolio_id")
        index_p = 0
        if port_id_herdados:
            # Achar a persona dona deste portfolio
            port_detalhe_herdado = buscar_portfolio_por_id(port_id_herdados)
            if port_detalhe_herdado:
                pid_herdado = port_detalhe_herdado.get("persona_id")
                lista_p_ids = list(opcoes_p.keys())
                if pid_herdado in lista_p_ids:
                    index_p = lista_p_ids.index(pid_herdado)
                    
        pid = st.selectbox("Selecione a Persona", list(opcoes_p.keys()), index=index_p, format_func=lambda x: opcoes_p[x])
        portfolios = listar_portfolios_persona(pid)
        
        if portfolios:
            opcoes_port = {pt["id"]: pt["nome"] for pt in portfolios}
            
            index_port = 0
            if port_id_herdados:
                lista_port_ids = list(opcoes_port.keys())
                if port_id_herdados in lista_port_ids:
                    index_port = lista_port_ids.index(port_id_herdados)
                    
            port_id = st.selectbox("Selecione a Carteira", list(opcoes_port.keys()), index=index_port, format_func=lambda x: opcoes_port[x])
            
            port_detalhe = buscar_portfolio_por_id(port_id)
            persona_detalhe = buscar_persona_por_id(pid)
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("👀 Adicionar à Watchlist", use_container_width=True):
                    adicionar_watchlist(port_id, ticker, manual=True)
                    st.success(f"{ticker} adicionado à watchlist da carteira '{opcoes_port[port_id]}'!")
            with c2:
                if st.button("📂 Ir para Carteira", use_container_width=True):
                    st.session_state.view_portfolio_id = port_id
                    st.switch_page("pages/_7_📂_Carteira_Detalhe.py")

            with st.expander("🛒 Registrar Compra", expanded=False):
                caixa_disp = port_detalhe.get('montante_disponivel', 0) if port_detalhe else 0
                st.markdown(f"**Saldo em caixa:** {formatar_moeda_md(caixa_disp)}", unsafe_allow_html=True)
                
                preco_atual_val = cotacao.get('preco_atual', 0) if isinstance(cotacao, dict) else 0
                if preco_atual_val > 0:
                    qtd_compra = st.number_input("Quantidade para comprar", min_value=1, value=1, step=1)
                    total_compra = qtd_compra * preco_atual_val
                    
                    st.markdown(f"**Preço unitário:** {formatar_moeda_md(preco_atual_val)}<br>**Total:** **{formatar_moeda_md(total_compra)}**", unsafe_allow_html=True)
                    
                    if total_compra > caixa_disp:
                        st.error("Saldo insuficiente para esta compra.")
                    else:
                        if st.button("Confirmar Compra", type="primary", use_container_width=True):
                            from database.crud import adicionar_ativo, atualizar_ativo, registrar_transacao, listar_ativos_portfolio
                            from datetime import date
                            ativos_cart = listar_ativos_portfolio(port_id)
                            ativo_existente = next((x for x in ativos_cart if x["ticker"] == ticker), None)
                            
                            if ativo_existente:
                                q_ant = ativo_existente["quantidade"]
                                p_ant = ativo_existente["preco_medio"]
                                q_nova = q_ant + qtd_compra
                                p_novo = ((q_ant * p_ant) + total_compra) / q_nova
                                atualizar_ativo(ativo_existente["id"], quantidade=q_nova, preco_medio=p_novo)
                            else:
                                adicionar_ativo(port_id, ticker, preco_atual_val, qtd_compra, date.today())
                            
                            registrar_transacao(port_id, "compra", total_compra, ticker, qtd_compra, preco_atual_val, "Compra Manual", date.today())
                            st.toast(f"{qtd_compra}x {ticker} comprados com sucesso! 🎉", icon="✅")
                            st.rerun()
                else:
                    st.warning("Não foi possível obter o preço atual do ativo para calcular a compra.")
            
            # Insights rapidos
            st.markdown("---")
            st.markdown(f"**Insights Rápidos para {opcoes_port[port_id]}:**")
            
            if port_detalhe and persona_detalhe:
                res = pontuar_ativo(ticker, persona_detalhe, port_detalhe)
                if res.get("sucesso"):
                    resumo = gerar_texto_resumo(ticker, res["indicadores"], res["score"])
                    st.info(f"**Score ({res['score']}):** {resumo}")
                    
                    # Botão IA
                    if st.button("💡 Análise Inteligente com IA", key=f"ia_btn_{ticker}"):
                        with st.spinner("🧠 Analisando com IA..."):
                            rec = gerar_recomendacao_completa(ticker, pid, port_id)
                            if rec.get("sucesso"):
                                st.success(f"**[IA - {rec['recomendacao'].get('confianca', 0)}% Trust]**\n\n{rec['recomendacao']['explicacao']}")
                            else:
                                st.error(rec.get("erro", "Falha na IA"))
        else:
            st.warning("Esta persona não tem carteiras criadas.")
    else:
        st.warning("Você não tem personas cadastradas.")

# --- GRÁFICO COM SELETORES ---
st.subheader("Gráfico de Candlestick")

gc1, gc2 = st.columns(2)
with gc1:
    periodo_opcoes = {"1 Mês": "1mo", "3 Meses": "3mo", "6 Meses": "6mo", "1 Ano": "1y", "2 Anos": "2y", "5 Anos": "5y"}
    periodo_label = st.selectbox("Período", list(periodo_opcoes.keys()), index=2)
    periodo_val = periodo_opcoes[periodo_label]

with gc2:
    intervalo_opcoes = {"Diário": "1d", "Semanal": "1wk", "Mensal": "1mo"}
    intervalo_label = st.selectbox("Intervalo das Velas", list(intervalo_opcoes.keys()), index=0)
    intervalo_val = intervalo_opcoes[intervalo_label]

with st.spinner("Carregando gráfico..."):
    try:
        from services.market_data import _formatar_ticker_br
        import yfinance as yf
        ticker_sa = _formatar_ticker_br(ticker)
        ativo_yf = yf.Ticker(ticker_sa)
        historico = ativo_yf.history(period=periodo_val, interval=intervalo_val)
    except Exception:
        historico = buscar_historico(ticker, periodo=periodo_val)

if historico is not None and not historico.empty:
    fig = go.Figure(data=[go.Candlestick(
        x=historico.index,
        open=historico['Open'],
        high=historico['High'],
        low=historico['Low'],
        close=historico['Close']
    )])
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=0, b=0),
        template="plotly_white",
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Dados históricos indisponíveis para este período/intervalo.")

# --- NOTÍCIAS (ordenadas por data) ---
st.subheader("📰 Notícias Recentes")
with st.spinner("Buscando notícias..."):
    noticias = buscar_noticias_ticker(ticker, max_resultados=5)
    
if noticias:
    # Ordenar por data (mais recente primeiro)
    noticias_ordenadas = sorted(noticias, key=lambda n: n.get('data', ''), reverse=True)
    for n in noticias_ordenadas:
        with st.container(border=True):
            st.markdown(f"**[{n['titulo']}]({n['link']})**")
            if 'data' in n:
                st.caption(f"Publicado em: {n['data']}")
else:
    st.info("Nenhuma notícia relevante encontrada nos últimos dias.")
