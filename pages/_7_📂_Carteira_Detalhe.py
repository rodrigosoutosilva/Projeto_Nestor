import streamlit as st
import pandas as pd
from datetime import date
from database.crud import (
    buscar_portfolio_por_id, atualizar_portfolio, deletar_portfolio,
    listar_ativos_portfolio, adicionar_ativo, atualizar_ativo, deletar_ativo,
    registrar_transacao, listar_acoes_portfolio, atualizar_status_acao, deletar_acao_planejada,
    adicionar_watchlist, listar_watchlist_portfolio, remover_watchlist,
    buscar_persona_por_id, resumo_transacoes_portfolio
)
from services.scoring import gerar_sugestoes_carteira
from services.recommendation import gerar_recomendacao_completa
from services.market_data import buscar_preco_atual
from utils.helpers import formatar_moeda, formatar_moeda_md, formatar_data_br, nome_ativo

st.set_page_config(page_title="Detalhes da Carteira", page_icon="📂", layout="wide")

if "user" not in st.session_state or st.session_state.user is None:
    st.warning("⚠️ Faça login na página principal primeiro.")
    st.stop()

# --- CARREGAMENTO ---
portfolio_id = st.session_state.get("view_portfolio_id", None)
if not portfolio_id:
    st.error("Nenhuma carteira selecionada. Volte e selecione uma na página 'Carteiras'.")
    if st.button("⬅️ Voltar para Carteiras", key="btn_volt_err"):
        st.switch_page("pages/3_💼_Carteiras.py")
    st.stop()

port = buscar_portfolio_por_id(portfolio_id)
if not port:
    st.error("Carteira não encontrada.")
    st.stop()

persona = buscar_persona_por_id(port["persona_id"])
ativos = listar_ativos_portfolio(portfolio_id)
watchlist = listar_watchlist_portfolio(portfolio_id)

if st.button("⬅️ Voltar para Carteiras", key="btn_volt_topo"):
    st.switch_page("pages/3_💼_Carteiras.py")

# --- CABEÇALHO COMPACTO ---
tipo_emoji = {"acoes": "📈", "fiis": "🏢", "misto": "🔀"}.get(port["tipo_ativo"], "📊")
st.header(f"{tipo_emoji} {port['nome']}")
st.caption(f"Persona: **{persona['nome'] if persona else 'N/A'}** | Prazo: {port['objetivo_prazo'].capitalize()} | Meta DY: {port['meta_dividendos']}%")

# Métricas financeiras compactas
caixa = port.get("montante_disponivel", 0)
resumo_fin = resumo_transacoes_portfolio(portfolio_id)
patrimonio = 0
for a in ativos:
    dados_p = buscar_preco_atual(a["ticker"])
    if dados_p and isinstance(dados_p, dict):
        patrimonio += a["quantidade"] * dados_p.get("preco_atual", a["preco_medio"])
    else:
        patrimonio += a["quantidade"] * a["preco_medio"]

valor_total = caixa + patrimonio
total_aportado = resumo_fin["total_aportes"]
lucro_acum = valor_total - total_aportado if total_aportado > 0 else 0
lucro_pct = (lucro_acum / total_aportado * 100) if total_aportado > 0 else 0

mh1, mh2, mh3, mh4, mh5 = st.columns(5)
mh1.metric("💎 Valor Total", formatar_moeda(valor_total))
mh2.metric("🏦 Caixa", formatar_moeda(caixa))
mh3.metric("📊 Patrimônio", formatar_moeda(patrimonio))
cor_delta = "normal" if lucro_acum >= 0 else "inverse"
mh4.metric("📈 Lucro", formatar_moeda(lucro_acum), help="Valor Total − Total Aportado")
mh5.metric("📉 Rendimento", f"{lucro_pct:+.1f}%", help="Lucro acumulado / Total aportado")

with st.expander("✏️ Editar Configurações da Carteira"):
    with st.form("form_edit_port"):
        e_nome = st.text_input("Nome", value=port["nome"])
        
        c_fix, c_ap = st.columns([1, 2])
        with c_fix:
            st.metric("Caixa Atual Registrado", formatar_moeda(port.get("montante_disponivel", 0)))
            st.caption("Para inserir mais caixa, registre um **Aporte** no painel de Gestão.")
        
        with c_ap:
            e_aporte = st.number_input("Aporte Periódico (R$)", value=float(port.get("aporte_periodico", 0)), step=50.0)
            e_freq = st.selectbox("Frequência Aporte", ["", "semanal", "quinzenal", "mensal"], index=["", "semanal", "quinzenal", "mensal"].index(port.get("frequencia_aporte", "")))
        
        if st.form_submit_button("Salvar Edição"):
            # Caixa não é listado no db-commit
            atualizar_portfolio(port["id"], nome=e_nome, aporte_periodico=e_aporte, frequencia_aporte=e_freq)
            st.toast("Carteira atualizada! ✅")
            st.rerun()

st.markdown("---")

# --- TABS: ATIVOS | MONITORANDO | SUGESTÕES ---
tab1, tab2, tab3 = st.tabs(["📊 Meus Ativos", "👁️ Monitorando", "⚡ Sugestões da Carteira"])

with tab1:
    st.markdown("### Ativos Atuais")
    
    if ativos:
        for a in ativos:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                with c1:
                    st.markdown(f"**{a['ticker']}** - {nome_ativo(a['ticker'])}")
                    st.caption(f"Posição desde: {formatar_data_br(a['data_posicao'])}")
                with c2:
                    st.markdown(f"**Qtd:** {a['quantidade']}")
                with c3:
                    st.markdown(f"**Preço Médio:** {formatar_moeda_md(a['preco_medio'])}", unsafe_allow_html=True)
                with c4:
                    col_bi, col_bd = st.columns(2)
                    with col_bi:
                        if st.button("ℹ️ Info", key=f"info_{a['id']}", use_container_width=True):
                            st.session_state.view_asset_ticker = a["ticker"]
                            st.session_state.voltar_para_pagina = "pages/_7_📂_Carteira_Detalhe.py"
                            st.switch_page("pages/_8_📄_Ativo.py")
                    with col_bd:
                        if st.button("🗑️ Excluir", key=f"del_{a['id']}", use_container_width=True):
                            deletar_ativo(a["id"])
                            st.rerun()
                            
        st.info("Sua carteira ainda não possui ativos.")
        
    st.markdown("#### 🛒 Movimentações Financeiras")
    st.markdown("Para realizar Aportes, Compras ou Vendas nesta carteira:")
    if st.button("➡️ Registrar Movimentação no Painel de Gestão", type="primary"):
        st.session_state.filtro_carteira_gestao = port["nome"]
        st.switch_page("pages/6_📜_Gestao_Financeira.py")

with tab2:
    st.subheader("Ativos em Monitoramento")
    
    with st.form("add_watchlist"):
        c1, c2 = st.columns([3, 1])
        with c1: novo_watch = st.text_input("Adicionar Ticker à Watchlist", placeholder="VALE3")
        with c2: 
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("➕ Adicionar", use_container_width=True) and novo_watch:
                adicionar_watchlist(portfolio_id, novo_watch)
                st.rerun()
                
    if watchlist:
        for w in watchlist:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    st.markdown(f"**{w['ticker']}** - {nome_ativo(w['ticker'])}")
                    if w["adicionado_manualmente"]: st.caption("Adicionado manualmente")
                    else: st.caption("Sugerido pela IA")
                with c2:
                    if st.button("ℹ️ Info", key=f"w_info_{w['id']}", use_container_width=True):
                        st.session_state.view_asset_ticker = w["ticker"]
                        st.session_state.voltar_para_pagina = "pages/_7_📂_Carteira_Detalhe.py"
                        st.switch_page("pages/_8_📄_Ativo.py")
                with c3:
                    if st.button("🗑️", key=f"w_del_{w['id']}", help="Remover", use_container_width=True):
                        remover_watchlist(w["id"])
                        st.rerun()
    else:
        st.info("Sua watchlist está vazia.")

with tab3:
    st.subheader("Sugestões de Movimentos")
    st.markdown("O sistema pontuou seus ativos e sugere movimentos através de algoritmo local. Para uma análise profunda com Inteligência Artificial, clique nos botões de IA abaixo.")
    
    # 1. Botão Geral de IA Inteligente da Carteira toda
    if st.button("💡 Gerar Sugestões da Carteira com IA", type="primary", use_container_width=True):
        st.session_state["ia_loading_geral"] = True
    
    if st.session_state.get("ia_loading_geral"):
        with st.spinner("🧠 Analisando carteira com IA (Pode demorar um pouco)..."):
            from services.ai_brain import gerar_sugestoes_compra
            portfolios_analise = buscar_portfolio_por_id(portfolio_id)
            rec_geral = gerar_sugestoes_compra(ativos, persona, portfolios_analise)
            
            if rec_geral and rec_geral.get("sucesso"):
                st.session_state["ia_resumo_geral"] = rec_geral.get("resumo", "")
                st.session_state["ia_sugestoes_raw"] = rec_geral.get("sugestoes", [])
                st.session_state["ia_loading_geral"] = False
            else:
                st.error(rec_geral.get("resumo", "Falha ao consultar IA. Tente novamente."))
                st.session_state["ia_loading_geral"] = False
                
    if st.session_state.get("ia_resumo_geral"):
        st.success(f"✅ **Análise da IA:** {st.session_state['ia_resumo_geral']}")
        sugestoes_ia = st.session_state.get("ia_sugestoes_raw", [])
        for i, sug in enumerate(sugestoes_ia):
            with st.container(border=True):
                col1, col2, col3 = st.columns([1.5, 4, 1.5])
                ticker_sug = sug.get("ticker", "")
                qtd_sug = sug.get("quantidade", 1)
                preco_sug = sug.get("preco_estimado", 0.0)
                
                with col1:
                    st.markdown(f"**{ticker_sug}**")
                    st.caption(sug.get("tipo", "Ação/FII"))
                with col2:
                    st.markdown(f"**Ação:** {sug.get('acao', 'COMPRAR').upper()} | **Preço Unit:** {formatar_moeda_md(preco_sug)}", unsafe_allow_html=True)
                    st.caption(sug.get("motivo", ""))
                with col3:
                    qtd_escolhida = st.number_input(f"Qtd sugerida:", min_value=1, value=qtd_sug, key=f"qtd_ia_{i}_{ticker_sug}")
                    valor_total = qtd_escolhida * preco_sug
                    caixa = port.get("montante_disponivel", 0)
                    
                    block_btn = False
                    if valor_total > caixa and sug.get("acao", "compra").lower() == "compra":
                        aviso_txt = f"Caixa insuficiente. Custará {formatar_moeda(valor_total)}, mas você tem {formatar_moeda(caixa)}.".replace("$", r"\$")
                        st.warning(aviso_txt, icon="⚠️")
                        block_btn = True
                    else:
                        st.markdown(f"**Total Estimado:** {formatar_moeda_md(valor_total)}", unsafe_allow_html=True)
                        
                    if st.button("🛒 Seguir Sugestão", disabled=block_btn, key=f"exec_ia_{ticker_sug}_{i}", use_container_width=True):
                        if sug.get("acao", "compra").lower() == "venda":
                            ativo_existente = next((x for x in ativos if x["ticker"] == ticker_sug), None)
                            if not ativo_existente or qtd_escolhida > ativo_existente["quantidade"]:
                                st.toast("Quantidade insuficiente em carteira para venda!", icon="❌")
                            else:
                                nova_qtd = ativo_existente["quantidade"] - qtd_escolhida
                                if nova_qtd <= 0:
                                    deletar_ativo(ativo_existente["id"])
                                else:
                                    atualizar_ativo(ativo_existente["id"], quantidade=nova_qtd, preco_medio=ativo_existente["preco_medio"])
                                registrar_transacao(port["id"], "venda", valor_total, ticker_sug, qtd_escolhida, preco_sug, "Venda IA Executada", date.today())
                                st.toast(f"{qtd_escolhida}x {ticker_sug} vendidos com sucesso! 🎉", icon="✅")
                                st.rerun()
                        else:
                            ativo_existente = next((x for x in ativos if x["ticker"] == ticker_sug), None)
                            if ativo_existente:
                                q_ant = ativo_existente["quantidade"]
                                p_ant = ativo_existente["preco_medio"]
                                q_nova = q_ant + qtd_escolhida
                                p_novo = ((q_ant * p_ant) + valor_total) / q_nova
                                atualizar_ativo(ativo_existente["id"], quantidade=q_nova, preco_medio=p_novo)
                            else:
                                adicionar_ativo(port["id"], ticker_sug, preco_sug, qtd_escolhida, date.today())
                            
                            registrar_transacao(port["id"], "compra", valor_total, ticker_sug, qtd_escolhida, preco_sug, "Compra IA Executada", date.today())
                            st.toast(f"{qtd_escolhida}x {ticker_sug} comprados com sucesso! 🎉", icon="✅")
                            st.rerun()
        st.markdown("---")
        
    # 2. Recomendações locais (Algoritmo) + IA individual
    st.markdown("#### Sugestões do Algoritmo Técnico")
    sugestoes = gerar_sugestoes_carteira(portfolio_id)
    
    if sugestoes:
        for s in sugestoes:
            with st.container(border=True):
                novo_label = " 🆕 **NOVO**" if s.get("novo") else ""
                c1, c2 = st.columns([5, 2])
                with c1:
                    st.markdown(f"### {s['ticker']}{novo_label}")
                    st.caption(nome_ativo(s['ticker']))
                    cor_acao = "#00C851" if s['acao'] == "compra" else "#FF4444" if s['acao'] == "venda" else "#FFBB33" if s['acao'] == "observar" else "#888"
                    # Resgatar cotacao real pro card
                    preco_sug_inline = 0.0
                    from services.market_data import buscar_preco_atual
                    cot = buscar_preco_atual(s["ticker"])
                    if isinstance(cot, dict) and cot.get("preco_atual", 0) > 0:
                        preco_sug_inline = float(cot["preco_atual"])
                        
                    st.markdown(f"**Ação sugerida:** <span style='color:{cor_acao}'>{s['acao'].upper()}</span> (Score: {s['score']}/100) | **Preço Unit:** {formatar_moeda_md(preco_sug_inline)}", unsafe_allow_html=True)
                    st.info(s['texto'])
                with c2:
                    c_bi, c_bia = st.columns(2)
                    with c_bi:
                        if st.button("ℹ️ Info", key=f"alc_i_{s['ticker']}", use_container_width=True):
                            st.session_state.view_asset_ticker = s['ticker']
                            st.session_state.voltar_para_pagina = "pages/_7_📂_Carteira_Detalhe.py"
                            st.switch_page("pages/_8_📄_Ativo.py")
                    with c_bia:
                        if st.button("💡 Análise IA", key=f"btn_ia_{s['ticker']}", use_container_width=True):
                            st.session_state[f"run_ia_{s['ticker']}"] = True
                        
                if st.session_state.get(f"run_ia_{s['ticker']}"):
                    with st.spinner(f"Consultando IA para {s['ticker']}..."):
                        rec_ia = gerar_recomendacao_completa(s['ticker'], persona["id"], portfolio_id)
                        st.session_state[f"res_ia_{s['ticker']}"] = rec_ia
                        st.session_state[f"run_ia_{s['ticker']}"] = False
                        
                if st.session_state.get(f"res_ia_{s['ticker']}"):
                    rec = st.session_state[f"res_ia_{s['ticker']}"]
                    st.markdown("---")
                    if rec["sucesso"]:
                        st.success(f"**Visão da IA ({rec['recomendacao']['confianca']}% confiança):** {rec['recomendacao']['explicacao']}")
                    else:
                        st.error(rec.get("erro", "Erro ao consultar IA."))
    else:
        st.info("Nenhuma sugestão encontrada. Adicione ativos ou configure os setores preferidos da carteira para receber sugestões.")

st.markdown("---")

# --- MOVIMENTAÇÕES AGENDADAS ---
st.subheader("📅 Movimentações Agendadas")
acoes_pendentes = listar_acoes_portfolio(portfolio_id, status="planejado")

if acoes_pendentes:
    for acao in acoes_pendentes:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                st.markdown(f"**{acao['asset_ticker']}** - {acao['tipo_acao'].upper()}")
                if acao['explicacao']:
                    st.caption(acao['explicacao'])
            with c2:
                st.markdown(f"**Data Planejada:** {formatar_data_br(acao['data_planejada'])}")
            with c3:
                sc1, sc2 = st.columns(2)
                with sc1:
                    if st.button("✅ Executar", key=f"exec_{acao['id']}", use_container_width=True):
                        # Executar significa concluir o agendamento
                        atualizar_status_acao(acao['id'], "executado")
                        # (O ideal seria abrir o modal de compra para confirmar os valores, mas para manter fluidez, marcamos como executado e o usuario registra a compra manual se quiser)
                        st.toast(f"Movimento {acao['asset_ticker']} marcado como executado! Registre a transação na aba Meus Ativos se necessário.")
                        st.rerun()
                with sc2:
                    if st.button("🗑️ Ignorar", key=f"ign_{acao['id']}", use_container_width=True):
                        atualizar_status_acao(acao['id'], "ignorado")
                        st.rerun()
else:
    st.info("Nenhuma movimentação programada.")

st.markdown("---")
if st.button("⚠️ Excluir Carteira Inteira", type="primary"):
    deletar_portfolio(portfolio_id)
    st.session_state.view_portfolio_id = None
    st.switch_page("pages/3_💼_Carteiras.py")
