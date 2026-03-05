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
from services.market_data import buscar_preco_atual, buscar_dados_fundamentalistas, buscar_historico, calcular_indicadores_tecnicos
from utils.helpers import formatar_moeda, formatar_moeda_md, formatar_data_br, nome_ativo, injetar_css_global

st.set_page_config(page_title="Detalhes da Carteira", page_icon="📂", layout="wide")
injetar_css_global()

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

btn_col1, btn_col2 = st.columns([1, 1])
with btn_col1:
    persona_nome = persona['nome'] if persona else 'Persona'
    if st.button(f"⬅️ {persona_nome}", key="btn_volt_persona", use_container_width=True):
        st.session_state.view_persona_id = port["persona_id"]
        st.switch_page("pages/_9_🧑_Persona_Detalhe.py")
with btn_col2:
    if st.button("Carteiras", key="btn_volt_carteiras", use_container_width=True):
        st.switch_page("pages/3_💼_Carteiras.py")

# --- CABEÇALHO ---
tipo_emoji = {"acoes": "📈", "fiis": "🏢", "misto": "🔀"}.get(port["tipo_ativo"], "📊")
st.markdown(f"""
<style>.big-name {{ font-size: 1.76rem !important; font-weight: 700 !important; margin-bottom: 0.3rem; }}</style>
<div class='big-name'>{tipo_emoji} {port['nome']}</div>
""", unsafe_allow_html=True)
st.caption(f"Persona: **{persona['nome'] if persona else 'N/A'}** | Prazo: {port['objetivo_prazo'].capitalize()} | Meta DY: {port['meta_dividendos']}%")

# CSS para métricas maiores nesta página
st.markdown("""<style>
[data-testid="stMetricValue"] > div { font-size: 1.5rem !important; font-weight: 700 !important; }
[data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 700 !important; }
</style>""", unsafe_allow_html=True)

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
total_aportado = resumo_fin["total_aportes"] - resumo_fin["total_retiradas"]
lucro_acum = valor_total - total_aportado if total_aportado > 0 else 0
lucro_pct = (lucro_acum / total_aportado * 100) if total_aportado > 0 else 0

mh1, mh2, mh3, mh4, mh5 = st.columns(5)
mh1.metric("💎 Valor Total", formatar_moeda(valor_total))
mh2.metric("🏦 Caixa", formatar_moeda(caixa))
mh3.metric("📊 Patrimônio", formatar_moeda(patrimonio))
cor_delta = "normal" if lucro_acum >= 0 else "inverse"
mh4.metric("📈 Lucro", formatar_moeda(lucro_acum), help="Valor Total − Total Aportado")
mh5.metric("📉 Rendimento", f"{lucro_pct:+.1f}%", help="Lucro acumulado / Total aportado")

# --- 3 BOTÕES DE AÇÃO INLINE ---
btn_c1, btn_c2, btn_c3 = st.columns(3)
with btn_c1:
    if st.button("✏️ Editar Carteira", key="tgl_edit", use_container_width=True):
        st.session_state["show_edit_port"] = not st.session_state.get("show_edit_port", False)
        st.session_state["show_aporte"] = False
        st.session_state["show_compra_dir"] = False
        st.rerun()
with btn_c2:
    if st.button("📥 Aporte / Retirada", key="tgl_aporte", use_container_width=True):
        st.session_state["show_aporte"] = not st.session_state.get("show_aporte", False)
        st.session_state["show_edit_port"] = False
        st.session_state["show_compra_dir"] = False
        st.rerun()
with btn_c3:
    if st.button("🛒 Comprar Ativo", key="tgl_compra", use_container_width=True):
        st.session_state["show_compra_dir"] = not st.session_state.get("show_compra_dir", False)
        st.session_state["show_edit_port"] = False
        st.session_state["show_aporte"] = False
        st.rerun()

# Painel: Editar Carteira
if st.session_state.get("show_edit_port"):
    with st.container(border=True):
        with st.form("form_edit_port"):
            e_nome = st.text_input("Nome", value=port["nome"])
            c_fix, c_ap = st.columns([1, 2])
            with c_fix:
                st.metric("Caixa Atual Registrado", formatar_moeda(port.get("montante_disponivel", 0)))
                st.caption("Para inserir mais caixa, registre um **Aporte**.")
            with c_ap:
                e_aporte = st.number_input("Aporte Periódico (R$)", value=float(port.get("aporte_periodico", 0)), step=50.0)
                e_freq = st.selectbox("Frequência Aporte", ["", "semanal", "quinzenal", "mensal"], index=["", "semanal", "quinzenal", "mensal"].index(port.get("frequencia_aporte", "")))
            if st.form_submit_button("Salvar Edição"):
                atualizar_portfolio(port["id"], nome=e_nome, aporte_periodico=e_aporte, frequencia_aporte=e_freq)
                st.session_state["show_edit_port"] = False
                st.toast("Carteira atualizada! ✅")
                st.rerun()

# Painel: Aporte / Retirada
if st.session_state.get("show_aporte"):
    with st.container(border=True):
        c_ap1, c_ap2, c_ap3, c_ap4 = st.columns([2, 3, 3, 4])
        with c_ap1:
            tipo_movimento = st.selectbox("Movimento", ["Aporte (+)", "Retirada (-)"], key="tipo_mov_caixa")
        with c_ap2:
            valor_movimento = st.number_input("Valor (R$)", min_value=0.01, value=100.0, step=50.0, key="valor_mov_caixa")
        with c_ap3:
            data_movimento = st.date_input("Data", value=date.today(), key="data_mov_caixa")
        with c_ap4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✅ Confirmar", key="btn_conf_mov_caixa", type="primary", use_container_width=True):
                tipo_db = "aporte" if "Aporte" in tipo_movimento else "retirada"
                caixa_c = port.get("montante_disponivel", 0)
                if tipo_db == "retirada" and valor_movimento > caixa_c:
                    st.error("⚠️ Saldo insuficiente!")
                else:
                    registrar_transacao(portfolio_id=port["id"], tipo=tipo_db, valor=valor_movimento,
                                       descricao=f"{tipo_db.capitalize()} de caixa", data_transacao=data_movimento)
                    novo_caixa = caixa_c + (valor_movimento if tipo_db == "aporte" else -valor_movimento)
                    atualizar_portfolio(port["id"], montante_disponivel=novo_caixa)
                    st.session_state["show_aporte"] = False
                    st.toast(f"{tipo_db.capitalize()} registrado! ✅")
                    st.rerun()

# Painel: Comprar Ativo Direto
if st.session_state.get("show_compra_dir"):
    with st.container(border=True):
        c_na1, c_na2, c_na3, c_na4 = st.columns(4)
        with c_na1:
            novo_ticker = st.text_input("Ticker", placeholder="MGLU3", key="novo_ticker_compra")
        with c_na2:
            novo_qtd = st.number_input("Quantidade", min_value=1, value=100, step=10, key="novo_qtd_compra")
        with c_na3:
            novo_preco = st.number_input("Preço (R$)", min_value=0.01, value=10.0, step=0.1, key="novo_preco_compra")
        with c_na4:
            novo_data = st.date_input("Data", value=date.today(), key="novo_data_compra")
        if st.button("✅ Registrar Compra", key="btn_novo_ativo_compra", type="primary", use_container_width=True):
            if not novo_ticker:
                st.error("Informe o Ticker.")
            else:
                ticker_upper = novo_ticker.upper().strip()
                valor_total_nova_compra = novo_qtd * novo_preco
                caixa = port.get("montante_disponivel", 0)
                if valor_total_nova_compra > caixa:
                    st.error(f"⚠️ Caixa insuficiente!")
                else:
                    ativo_ext = next((x for x in ativos if x["ticker"] == ticker_upper), None)
                    if ativo_ext:
                        q_ant = ativo_ext["quantidade"]
                        p_ant = ativo_ext["preco_medio"]
                        q_nova = q_ant + novo_qtd
                        p_novo = ((q_ant * p_ant) + valor_total_nova_compra) / q_nova
                        atualizar_ativo(ativo_ext["id"], quantidade=q_nova, preco_medio=p_novo)
                    else:
                        adicionar_ativo(port["id"], ticker_upper, novo_preco, novo_qtd, novo_data)
                    registrar_transacao(port["id"], "compra", valor_total_nova_compra, ticker_upper, novo_qtd, novo_preco, "Compra Direta", novo_data)
                    atualizar_portfolio(port["id"], montante_disponivel=caixa - valor_total_nova_compra)
                    st.session_state["show_compra_dir"] = False
                    st.toast(f"Ativo {ticker_upper} comprado! 🎉")
                    st.rerun()

st.markdown("---")

# --- TABS: ATIVOS | MONITORANDO | SUGESTÕES ATIVOS | SUGESTÕES MOVIMENTAÇÕES ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 Meus Ativos", "👁️ Monitorando", "💡 Sugestões de Ativos", "🔄 Sugestões de Movimentações"])

with tab1:
    st.markdown("### Ativos Atuais")
    
    if ativos:
        for a in ativos:
            # Buscar preço atual para calcular posição e lucro
            preco_info = buscar_preco_atual(a['ticker'])
            preco_atual = preco_info.get("preco_atual", a['preco_medio']) if isinstance(preco_info, dict) else a['preco_medio']
            
            total_investido = a['quantidade'] * a['preco_medio']
            posicao_atual = a['quantidade'] * preco_atual
            lucro_valor = posicao_atual - total_investido
            lucro_pct = ((preco_atual - a['preco_medio']) / a['preco_medio'] * 100) if a['preco_medio'] > 0 else 0
            cor_lucro = "#00C851" if lucro_valor >= 0 else "#FF4444"
            sinal = "+" if lucro_valor >= 0 else ""
            
            with st.container(border=True):
                # Linha 1: Ticker + Botões
                c_nome, c_btns = st.columns([5, 2])
                with c_nome:
                    st.markdown(f"**{a['ticker']}** — {nome_ativo(a['ticker'])}  |  **{a['quantidade']}** cotas")
                    st.caption(f"Posição desde: {formatar_data_br(a['data_posicao'])}")
                with c_btns:
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
                
                # Linha 2: Métricas financeiras
                m1, m2, m3, m4, m5 = st.columns(5)
                with m1:
                    st.markdown(f"<small>Preço Médio</small><br><b>R\\$ {a['preco_medio']:,.2f}</b>".replace(",", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)
                with m2:
                    st.markdown(f"<small>Preço Atual</small><br><b>R\\$ {preco_atual:,.2f}</b>".replace(",", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)
                with m3:
                    st.markdown(f"<small>Total Investido</small><br><b>R\\$ {total_investido:,.2f}</b>".replace(",", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)
                with m4:
                    st.markdown(f"<small>Posição Atual</small><br><b>R\\$ {posicao_atual:,.2f}</b>".replace(",", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)
                with m5:
                    st.markdown(
                        f"<small>Lucro/Prejuízo</small><br>"
                        f"<b style='color:{cor_lucro}'>{sinal}R\\$ {abs(lucro_valor):,.2f}</b>"
                        f" <span style='color:{cor_lucro};font-size:0.78em'>({sinal}{lucro_pct:.2f}%)</span>".replace(",", "X").replace(".", ",").replace("X", "."),
                        unsafe_allow_html=True
                    )
                
                with st.expander("💸 Negociar (Comprar / Vender)"):
                    c_op1, c_op2, c_op3, c_op4, c_op5 = st.columns(5)
                    with c_op1:
                        op_tipo = st.selectbox("Operação", ["Compra", "Venda"], key=f"op_tipo_{a['id']}")
                    with c_op2:
                        op_qtd = st.number_input("Qtd", min_value=1, value=1, key=f"op_qtd_{a['id']}")
                    with c_op3:
                        op_preco = st.number_input("Preço (R$)", min_value=0.01, value=float(a['preco_medio']), key=f"op_prc_{a['id']}")
                    with c_op4:
                        op_data = st.date_input("Data", value=date.today(), key=f"op_dt_{a['id']}")
                    with c_op5:
                        valor_op_preview = op_qtd * op_preco
                        st.markdown(f"**Total:** {formatar_moeda(valor_op_preview).replace('$', chr(36))}")
                        if st.button("Executar", key=f"btn_exec_{a['id']}", type="primary", use_container_width=True):
                            valor_op = op_qtd * op_preco
                            caixa_atual = port.get("montante_disponivel", 0)
                            
                            if op_tipo == "Compra":
                                if valor_op > caixa_atual:
                                    st.error("⚠️ Saldo em caixa insuficiente para compra.")
                                else:
                                    q_ant = a["quantidade"]
                                    p_ant = a["preco_medio"]
                                    q_nova = q_ant + op_qtd
                                    p_novo = ((q_ant * p_ant) + valor_op) / q_nova
                                    atualizar_ativo(a["id"], quantidade=q_nova, preco_medio=p_novo)
                                    registrar_transacao(port["id"], "compra", valor_op, a["ticker"], op_qtd, op_preco, f"Compra {a['ticker']}", op_data)
                                    atualizar_portfolio(port["id"], montante_disponivel=caixa_atual - valor_op)
                                    st.toast(f"Compra de {a['ticker']} registrada! 💸")
                                    st.rerun()
                            else: # Venda
                                if op_qtd > a["quantidade"]:
                                    st.error("⚠️ Você não possui essa quantidade toda para vender.")
                                else:
                                    nova_qtd = a["quantidade"] - op_qtd
                                    if nova_qtd <= 0:
                                        deletar_ativo(a["id"])
                                    else:
                                        atualizar_ativo(a["id"], quantidade=nova_qtd, preco_medio=a["preco_medio"])
                                    registrar_transacao(port["id"], "venda", valor_op, a["ticker"], op_qtd, op_preco, f"Venda {a['ticker']}", op_data)
                                    atualizar_portfolio(port["id"], montante_disponivel=caixa_atual + valor_op)
                                    st.toast(f"Venda de {a['ticker']} registrada! 💰")
                                    st.rerun()
                            
        st.info("Sua carteira ainda não possui ativos.")

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
            ticker_w = w['ticker']
            with st.container(border=True):
                # Buscar dados de mercado
                preco_w = buscar_preco_atual(ticker_w)
                fund_w = buscar_dados_fundamentalistas(ticker_w)
                
                preco_val = preco_w.get("preco_atual", 0) if isinstance(preco_w, dict) else 0
                var_dia = preco_w.get("variacao_dia", 0) if isinstance(preco_w, dict) else 0
                nome_w = nome_ativo(ticker_w)
                
                # Indicadores técnicos (RSI, MACD)
                hist_w = buscar_historico(ticker_w, "6mo")
                ind_w = calcular_indicadores_tecnicos(hist_w) if hist_w is not None else {}
                rsi_val = ind_w.get("rsi", None)
                macd_val = ind_w.get("macd", None)
                macd_sig = ind_w.get("macd_signal", None)
                tendencia = ind_w.get("tendencia", "neutra")
                
                # Tipo e setor
                is_fii = ticker_w.endswith("11") and len(ticker_w) >= 5
                tipo_ativo_w = "FII" if is_fii else "Ação"
                setor_w = fund_w.get("setor", "—") if fund_w else "—"
                
                # Cor da variação
                cor_var = "#00C851" if var_dia >= 0 else "#FF4444"
                sinal_var = "+" if var_dia >= 0 else ""
                
                # Linha 1: Nome + tipo + setor
                c_nome_w, c_acoes_w = st.columns([5, 3])
                with c_nome_w:
                    st.markdown(
                        f"**{ticker_w}** — {nome_w} "
                        f"<span style='background:#667eea;color:#fff;padding:1px 8px;border-radius:10px;font-size:0.7em'>{tipo_ativo_w}</span> "
                        f"<span style='color:#888;font-size:0.8em'>| {setor_w or '—'}</span>",
                        unsafe_allow_html=True
                    )
                    if w["adicionado_manualmente"]: st.caption("Adicionado manualmente")
                    else: st.caption("Sugerido pela IA")
                with c_acoes_w:
                    bc1, bc2, bc3, bc4 = st.columns(4)
                    with bc1:
                        if st.button("🛒", key=f"w_buy_{w['id']}", help="Comprar este ativo", use_container_width=True):
                            st.session_state.view_asset_ticker = ticker_w
                            st.session_state.voltar_para_pagina = "pages/_7_📂_Carteira_Detalhe.py"
                            st.switch_page("pages/_8_📄_Ativo.py")
                    with bc2:
                        if st.button("ℹ️", key=f"w_info_{w['id']}", help="Ver detalhes", use_container_width=True):
                            st.session_state.view_asset_ticker = ticker_w
                            st.session_state.voltar_para_pagina = "pages/_7_📂_Carteira_Detalhe.py"
                            st.switch_page("pages/_8_📄_Ativo.py")
                    with bc3:
                        if st.button("📂", key=f"w_cart_{w['id']}", help="Ir para Carteira", use_container_width=True):
                            pass  # Already on this page
                    with bc4:
                        if st.button("🗑️", key=f"w_del_{w['id']}", help="Remover", use_container_width=True):
                            remover_watchlist(w["id"])
                            st.rerun()
                
                # Linha 2: Indicadores financeiros
                i1, i2, i3, i4, i5, i6, i7 = st.columns(7)
                with i1:
                    st.markdown(f"<small>Preço</small><br><b>R\\$ {preco_val:,.2f}</b>".replace(",", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)
                with i2:
                    st.markdown(f"<small>Variação</small><br><b style='color:{cor_var}'>{sinal_var}{var_dia:.2f}%</b>", unsafe_allow_html=True)
                with i3:
                    pvp_txt = f"{fund_w.get('pvp', 0):.2f}" if fund_w and fund_w.get("pvp") else "—"
                    st.markdown(f"<small>P/VP</small><br><b>{pvp_txt}</b>", unsafe_allow_html=True)
                with i4:
                    pl_txt = f"{fund_w.get('pl', 0):.1f}" if fund_w and fund_w.get("pl") else "—"
                    st.markdown(f"<small>P/L</small><br><b>{pl_txt}</b>", unsafe_allow_html=True)
                with i5:
                    dy_txt = f"{fund_w.get('dy', 0):.1f}%" if fund_w and fund_w.get("dy") else "—"
                    st.markdown(f"<small>DY</small><br><b>{dy_txt}</b>", unsafe_allow_html=True)
                with i6:
                    rsi_txt = f"{rsi_val:.0f}" if rsi_val is not None else "—"
                    cor_rsi = "#FF4444" if rsi_val and rsi_val > 70 else ("#00C851" if rsi_val and rsi_val < 30 else "#333")
                    st.markdown(f"<small>RSI</small><br><b style='color:{cor_rsi}'>{rsi_txt}</b>", unsafe_allow_html=True)
                with i7:
                    if macd_val is not None and macd_sig is not None:
                        macd_status = "Compra" if macd_val > macd_sig else "Venda"
                        cor_macd = "#00C851" if macd_val > macd_sig else "#FF4444"
                    else:
                        macd_status = "—"
                        cor_macd = "#333"
                    st.markdown(f"<small>MACD</small><br><b style='color:{cor_macd}'>{macd_status}</b>", unsafe_allow_html=True)

with tab3:
    st.subheader("Sugestões de Ativos")
    st.markdown("Ativos sugeridos para **compra ou observação**. Use para montar sua carteira ou alocar saldo disponível.")
    
    # 1. Botão Geral de IA — Sugestões de Compra
    if st.button("💡 Gerar Sugestões de Compra com IA", type="primary", use_container_width=True):
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
        
        total_todas_sugestoes = sum(s.get("valor_total", 0) for s in sugestoes_ia if s.get("quantidade", 0) > 0)
        caixa_disponivel = port.get("montante_disponivel", 0)
        
        st.markdown(f"**💰 Caixa disponível:** R\\$ {caixa_disponivel:,.2f} | **🛒 Total das sugestões:** R\\$ {total_todas_sugestoes:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        # Filtrar sugestões com quantidade 0
        sugestoes_mostrar = [s for s in sugestoes_ia if s.get("quantidade", 0) > 0]
        
        if not sugestoes_mostrar:
            st.warning("Nenhuma sugestão viável — preços indisponíveis ou alocação insuficiente.")
        else:
            for i, sug in enumerate(sugestoes_mostrar):
                with st.container(border=True):
                    ticker_sug = sug.get("ticker", "")
                    qtd_sug_ia = sug.get("quantidade", 0)
                    preco_sug = sug.get("preco_estimado", 0.0)
                    alocacao_pct = sug.get("alocacao_pct", 0)
                    
                    col_ticker, col_aloc, col_preco, col_qtd, col_total, col_acoes = st.columns([2, 1, 1.5, 1.2, 1.5, 1.8])
                    
                    with col_ticker:
                        st.markdown(f"**{ticker_sug}**")
                        st.caption(sug.get("tipo", "Ação/FII"))
                    with col_aloc:
                        st.markdown(f"**Alocação**")
                        st.markdown(f"{alocacao_pct:.0f}%")
                    with col_preco:
                        st.markdown(f"**Preço Unit.**")
                        st.markdown(f"R\\$ {preco_sug:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    with col_qtd:
                        qtd_editada = st.number_input("Qtd", min_value=0, value=qtd_sug_ia, key=f"qtd_sug_{i}_{ticker_sug}", step=1)
                    with col_total:
                        valor_total_display = qtd_editada * preco_sug
                        st.markdown(f"**Total**")
                        st.markdown(f"R\\$ {valor_total_display:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    with col_acoes:
                        st.markdown("<br>", unsafe_allow_html=True)
                        ca1, ca2 = st.columns(2)
                        with ca1:
                            if st.button("🛒", key=f"buy_sug_{i}_{ticker_sug}", use_container_width=True, help="Comprar este ativo"):
                                if qtd_editada <= 0:
                                    st.toast("⚠️ Quantidade deve ser maior que 0!", icon="⚠️")
                                else:
                                    v_compra = qtd_editada * preco_sug
                                    caixa_at = port.get("montante_disponivel", 0)
                                    if v_compra > caixa_at:
                                        st.toast("⚠️ Caixa insuficiente!", icon="⚠️")
                                    else:
                                        ativo_ext = next((x for x in ativos if x["ticker"] == ticker_sug), None)
                                        if ativo_ext:
                                            q_ant = ativo_ext["quantidade"]
                                            p_ant = ativo_ext["preco_medio"]
                                            q_nova = q_ant + qtd_editada
                                            p_novo = ((q_ant * p_ant) + v_compra) / q_nova
                                            atualizar_ativo(ativo_ext["id"], quantidade=q_nova, preco_medio=p_novo)
                                        else:
                                            adicionar_ativo(port["id"], ticker_sug, preco_sug, qtd_editada, date.today())
                                        registrar_transacao(port["id"], "compra", v_compra, ticker_sug, qtd_editada, preco_sug, "Compra IA", date.today())
                                        atualizar_portfolio(port["id"], montante_disponivel=caixa_at - v_compra)
                                        st.toast(f"{ticker_sug} comprado! 🎉", icon="✅")
                                        st.rerun()
                        with ca2:
                            if st.button("ℹ️", key=f"info_sug_{i}_{ticker_sug}", use_container_width=True, help="Ver detalhes"):
                                st.session_state.view_asset_ticker = ticker_sug
                                st.session_state.voltar_para_pagina = "pages/_7_📂_Carteira_Detalhe.py"
                                st.switch_page("pages/_8_📄_Ativo.py")
                    
                    st.caption(f"📝 {sug.get('motivo', '')}")
            
            # Botão "Comprar Tudo"
            st.markdown("---")
            
            # Calcula total baseado nas quantidades editadas
            total_compra_tudo = 0
            sugestoes_para_compra = []
            for i, sug in enumerate(sugestoes_mostrar):
                ticker_sug = sug.get("ticker", "")
                preco_sug = sug.get("preco_estimado", 0.0)
                qtd_atual = st.session_state.get(f"qtd_sug_{i}_{ticker_sug}", sug.get("quantidade", 0))
                if qtd_atual > 0:
                    valor = qtd_atual * preco_sug
                    total_compra_tudo += valor
                    sugestoes_para_compra.append({"ticker": ticker_sug, "quantidade": qtd_atual, "preco_estimado": preco_sug, "valor_total": valor})
            
            if sugestoes_para_compra:
                if total_compra_tudo > caixa_disponivel:
                    st.error(f"⚠️ O total (R\\$ {total_compra_tudo:,.2f}) excede o caixa disponível (R\\$ {caixa_disponivel:,.2f}).".replace(",", "X").replace(".", ",").replace("X", "."))
                else:
                    col_btn1, col_btn2 = st.columns([3, 1])
                    with col_btn1:
                        st.markdown(
                            f"**🛒 Comprar todos os {len(sugestoes_para_compra)} ativos** — "
                            f"Total: R\\$ {total_compra_tudo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        )
                    with col_btn2:
                        if st.button("🛒 Comprar Tudo", key="btn_comprar_tudo_ia", type="primary", use_container_width=True):
                            caixa_restante = caixa_disponivel
                            compras_ok = 0
                            
                            for sug_exec in sugestoes_para_compra:
                                t_sug = sug_exec["ticker"]
                                q_sug = sug_exec["quantidade"]
                                p_sug = sug_exec["preco_estimado"]
                                v_total = q_sug * p_sug
                                
                                if v_total > caixa_restante:
                                    continue
                                
                                ativo_existente = next((x for x in ativos if x["ticker"] == t_sug), None)
                                if ativo_existente:
                                    q_ant = ativo_existente["quantidade"]
                                    p_ant = ativo_existente["preco_medio"]
                                    q_nova = q_ant + q_sug
                                    p_novo = ((q_ant * p_ant) + v_total) / q_nova
                                    atualizar_ativo(ativo_existente["id"], quantidade=q_nova, preco_medio=p_novo)
                                else:
                                    adicionar_ativo(port["id"], t_sug, p_sug, q_sug, date.today())
                                
                                registrar_transacao(port["id"], "compra", v_total, t_sug, q_sug, p_sug, "Compra IA (Lote)", date.today())
                                caixa_restante -= v_total
                                compras_ok += 1
                            
                            atualizar_portfolio(port["id"], montante_disponivel=caixa_restante)
                            st.toast(f"{compras_ok} ativo(s) comprado(s) com sucesso! 🎉", icon="✅")
                            st.session_state["ia_resumo_geral"] = None
                            st.session_state["ia_sugestoes_raw"] = []
                            st.rerun()
            else:
                st.warning("Nenhuma sugestão com quantidade > 0.")
        
        st.markdown("---")
        
    # 2. Sugestões técnicas — pré-carregadas
    st.markdown("#### Sugestões do Algoritmo Técnico")
    
    sugestoes = gerar_sugestoes_carteira(portfolio_id)
    
    if sugestoes:
        sugestoes_compra_obs = [s for s in sugestoes if s.get("acao") in ("compra", "observar")]
        if sugestoes_compra_obs:
            for idx_s, s in enumerate(sugestoes_compra_obs):
                with st.container(border=True):
                    novo_label = " 🆕 **NOVO**" if s.get("novo") else ""
                    st.markdown(f"### {s['ticker']}{novo_label}")
                    st.caption(nome_ativo(s['ticker']))
                    cor_acao = "#00C851" if s['acao'] == "compra" else "#FFBB33"
                    preco_sug_inline = 0.0
                    cot = buscar_preco_atual(s["ticker"])
                    if isinstance(cot, dict) and cot.get("preco_atual", 0) > 0:
                        preco_sug_inline = float(cot["preco_atual"])
                        
                    st.markdown(f"**Ação sugerida:** <span style='color:{cor_acao}'>{s['acao'].upper()}</span> (Score: {s['score']}/100) | **Preço Unit:** {formatar_moeda_md(preco_sug_inline)}", unsafe_allow_html=True)
                    st.info(s['texto'])
                    
                    # Botões abaixo do texto
                    if preco_sug_inline > 0:
                        caixa_alg = port.get("montante_disponivel", 0)
                        ca_qty, ca_total, ca1, ca2, ca3, ca4 = st.columns([1, 1.5, 0.8, 0.8, 0.8, 0.8])
                        with ca_qty:
                            qtd_alg = st.number_input("Qtd", min_value=1, value=1, key=f"alg_qtd_{idx_s}_{s['ticker']}", step=1)
                        with ca_total:
                            valor_total_alg = qtd_alg * preco_sug_inline
                            st.markdown(f"**Total**")
                            st.markdown(f"R\\$ {valor_total_alg:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                        with ca1:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("🛒", key=f"alc_buy_{idx_s}_{s['ticker']}", use_container_width=True, help="Comprar"):
                                if valor_total_alg > caixa_alg:
                                    st.toast("⚠️ Caixa insuficiente!", icon="⚠️")
                                else:
                                    ativo_ext = next((x for x in ativos if x["ticker"] == s['ticker']), None)
                                    if ativo_ext:
                                        q_ant = ativo_ext["quantidade"]
                                        p_ant = ativo_ext["preco_medio"]
                                        q_nova = q_ant + qtd_alg
                                        p_novo = ((q_ant * p_ant) + valor_total_alg) / q_nova
                                        atualizar_ativo(ativo_ext["id"], quantidade=q_nova, preco_medio=p_novo)
                                    else:
                                        adicionar_ativo(port["id"], s['ticker'], preco_sug_inline, qtd_alg, date.today())
                                    registrar_transacao(port["id"], "compra", valor_total_alg, s['ticker'], qtd_alg, preco_sug_inline, "Compra Algoritmo", date.today())
                                    atualizar_portfolio(port["id"], montante_disponivel=caixa_alg - valor_total_alg)
                                    st.toast(f"{s['ticker']} comprado! 🎉", icon="✅")
                                    st.rerun()
                        with ca2:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("👁️", key=f"alc_watch_{idx_s}_{s['ticker']}", use_container_width=True, help="Watchlist"):
                                adicionar_watchlist(portfolio_id, s['ticker'])
                                st.toast(f"{s['ticker']} adicionado à watchlist! 👁️", icon="✅")
                                st.rerun()
                        with ca3:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("ℹ️", key=f"alc_i_{idx_s}_{s['ticker']}", use_container_width=True, help="Info"):
                                st.session_state.view_asset_ticker = s['ticker']
                                st.session_state.voltar_para_pagina = "pages/_7_📂_Carteira_Detalhe.py"
                                st.switch_page("pages/_8_📄_Ativo.py")
                        with ca4:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("💡", key=f"btn_ia_{idx_s}_{s['ticker']}", use_container_width=True, help="Análise IA"):
                                st.session_state[f"run_ia_{s['ticker']}"] = True
                    else:
                        if st.button("👁️ Watchlist", key=f"alc_watch_np_{idx_s}_{s['ticker']}", use_container_width=True):
                            adicionar_watchlist(portfolio_id, s['ticker'])
                            st.toast(f"{s['ticker']} adicionado à watchlist!", icon="✅")
                            st.rerun()
                            
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
            st.info("Nenhuma sugestão de compra/observação encontrada pelo algoritmo técnico.")
    else:
        st.info("Nenhuma sugestão encontrada. Adicione ativos ou configure os setores preferidos da carteira para receber sugestões.")

with tab4:
    st.subheader("Sugestões de Movimentações")
    st.markdown("Avalie se é necessário **rebalancear ou vender** algum ativo da sua carteira atual.")
    
    # Tickers que já estão na carteira
    tickers_na_carteira = {a["ticker"] for a in ativos}
    
    # 1. Sugestões técnicas — APENAS venda, e somente se ativo já está na carteira
    st.markdown("#### Algoritmo Técnico — Movimentações Sugeridas")
    sugestoes_mov = gerar_sugestoes_carteira(portfolio_id)
    
    if sugestoes_mov:
        sugestoes_venda = [s for s in sugestoes_mov if s.get("acao") == "venda" and s.get("ticker") in tickers_na_carteira]
        if sugestoes_venda:
            for idx_m, s in enumerate(sugestoes_venda):
                with st.container(border=True):
                    novo_label = " 🆕 **NOVO**" if s.get("novo") else ""
                    st.markdown(f"### {s['ticker']}{novo_label}")
                    st.caption(nome_ativo(s['ticker']))
                    
                    # Info do ativo na carteira
                    ativo_cart = next((a for a in ativos if a["ticker"] == s["ticker"]), None)
                    qtd_cart = ativo_cart["quantidade"] if ativo_cart else 0
                    pm_cart = ativo_cart["preco_medio"] if ativo_cart else 0
                    
                    cot = buscar_preco_atual(s["ticker"])
                    preco_atual_mov = float(cot["preco_atual"]) if isinstance(cot, dict) and cot.get("preco_atual", 0) > 0 else pm_cart
                    
                    lucro_un = preco_atual_mov - pm_cart
                    lucro_total = lucro_un * qtd_cart
                    cor_lucro = "#00C851" if lucro_total >= 0 else "#FF4444"
                    
                    st.markdown(
                        f"**Ação sugerida:** <span style='color:#FF4444'>VENDA</span> (Score: {s['score']}/100) | "
                        f"Em carteira: {qtd_cart} papéis | PM: {formatar_moeda_md(pm_cart)} | "
                        f"Atual: {formatar_moeda_md(preco_atual_mov)} | "
                        f"L/P: <span style='color:{cor_lucro}'>{formatar_moeda_md(lucro_total)}</span>",
                        unsafe_allow_html=True
                    )
                    st.info(s['texto'])
                    
                    # Botões abaixo do texto
                    if preco_atual_mov > 0:
                        caixa_mov = port.get("montante_disponivel", 0)
                        ca_qty, ca_total, ca1, ca1b, ca2, ca3, ca4 = st.columns([1, 1.5, 0.7, 0.7, 0.7, 0.7, 0.7])
                        with ca_qty:
                            qtd_mov = st.number_input("Qtd", min_value=1, value=1, key=f"mov_qtd_{idx_m}_{s['ticker']}", step=1)
                        with ca_total:
                            valor_total_mov = qtd_mov * preco_atual_mov
                            st.markdown(f"**Total**")
                            st.markdown(f"R\\$ {valor_total_mov:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                        with ca1:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("🛒", key=f"mov_buy_{idx_m}_{s['ticker']}", use_container_width=True, help="Comprar"):
                                if valor_total_mov > caixa_mov:
                                    st.toast("⚠️ Caixa insuficiente!", icon="⚠️")
                                else:
                                    if ativo_cart:
                                        q_ant = ativo_cart["quantidade"]
                                        p_ant = ativo_cart["preco_medio"]
                                        q_nova = q_ant + qtd_mov
                                        p_novo = ((q_ant * p_ant) + valor_total_mov) / q_nova
                                        atualizar_ativo(ativo_cart["id"], quantidade=q_nova, preco_medio=p_novo)
                                    else:
                                        adicionar_ativo(port["id"], s['ticker'], preco_atual_mov, qtd_mov, date.today())
                                    registrar_transacao(port["id"], "compra", valor_total_mov, s['ticker'], qtd_mov, preco_atual_mov, "Compra (Mov)", date.today())
                                    atualizar_portfolio(port["id"], montante_disponivel=caixa_mov - valor_total_mov)
                                    st.toast(f"{s['ticker']} comprado! 🎉", icon="✅")
                                    st.rerun()
                        with ca1b:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("💰", key=f"mov_sell_{idx_m}_{s['ticker']}", use_container_width=True, help="Vender"):
                                if ativo_cart and qtd_mov <= ativo_cart["quantidade"]:
                                    nova_qtd = ativo_cart["quantidade"] - qtd_mov
                                    if nova_qtd == 0:
                                        from database.crud import deletar_ativo
                                        deletar_ativo(ativo_cart["id"])
                                    else:
                                        atualizar_ativo(ativo_cart["id"], quantidade=nova_qtd, preco_medio=ativo_cart["preco_medio"])
                                    registrar_transacao(port["id"], "venda", valor_total_mov, s['ticker'], qtd_mov, preco_atual_mov, "Venda (Mov)", date.today())
                                    atualizar_portfolio(port["id"], montante_disponivel=caixa_mov + valor_total_mov)
                                    st.toast(f"{s['ticker']} vendido! 💰", icon="✅")
                                    st.rerun()
                                else:
                                    st.toast(f"⚠️ Você só tem {qtd_cart} papéis!", icon="⚠️")
                        with ca2:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("👁️", key=f"mov_watch_{idx_m}_{s['ticker']}", use_container_width=True, help="Watchlist"):
                                adicionar_watchlist(portfolio_id, s['ticker'])
                                st.toast(f"{s['ticker']} adicionado à watchlist! 👁️", icon="✅")
                                st.rerun()
                        with ca3:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("ℹ️", key=f"mov_i_{idx_m}_{s['ticker']}", use_container_width=True, help="Info"):
                                st.session_state.view_asset_ticker = s['ticker']
                                st.session_state.voltar_para_pagina = "pages/_7_📂_Carteira_Detalhe.py"
                                st.switch_page("pages/_8_📄_Ativo.py")
                        with ca4:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("💡", key=f"btn_ia_mov_{idx_m}_{s['ticker']}", use_container_width=True, help="Análise IA"):
                                st.session_state[f"run_ia_mov_{s['ticker']}"] = True
                    
                    if st.session_state.get(f"run_ia_mov_{s['ticker']}"):
                        with st.spinner(f"Consultando IA para {s['ticker']}..."):
                            rec_ia = gerar_recomendacao_completa(s['ticker'], persona["id"], portfolio_id)
                            st.session_state[f"res_ia_mov_{s['ticker']}"] = rec_ia
                            st.session_state[f"run_ia_mov_{s['ticker']}"] = False
                            
                    if st.session_state.get(f"res_ia_mov_{s['ticker']}"):
                        rec = st.session_state[f"res_ia_mov_{s['ticker']}"]
                        st.markdown("---")
                        if rec["sucesso"]:
                            st.success(f"**Visão da IA ({rec['recomendacao']['confianca']}% confiança):** {rec['recomendacao']['explicacao']}")
                        else:
                            st.error(rec.get("erro", "Erro ao consultar IA."))
        else:
            st.info("✅ Nenhuma sugestão de venda para os ativos da sua carteira no momento.")
    else:
        st.info("Nenhuma sugestão encontrada. Adicione ativos à carteira para receber análises de movimentação.")
    
    # 2. IA Geral — Análise de Rebalanceamento
    st.markdown("---")
    st.markdown("#### 🧠 Análise de Rebalanceamento com IA")
    st.markdown("A IA analisa sua carteira atual e sugere movimentações (compra, venda, rebalanceamento) e próximos passos.")
    
    if st.button("🔄 Analisar Movimentações com IA", type="primary", use_container_width=True):
        st.session_state["ia_loading_mov"] = True
    
    if st.session_state.get("ia_loading_mov"):
        with st.spinner("🧠 Analisando movimentações com IA..."):
            from services.ai_brain import gerar_sugestoes_compra
            portfolios_analise = buscar_portfolio_por_id(portfolio_id)
            rec_mov = gerar_sugestoes_compra(ativos, persona, portfolios_analise)
            
            if rec_mov and rec_mov.get("sucesso"):
                st.session_state["ia_resumo_mov"] = rec_mov.get("resumo", "")
                st.session_state["ia_loading_mov"] = False
            else:
                st.error(rec_mov.get("resumo", "Falha ao consultar IA."))
                st.session_state["ia_loading_mov"] = False
    
    if st.session_state.get("ia_resumo_mov"):
        st.success(f"🔄 **Análise da IA:** {st.session_state['ia_resumo_mov']}")
        st.caption("💡 Use esta análise junto com as sugestões técnicas acima para tomar decisões informadas.")

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
