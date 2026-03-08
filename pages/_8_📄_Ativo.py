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

# Métricas de preço em destaque
col_p1, col_p2, col_p3 = st.columns(3)
col_p1.metric("Preço Atual", formatar_moeda(preco), f"{variacao:+.2f}%", help="Variação em relação ao fechamento do último pregão")
if fundamentos.get("setor"):
    col_p2.metric("Setor", fundamentos["setor"][:25])
if fundamentos.get("industria") and fundamentos["industria"] != fundamentos.get("setor"):
    col_p3.metric("Indústria", fundamentos["industria"][:25])

# --- TABELA DE INDICADORES FUNDAMENTALISTAS E REFERÊNCIA DO SETOR ---
st.markdown("---")
st.markdown("#### 📊 Indicadores e Referência do Setor")

with st.spinner("Buscando dados de referência do setor..."):
    from services.market_data import buscar_referencia_setor
    ref = buscar_referencia_setor(ticker, fundamentos.get("setor"))

if ref and ref.get("peers_analisados", 0) > 0:
    st.caption(f"Setor: **{ref['setor']}** — {ref['peers_analisados']} peers do mesmo setor usados para as médias abaixo.")
else:
    st.caption("Sem dados de referência de setor suficientes para comparação.")

def _fmt_moeda_compacta(val):
    """Formata valores monetários grandes de forma compacta."""
    if val is None: return "—"
    try:
        val = float(val)
    except (ValueError, TypeError):
        return "—"
    if abs(val) >= 1e12: return f"R$ {val/1e12:.2f} T"
    if abs(val) >= 1e9: return f"R$ {val/1e9:.2f} B"
    if abs(val) >= 1e6: return f"R$ {val/1e6:.1f} M"
    return f"R$ {val:,.0f}".replace(",", ".")

def _fmt_pct(val):
    if val is None: return "—"
    return f"{val:.2f}%"

def _fmt_num(val, decimals=2):
    if val is None: return "—"
    return f"{val:.{decimals}f}"

# Definição de todos os indicadores com tooltip
# (chave_no_dict, nome_exibição, tooltip, função_de_formatação)
indicadores_config = {
    "📈 Valuation": [
        ("pl",                "P/L",                "Preço/Lucro: quanto o mercado paga por cada R$1 de lucro. Menor pode indicar ativo mais barato.",     lambda v: _fmt_num(v, 1)),
        ("pvp",               "P/VP",               "Preço/Valor Patrimonial: relação entre preço de mercado e patrimônio líquido. Abaixo de 1 = negocia abaixo do patrimônio.",     lambda v: _fmt_num(v)),
        ("ev_ebitda",         "EV/EBITDA",          "Enterprise Value / EBITDA: valuation da empresa incluindo dívida. Menor = mais barato.",           lambda v: _fmt_num(v)),
        ("peg_ratio",         "PEG Ratio",          "P/L dividido pelo crescimento de lucros. PEG < 1 pode indicar ação subvalorizada para seu crescimento.",          lambda v: _fmt_num(v)),
        ("preco_sobre_vendas","P/Vendas",           "Preço/Receita: quanto se paga por cada R$1 de receita. Útil para empresas sem lucro.",           lambda v: _fmt_num(v)),
    ],
    "💰 Rentabilidade": [
        ("roe",               "ROE",                "Return on Equity: retorno sobre o patrimônio líquido. Mede eficiência do capital próprio. Acima de 15% é considerado bom.",   lambda v: _fmt_pct(v)),
        ("roa",               "ROA",                "Return on Assets: retorno sobre ativos totais. Mede eficiência do uso dos ativos da empresa.",   lambda v: _fmt_pct(v)),
    ],
    "🏦 Endividamento": [
        ("divida_pl",         "Dívida/PL",          "Dívida Líquida / Patrimônio Líquido: quanto de dívida para cada R$1 de patrimônio. Acima de 100% merece atenção.",      lambda v: _fmt_num(v)),
        ("liquidez_corrente", "Liquidez Corrente",   "Ativo circulante / Passivo circulante. Acima de 1 indica capacidade de pagar dívidas de curto prazo.",    lambda v: _fmt_num(v)),
    ],
    "📊 Margens": [
        ("margem_bruta",      "Margem Bruta",       "Lucro bruto / Receita líquida. Indica o quanto sobra da receita após custos diretos de produção.",   lambda v: _fmt_pct(v)),
        ("margem_operacional","Margem Operacional",  "Lucro operacional / Receita. Mostra eficiência operacional antes de juros e impostos.",    lambda v: _fmt_pct(v)),
        ("margem_liquida",    "Margem Líquida",     "Lucro líquido / Receita líquida. Indica o percentual de lucro final por cada R$1 de receita.",   lambda v: _fmt_pct(v)),
    ],
    "🚀 Crescimento": [
        ("crescimento_receita","Cresc. Receita",    "Crescimento da receita no último período reportado em relação ao anterior.",                  lambda v: _fmt_pct(v)),
        ("crescimento_lucro",  "Cresc. Lucro",      "Crescimento do lucro no último período reportado em relação ao anterior.",                    lambda v: _fmt_pct(v)),
    ],
    "🪙 Dividendos": [
        ("dy",                "Dividend Yield",     "Rendimento anual estimado de dividendos em relação ao preço atual.",                        lambda v: _fmt_pct(v)),
        ("dividend_rate",     "Dividendo/Cota (R$)","Valor em reais dos dividendos pagos por ação/cota nos últimos 12 meses.",                    lambda v: f"R$ {v:.2f}" if v else "—"),
        ("payout",            "Payout",             "Percentual do lucro líquido distribuído como dividendos. Payout > 100% pode não ser sustentável.",   lambda v: _fmt_pct(v)),
        ("dy_medio_5_anos",   "DY Médio 5 Anos",   "Dividend Yield médio dos últimos 5 anos. Útil para comparar com o DY atual.",               lambda v: f"{v:.2f}%" if v else "—"),
    ],
    "🌐 Mercado": [
        ("market_cap",        "Valor de Mercado",   "Capitalização de mercado: preço da ação × total de ações emitidas.",                        _fmt_moeda_compacta),
        ("ebitda",            "EBITDA",             "Lucro antes de juros, impostos, depreciação e amortização. Proxy de geração de caixa operacional.",  _fmt_moeda_compacta),
        ("fluxo_caixa_livre", "Fluxo Cx. Livre",   "Free Cash Flow: caixa gerado disponível após investimentos. Indica capacidade de pagar dividendos e reduzir dívida.",     _fmt_moeda_compacta),
        ("beta",              "Beta",               "Volatilidade em relação ao mercado. Beta 1 = igual ao mercado. > 1 = mais volátil. < 1 = menos volátil.",  lambda v: _fmt_num(v, 3)),
        ("var_52_semanas",    "Var. 52 Semanas",    "Variação percentual do preço nos últimos 12 meses.",                                        lambda v: _fmt_pct(v)),
    ],
    "🎯 Analistas": [
        ("consenso_analistas","Consenso",           "Recomendação consensual dos analistas que cobrem o ativo (buy, hold, sell).",                lambda v: {"buy":"🟢 Compra","hold":"🟡 Neutro","sell":"🔴 Venda","strong_buy":"🟢 Compra Forte","underperform":"🔴 Abaixo","none":"—"}.get(v, v or "—")),
        ("preco_alvo_medio",  "Preço-Alvo Médio",   "Média dos preços-alvo definidos pelos analistas para os próximos 12 meses.",                lambda v: f"R$ {v:.2f}" if v else "—"),
        ("preco_alvo_min",    "Preço-Alvo Mín.",    "Preço-alvo mais pessimista entre os analistas.",                                            lambda v: f"R$ {v:.2f}" if v else "—"),
        ("preco_alvo_max",    "Preço-Alvo Máx.",    "Preço-alvo mais otimista entre os analistas.",                                              lambda v: f"R$ {v:.2f}" if v else "—"),
        ("num_analistas",     "Nº Analistas",       "Quantidade de analistas que cobrem este ativo.",                                            lambda v: str(v) if v else "—"),
    ],
}

# CSS para tabela
st.markdown("""
<style>
.fund-table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
.fund-table th { text-align: left; padding: 8px 10px; border-bottom: 2px solid #444; font-size: 0.85rem; color: #aaa; }
.fund-table td { padding: 6px 10px; border-bottom: 1px solid rgba(128,128,128,0.15); }
.fund-table td.val-col { text-align: right; font-weight: 600; }
.fund-table td.ref-col { text-align: right; color: #888; font-size: 0.85rem; }
.fund-table .cat-cell { vertical-align: middle; font-weight: 700; color: #444; background: rgba(128,128,128,0.05); border-right: 1px solid rgba(128,128,128,0.15); width: 15%; }
.ind-name { cursor: help; border-bottom: 1px dotted #888; }
</style>
""", unsafe_allow_html=True)

# Montar HTML da tabela fundida
html_rows = (
    '<thead><tr>'
    '<th>Categoria</th>'
    '<th>Indicador</th>'
    f'<th style="text-align: right;">{ticker}</th>'
    '<th style="text-align: right; color: #888;">Mín. Setor</th>'
    '<th style="text-align: right; color: #888;">Média Setor</th>'
    '<th style="text-align: right; color: #888;">Máx. Setor</th>'
    '</tr></thead><tbody>\n'
)

has_data = False
for categoria, indicadores in indicadores_config.items():
    # Filtrar linhas com dados
    linhas_com_dados = [(k, nome, tip, fmt) for k, nome, tip, fmt in indicadores if fundamentos.get(k) is not None]
    if not linhas_com_dados:
        continue
        
    has_data = True
    rowspan = len(linhas_com_dados)
    
    for i, (chave, nome_ind, tooltip, fmt_fn) in enumerate(linhas_com_dados):
        valor = fundamentos.get(chave)
        valor_fmt = fmt_fn(valor)
        
        # Obter ref se existir
        r_min = r_med = r_max = "—"
        if ref and chave in ref:
            dados_ref = ref.get(chave, {})
            if dados_ref and dados_ref.get("min") is not None:
                r_min = fmt_fn(dados_ref.get("min"))
                r_med = fmt_fn(dados_ref.get("media"))
                r_max = fmt_fn(dados_ref.get("max"))
                
        html_rows += '<tr>'
        if i == 0:
            html_rows += f'<td rowspan="{rowspan}" class="cat-cell">{categoria}</td>'
            
        html_rows += (
            f'<td><span class="ind-name" title="{tooltip}">{nome_ind}</span></td>'
            f'<td class="val-col">{valor_fmt}</td>'
            f'<td class="ref-col">{r_min}</td>'
            f'<td class="ref-col">{r_med}</td>'
            f'<td class="ref-col">{r_max}</td>'
            f'</tr>\n'
        )

html_rows += '</tbody>'

if has_data:
    st.markdown(f'<table class="fund-table">{html_rows}</table>', unsafe_allow_html=True)
else:
    st.info("Dados fundamentalistas indisponíveis para este ativo.")

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
