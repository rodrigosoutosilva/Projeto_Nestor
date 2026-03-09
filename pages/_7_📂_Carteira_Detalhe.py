import streamlit as st
import pandas as pd
from datetime import date, datetime
from database.crud import (
    buscar_portfolio_por_id, atualizar_portfolio, deletar_portfolio,
    listar_ativos_portfolio, adicionar_ativo, atualizar_ativo, deletar_ativo,
    registrar_transacao, listar_acoes_portfolio, atualizar_status_acao, deletar_acao_planejada,
    adicionar_watchlist, listar_watchlist_portfolio, remover_watchlist,
    buscar_persona_por_id, resumo_transacoes_portfolio,
    adicionar_observacao, listar_observacoes, deletar_observacao,
    criar_ordem_pendente, listar_ordens_pendentes, cancelar_ordem,
    listar_transacoes_portfolio, executar_ordem_pendente
)
from services.order_checker import deve_executar_ordem
from services.scoring import gerar_sugestoes_carteira
from services.recommendation import gerar_recomendacao_completa
from services.market_data import buscar_preco_atual, buscar_dados_fundamentalistas, buscar_historico, calcular_indicadores_tecnicos
from utils.helpers import formatar_moeda, formatar_moeda_md, formatar_data_br, nome_ativo, injetar_css_global

# Verificar ordens pendentes ao carregar a página
try:
    from services.order_checker import verificar_e_executar_ordens
    ordens_exec = verificar_e_executar_ordens()
    if ordens_exec:
        for oe in ordens_exec:
            st.toast(f"✅ Ordem de {oe['tipo']} de {oe['ticker']} executada a R$ {oe['preco_alvo']:.2f}!", icon="🔔")
except Exception:
    pass

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
# Rendimento anual projetado
rend_anual = 0.0
if port.get("created_at") and total_aportado > 0:
    try:
        from dateutil import parser
        dt_port = parser.parse(str(port["created_at"])).replace(tzinfo=None)
    except Exception:
        dt_port = None
    if dt_port:
        dias = (datetime.utcnow() - dt_port).days
        if dias <= 0:
            dias = 1
        rend_anual = (lucro_pct / dias) * 365

mh1, mh2, mh3, mh4, mh5, mh6 = st.columns(6)
mh1.metric("💎 Patrimônio", formatar_moeda(valor_total), help="Caixa + valor atual dos ativos")
mh2.metric("💵 Investido", formatar_moeda(total_aportado), help="Total aportado líquido")
cor_lucro_h = "#00C851" if lucro_acum >= 0 else "#FF4444"
mh3.markdown(
    f"<small>📈 Lucro</small><br>"
    f"<b>{formatar_moeda_md(lucro_acum)}</b> "
    f"<span style='color:{cor_lucro_h};font-size:0.8em'>({lucro_pct:+.1f}%)</span>",
    unsafe_allow_html=True
)
cor_rend = "#00C851" if rend_anual >= 0 else "#FF4444"
mh4.markdown(
    f"<small>📅 Rend. Anual</small><br>"
    f"<b style='color:{cor_rend}'>{rend_anual:+.1f}% a.a.</b>",
    unsafe_allow_html=True
)
# Calcular valor comprometido (ordens pendentes de COMPRA apenas)
ordens_pendentes_all = listar_ordens_pendentes(portfolio_id)
valor_comprometido = sum(o["quantidade"] * o["preco_alvo"] for o in ordens_pendentes_all if o.get("tipo") == "compra")
mh5.markdown(
    f"<small>🏦 Caixa</small><br>"
    f"<b>{formatar_moeda_md(caixa)}</b>"
    + (f"<br><span style='color:#8B0000;font-size:0.75em'>{formatar_moeda_md(valor_comprometido)} comprometido</span>" if valor_comprometido > 0 else ""),
    unsafe_allow_html=True
)
mh6.metric("📊 Ativos", len(ativos))

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
                    st.warning("⚠️ Saldo insuficiente! Esta retirada causará saldo negativo, sujeito a cobrança diária de juros. Clique em Confirmar novamente para prosseguir.")
                    if not st.session_state.get(f"conf_retirada_port", False):
                        st.session_state[f"conf_retirada_port"] = True
                        st.stop()
                    st.session_state[f"conf_retirada_port"] = False
                    
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
        c_na1, c_na2, c_na3 = st.columns(3)
        with c_na1:
            novo_ticker = st.text_input("Ticker", placeholder="MGLU3", key="novo_ticker_compra")
        # Carregar preço atual do ticker digitado
        _preco_default_compra = 10.0
        if novo_ticker:
            _p_info = buscar_preco_atual(novo_ticker.upper().strip())
            if isinstance(_p_info, dict) and _p_info.get("preco_atual", 0) > 0:
                _preco_default_compra = float(_p_info["preco_atual"])
        with c_na2:
            novo_qtd = st.number_input("Quantidade", min_value=1, value=100, step=10, key="novo_qtd_compra")
        with c_na3:
            novo_preco = st.number_input("Preço (R$)", min_value=0.01, value=_preco_default_compra, step=0.1, key="novo_preco_compra", help="Se alterar o preço, a ordem só será executada quando o ativo atingir este valor.")
            if abs(novo_preco - _preco_default_compra) >= 0.01:
                st.caption(f"Preço atual: R$ {_preco_default_compra:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        if st.button("✅ Registrar Compra", key="btn_novo_ativo_compra", type="primary", use_container_width=True):
            if not novo_ticker:
                st.error("Informe o Ticker.")
            else:
                ticker_upper = novo_ticker.upper().strip()
                valor_total_nova_compra = novo_qtd * novo_preco
                caixa = port.get("montante_disponivel", 0)
                
                # Verificar se deve executar imediatamente ou criar ordem pendente
                _preco_mercado = _preco_default_compra if _preco_default_compra > 0 else 0
                executa_agora = deve_executar_ordem("compra", novo_preco, _preco_mercado) if _preco_mercado > 0 else False
                
                if executa_agora:
                    # Execução imediata
                    if valor_total_nova_compra > caixa and not st.session_state.get(f"confirm_negative_{ticker_upper}_{port['id']}", False):
                        st.session_state[f"confirm_negative_{ticker_upper}_{port['id']}"] = True
                        st.warning(f"⚠️ Caixa insuficiente! Esta compra causará saldo negativo, sujeito a cobrança diária de juros. Clique em Registrar Compra novamente para confirmar.")
                    else:
                        st.session_state[f"confirm_negative_{ticker_upper}_{port['id']}"] = False
                        ativo_ext = next((x for x in ativos if x["ticker"] == ticker_upper), None)
                        if ativo_ext:
                            q_ant = ativo_ext["quantidade"]
                            p_ant = ativo_ext["preco_medio"]
                            q_nova = q_ant + novo_qtd
                            p_novo = ((q_ant * p_ant) + valor_total_nova_compra) / q_nova
                            atualizar_ativo(ativo_ext["id"], quantidade=q_nova, preco_medio=p_novo)
                        else:
                            adicionar_ativo(port["id"], ticker_upper, novo_preco, novo_qtd, date.today())
                        registrar_transacao(port["id"], "compra", valor_total_nova_compra, ticker_upper, novo_qtd, novo_preco, "Compra Direta", date.today())
                        atualizar_portfolio(port["id"], montante_disponivel=caixa - valor_total_nova_compra)
                        st.session_state["show_compra_dir"] = False
                        st.toast(f"Ativo {ticker_upper} comprado! 🎉")
                        st.rerun()
                else:
                    # Ordem condicional (preço abaixo do mercado)
                    criar_ordem_pendente(port["id"], ticker_upper, "compra", novo_qtd, novo_preco)
                    st.session_state["show_compra_dir"] = False
                    st.warning(f"⏳ Ordem de compra de {ticker_upper} a R$ {novo_preco:.2f} **ainda não foi executada**. Será executada quando o preço for atingido.")
                    st.toast(f"📋 Ordem condicional criada!", icon="📋")
                    st.rerun()

# --- OBSERVAÇÕES ---
with st.expander("📝 Observações", expanded=False):
    observacoes = listar_observacoes("portfolio", portfolio_id)
    
    if observacoes:
        for obs in observacoes:
            c_obs_txt, c_obs_del = st.columns([6, 1])
            with c_obs_txt:
                data_obs = formatar_data_br(obs["created_at"].split(" ")[0]) if obs.get("created_at") else ""
                st.markdown(f"• {obs['texto']}  \n<small style='color:#888'>{data_obs}</small>", unsafe_allow_html=True)
            with c_obs_del:
                if st.button("🗑️", key=f"del_obs_port_{obs['id']}", help="Remover"):
                    deletar_observacao(obs["id"])
                    st.rerun()
    else:
        st.caption("Nenhuma observação registrada.")
    
    st.markdown("---")
    c_nova_obs, c_btn_obs = st.columns([5, 1])
    with c_nova_obs:
        nova_obs = st.text_input("Nova observação", placeholder="Escreva uma nota...", key="nova_obs_portfolio", label_visibility="collapsed")
    with c_btn_obs:
        if st.button("➕", key="btn_add_obs_portfolio", use_container_width=True, help="Adicionar observação"):
            if nova_obs and nova_obs.strip():
                adicionar_observacao("portfolio", portfolio_id, nova_obs.strip())
                st.rerun()

st.markdown("---")

# --- TABS: ATIVOS | MONITORANDO | ORDENS PENDENTES | SUGESTÕES ATIVOS | SUGESTÕES MOVIMENTAÇÕES ---
qtd_ordens = len(ordens_pendentes_all) if 'ordens_pendentes_all' in locals() else 0
tab_ordens_title = f"📋 Ordens Pendentes ({qtd_ordens})" if qtd_ordens > 0 else "📋 Ordens Pendentes"
tab1, tab2, tab_ordens, tab3, tab4 = st.tabs(["📊 Meus Ativos", "👁️ Monitorando", tab_ordens_title, "💡 Sugestões de Ativos", "🔄 Sugestões de Movimentações"])

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
            lucro_pct_at = ((preco_atual - a['preco_medio']) / a['preco_medio'] * 100) if a['preco_medio'] > 0 else 0
            cor_lucro = "#00C851" if lucro_valor >= 0 else "#FF4444"
            sinal = "+" if lucro_valor >= 0 else ""
            
            with st.container(border=True):
                # Linha 1: Ticker + Botões (Info + Watchlist)
                c_nome, c_btns = st.columns([5, 2])
                with c_nome:
                    st.markdown(f"**{a['ticker']}** — {nome_ativo(a['ticker'])}  |  **{a['quantidade']}** cotas")
                with c_btns:
                    col_bi, col_bw = st.columns(2)
                    with col_bi:
                        if st.button("ℹ️ Info", key=f"info_{a['id']}", use_container_width=True):
                            st.session_state.view_asset_ticker = a["ticker"]
                            st.session_state.voltar_para_pagina = "pages/_7_📂_Carteira_Detalhe.py"
                            st.switch_page("pages/_8_📄_Ativo.py")
                    with col_bw:
                        if st.button("👁️ Watch", key=f"watch_{a['id']}", use_container_width=True, help="Adicionar à Watchlist"):
                            adicionar_watchlist(portfolio_id, a["ticker"])
                            st.toast(f"{a['ticker']} adicionado à watchlist! 👁️", icon="✅")
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
                        f" <span style='color:{cor_lucro};font-size:0.78em'>({sinal}{lucro_pct_at:.2f}%)</span>".replace(",", "X").replace(".", ",").replace("X", "."),
                        unsafe_allow_html=True
                    )
                
                with st.expander("💸 Negociar (Comprar / Vender)"):
                    c_op1, c_op2, c_op3, c_op4 = st.columns(4)
                    with c_op1:
                        op_tipo = st.selectbox("Operação", ["Compra", "Venda"], key=f"op_tipo_{a['id']}")
                    with c_op2:
                        op_qtd = st.number_input("Qtd", min_value=1, value=1, key=f"op_qtd_{a['id']}")
                    with c_op3:
                        op_preco = st.number_input("Preço (R$)", min_value=0.01, value=float(preco_atual), key=f"op_prc_{a['id']}", help="Se alterar o preço, cria ordem condicional.")
                        if abs(op_preco - preco_atual) >= 0.01:
                            st.caption(f"Preço atual: R$ {preco_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    with c_op4:
                        valor_op_preview = op_qtd * op_preco
                        st.markdown(f"**Total:** {formatar_moeda(valor_op_preview).replace('$', chr(36))}")
                        if st.button("Executar", key=f"btn_exec_{a['id']}", type="primary", use_container_width=True):
                            valor_op = op_qtd * op_preco
                            caixa_atual = port.get("montante_disponivel", 0)
                            tipo_ord = "compra" if op_tipo == "Compra" else "venda"
                            executa_agora = deve_executar_ordem(tipo_ord, op_preco, preco_atual)
                            
                            if not executa_agora:
                                # Ordem condicional
                                if tipo_ord == "venda" and op_qtd > a["quantidade"]:
                                    st.error("⚠️ Não possui essa quantidade para vender.")
                                else:
                                    criar_ordem_pendente(port["id"], a["ticker"], tipo_ord, op_qtd, op_preco)
                                    st.warning(f"⏳ Ordem de {tipo_ord} de {a['ticker']} a R$ {op_preco:.2f} **ainda não foi executada**. Será executada quando o preço for atingido.")
                                    st.toast(f"📋 Ordem condicional criada!", icon="📋")
                            elif op_tipo == "Compra":
                                if valor_op > caixa_atual:
                                    st.warning(f"⚠️ Caixa insuficiente! Esta compra causará saldo negativo, sujeito a cobrança diária de juros. Clique em Executar novamente para confirmar.")
                                    if not st.session_state.get(f"conf_op_cart_{a['id']}", False):
                                        st.session_state[f"conf_op_cart_{a['id']}"] = True
                                        st.stop()
                                    st.session_state[f"conf_op_cart_{a['id']}"] = False
                                    
                                q_ant = a["quantidade"]
                                p_ant = a["preco_medio"]
                                q_nova = q_ant + op_qtd
                                p_novo = ((q_ant * p_ant) + valor_op) / q_nova
                                atualizar_ativo(a["id"], quantidade=q_nova, preco_medio=p_novo)
                                registrar_transacao(port["id"], "compra", valor_op, a["ticker"], op_qtd, op_preco, f"Compra {a['ticker']}", date.today())
                                atualizar_portfolio(port["id"], montante_disponivel=caixa_atual - valor_op)
                                st.toast(f"Compra de {a['ticker']} registrada! 💸")
                                st.rerun()
                            else: # Venda imediata
                                if op_qtd > a["quantidade"]:
                                    st.error("⚠️ Você não possui essa quantidade toda para vender.")
                                else:
                                    nova_qtd = a["quantidade"] - op_qtd
                                    if nova_qtd <= 0:
                                        deletar_ativo(a["id"])
                                    else:
                                        atualizar_ativo(a["id"], quantidade=nova_qtd, preco_medio=a["preco_medio"])
                                    registrar_transacao(port["id"], "venda", valor_op, a["ticker"], op_qtd, op_preco, f"Venda {a['ticker']}", date.today())
                                    atualizar_portfolio(port["id"], montante_disponivel=caixa_atual + valor_op)
                                    st.toast(f"Venda de {a['ticker']} registrada! 💰")
                                    st.rerun()
    else:            
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
                preco_w = buscar_preco_atual(ticker_w)
                preco_val = preco_w.get("preco_atual", 0) if isinstance(preco_w, dict) else 0
                var_dia = preco_w.get("variacao_dia", 0) if isinstance(preco_w, dict) else 0
                nome_w = nome_ativo(ticker_w)
                cor_var = "#00C851" if var_dia >= 0 else "#FF4444"
                sinal_var = "+" if var_dia >= 0 else ""
                
                # Header: Ticker + Info/Delete buttons
                c_nome_w, c_acoes_w = st.columns([5, 2])
                with c_nome_w:
                    st.markdown(f"**{ticker_w}** — {nome_w}")
                    st.caption(f"{'Adicionado manualmente' if w['adicionado_manualmente'] else 'Sugerido pela IA'} | Preço: R\\$ {preco_val:,.2f} | Var: {sinal_var}{var_dia:.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))
                with c_acoes_w:
                    bc1, bc2 = st.columns(2)
                    with bc1:
                        if st.button("ℹ️ Info", key=f"w_info_{w['id']}", use_container_width=True):
                            st.session_state.view_asset_ticker = ticker_w
                            st.session_state.voltar_para_pagina = "pages/_7_📂_Carteira_Detalhe.py"
                            st.switch_page("pages/_8_📄_Ativo.py")
                    with bc2:
                        if st.button("🗑️ Remover", key=f"w_del_{w['id']}", use_container_width=True):
                            remover_watchlist(w["id"])
                            st.rerun()
                
                # Negotiation expander
                if preco_val > 0:
                    with st.expander("💸 Negociar"):
                        wc1, wc2, wc3, wc4 = st.columns(4)
                        with wc1:
                            op_tipo_w = st.selectbox("Operação", ["Compra", "Venda"], key=f"w_tipo_{w['id']}")
                        with wc2:
                            qtd_w = st.number_input("Qtd", min_value=1, value=1, key=f"w_qtd_{w['id']}", step=1)
                        with wc3:
                            prc_w = st.number_input("Preço (R$)", min_value=0.01, value=float(preco_val), key=f"w_prc_{w['id']}", step=0.1, help="Alterar cria ordem condicional.")
                            if abs(prc_w - preco_val) >= 0.01:
                                st.caption(f"Preço atual: R$ {preco_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                        with wc4:
                            vt_w = qtd_w * prc_w
                            st.markdown(f"**Total:** R\\$ {vt_w:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                            if st.button("Executar", key=f"w_exec_{w['id']}", type="primary", use_container_width=True):
                                caixa_w = port.get("montante_disponivel", 0)
                                tipo_ord = "compra" if op_tipo_w == "Compra" else "venda"
                                executa_agora = deve_executar_ordem(tipo_ord, prc_w, preco_val)
                                if not executa_agora:
                                    criar_ordem_pendente(port["id"], ticker_w, tipo_ord, qtd_w, prc_w)
                                    st.warning(f"⏳ Ordem de {tipo_ord} de {ticker_w} a R$ {prc_w:.2f} **ainda não foi executada**. Será executada quando o preço for atingido.")
                                elif tipo_ord == "compra":
                                    if vt_w > caixa_w:
                                        st.warning(f"⚠️ Caixa insuficiente! Esta compra causará saldo negativo, sujeito a cobrança diária de juros. Clique em Executar novamente para confirmar.")
                                        if not st.session_state.get(f"conf_op_watch_{w['id']}", False):
                                            st.session_state[f"conf_op_watch_{w['id']}"] = True
                                            st.stop()
                                        st.session_state[f"conf_op_watch_{w['id']}"] = False
                                        
                                    ativo_ext = next((x for x in ativos if x["ticker"] == ticker_w), None)
                                    if ativo_ext:
                                        q_ant = ativo_ext["quantidade"]; p_ant = ativo_ext["preco_medio"]
                                        atualizar_ativo(ativo_ext["id"], quantidade=q_ant + qtd_w, preco_medio=((q_ant * p_ant) + vt_w) / (q_ant + qtd_w))
                                    else:
                                        adicionar_ativo(port["id"], ticker_w, prc_w, qtd_w, date.today())
                                    registrar_transacao(port["id"], "compra", vt_w, ticker_w, qtd_w, prc_w, "Compra (Watch)", date.today())
                                    atualizar_portfolio(port["id"], montante_disponivel=caixa_w - vt_w)
                                    st.toast(f"{ticker_w} comprado! 🎉", icon="✅")
                                    st.rerun()
                                else:
                                    ativo_ext = next((x for x in ativos if x["ticker"] == ticker_w), None)
                                    if not ativo_ext or qtd_w > ativo_ext["quantidade"]:
                                        st.error("⚠️ Não possui essa quantidade para vender.")
                                    else:
                                        nq = ativo_ext["quantidade"] - qtd_w
                                        if nq <= 0: deletar_ativo(ativo_ext["id"])
                                        else: atualizar_ativo(ativo_ext["id"], quantidade=nq, preco_medio=ativo_ext["preco_medio"])
                                        registrar_transacao(port["id"], "venda", vt_w, ticker_w, qtd_w, prc_w, "Venda (Watch)", date.today())
                                        atualizar_portfolio(port["id"], montante_disponivel=caixa_w + vt_w)
                                        st.toast(f"{ticker_w} vendido! 💰", icon="✅"); st.rerun()

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
                    
                    # Header: Ticker + Info/Watchlist buttons
                    c_nome_s, c_btns_s = st.columns([5, 2])
                    with c_nome_s:
                        st.markdown(f"**{ticker_sug}** — {nome_ativo(ticker_sug)}  |  Alocação: {alocacao_pct:.0f}%")
                        st.caption(f"📝 {sug.get('motivo', '')}")
                    with c_btns_s:
                        sb1, sb2 = st.columns(2)
                        with sb1:
                            if st.button("ℹ️ Info", key=f"info_sug_{i}_{ticker_sug}", use_container_width=True):
                                st.session_state.view_asset_ticker = ticker_sug
                                st.session_state.voltar_para_pagina = "pages/_7_📂_Carteira_Detalhe.py"
                                st.switch_page("pages/_8_📄_Ativo.py")
                        with sb2:
                            if st.button("👁️ Watch", key=f"watch_sug_{i}_{ticker_sug}", use_container_width=True):
                                adicionar_watchlist(portfolio_id, ticker_sug)
                                st.toast(f"{ticker_sug} adicionado à watchlist!", icon="✅")
                                st.rerun()
                    
                    # Pre-expanded negotiation
                    with st.expander("💸 Negociar", expanded=True):
                        cs1, cs2, cs3, cs4 = st.columns(4)
                        with cs1:
                            op_tipo_sug = st.selectbox("Operação", ["Compra", "Venda"], key=f"op_sug_tipo_{i}_{ticker_sug}")
                        with cs2:
                            qtd_editada = st.number_input("Qtd", min_value=1, value=max(1, qtd_sug_ia), key=f"qtd_sug_{i}_{ticker_sug}", step=1)
                        with cs3:
                            preco_editado = st.number_input("Preço (R$)", min_value=0.01, value=float(preco_sug), key=f"prc_sug_{i}_{ticker_sug}", step=0.1, help="Se alterar o preço, cria ordem condicional.")
                            if abs(preco_editado - preco_sug) >= 0.01:
                                st.caption(f"Preço atual: R$ {preco_sug:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                        with cs4:
                            valor_total_display = qtd_editada * preco_editado
                            st.markdown(f"**Total:** R\\$ {valor_total_display:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                            if st.button("Executar", key=f"exec_sug_{i}_{ticker_sug}", type="primary", use_container_width=True):
                                caixa_at = port.get("montante_disponivel", 0)
                                tipo_ord = "compra" if op_tipo_sug == "Compra" else "venda"
                                executa_agora = deve_executar_ordem(tipo_ord, preco_editado, preco_sug) if preco_sug > 0 else False
                                
                                if not executa_agora:
                                    criar_ordem_pendente(port["id"], ticker_sug, tipo_ord, qtd_editada, preco_editado)
                                    st.warning(f"⏳ Ordem de {tipo_ord} de {ticker_sug} a R$ {preco_editado:.2f} **ainda não foi executada**. Será executada quando o preço for atingido.")
                                    st.toast(f"📋 Ordem condicional de {ticker_sug} criada!", icon="📋")
                                elif tipo_ord == "compra":
                                    v_compra = qtd_editada * preco_editado
                                    if v_compra > caixa_at and not st.session_state.get(f"confirm_negative_{ticker_sug}_{port['id']}", False):
                                        st.session_state[f"confirm_negative_{ticker_sug}_{port['id']}"] = True
                                        st.warning("⚠️ Caixa insuficiente! A compra resultará em saldo negativo. Clique novamente em Executar para confirmar e arcar com os juros (Selic).")
                                    else:
                                        st.session_state[f"confirm_negative_{ticker_sug}_{port['id']}"] = False
                                        ativo_ext = next((x for x in ativos if x["ticker"] == ticker_sug), None)
                                        if ativo_ext:
                                            q_ant = ativo_ext["quantidade"]
                                            p_ant = ativo_ext["preco_medio"]
                                            q_nova = q_ant + qtd_editada
                                            p_novo = ((q_ant * p_ant) + v_compra) / q_nova
                                            atualizar_ativo(ativo_ext["id"], quantidade=q_nova, preco_medio=p_novo)
                                        else:
                                            adicionar_ativo(port["id"], ticker_sug, preco_editado, qtd_editada, date.today())
                                        registrar_transacao(port["id"], "compra", v_compra, ticker_sug, qtd_editada, preco_editado, "Compra Sugerida IA", date.today())
                                        atualizar_portfolio(port["id"], montante_disponivel=caixa_at - v_compra)
                                        st.toast(f"{ticker_sug} comprado! 🎉", icon="✅")
                                        st.rerun()
                                else:
                                    ativo_ext = next((x for x in ativos if x["ticker"] == ticker_sug), None)
                                    if not ativo_ext or qtd_editada > ativo_ext["quantidade"]:
                                        st.error("⚠️ Não possui essa quantidade para vender.")
                                    else:
                                        v_venda = qtd_editada * preco_editado
                                        nova_qtd = ativo_ext["quantidade"] - qtd_editada
                                        if nova_qtd <= 0:
                                            deletar_ativo(ativo_ext["id"])
                                        else:
                                            atualizar_ativo(ativo_ext["id"], quantidade=nova_qtd, preco_medio=ativo_ext["preco_medio"])
                                        registrar_transacao(port["id"], "venda", v_venda, ticker_sug, qtd_editada, preco_editado, "Venda IA", date.today())
                                        atualizar_portfolio(port["id"], montante_disponivel=caixa_at + v_venda)
                                        st.toast(f"{ticker_sug} vendido! 💰", icon="✅")
                                        st.rerun()
        
        # Botão "Comprar Tudo" (executa todas as sugestões com qtd editada)
        st.markdown("---")
        total_compra_tudo = 0
        sugestoes_para_compra = []
        for i, sug in enumerate(sugestoes_mostrar):
            ticker_sug = sug.get("ticker", "")
            preco_sug = sug.get("preco_estimado", 0.0)
            qtd_atual = st.session_state.get(f"qtd_sug_{i}_{ticker_sug}", sug.get("quantidade", 0))
            prc_atual = st.session_state.get(f"prc_sug_{i}_{ticker_sug}", preco_sug)
            if qtd_atual > 0:
                valor = qtd_atual * prc_atual
                total_compra_tudo += valor
                sugestoes_para_compra.append({"ticker": ticker_sug, "quantidade": qtd_atual, "preco": prc_atual, "valor_total": valor})
        
        if sugestoes_para_compra:
            caixa_disponivel = port.get("montante_disponivel", 0)
            
            col_btn1, col_btn2 = st.columns([3, 1])
            with col_btn1:
                st.markdown(
                    f"**🛒 Comprar todos os {len(sugestoes_para_compra)} ativos** — "
                    f"Total: R\\$ {total_compra_tudo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
            with col_btn2:
                if st.button("🛒 Comprar Tudo", key="btn_comprar_tudo_ia", type="primary", use_container_width=True):
                    if total_compra_tudo > caixa_disponivel and not st.session_state.get("confirm_negative_comprar_tudo", False):
                        st.session_state["confirm_negative_comprar_tudo"] = True
                        st.warning(f"⚠️ O total (R\\$ {total_compra_tudo:,.2f}) excede o caixa disponível (R\\$ {caixa_disponivel:,.2f}). A compra resultará em saldo negativo. Clique novamente em 'Comprar Tudo' para confirmar e arcar com os juros (Selic).")
                    else:
                        st.session_state["confirm_negative_comprar_tudo"] = False
                        caixa_restante = caixa_disponivel
                        compras_ok = 0
                        for sug_exec in sugestoes_para_compra:
                            t_sug = sug_exec["ticker"]
                            q_sug = sug_exec["quantidade"]
                            p_sug = sug_exec["preco"]
                            v_total = sug_exec["valor_total"]
                            preco_mercado = sug.get("preco_estimado", p_sug)
                            executa_agora = deve_executar_ordem("compra", p_sug, preco_mercado) if preco_mercado > 0 else False
                            
                            if not executa_agora:
                                criar_ordem_pendente(port["id"], t_sug, "compra", q_sug, p_sug)
                                compras_ok += 1
                                continue
                            
                            # No longer checking v_total > caixa_restante here, as negative balance is allowed with confirmation
                            
                            ativo_existente = next((x for x in ativos if x["ticker"] == t_sug), None)
                            if ativo_existente:
                                q_ant = ativo_existente["quantidade"]; p_ant = ativo_existente["preco_medio"]
                                q_nova = q_ant + q_sug
                                p_novo = ((q_ant * p_ant) + v_total) / q_nova
                                atualizar_ativo(ativo_existente["id"], quantidade=q_nova, preco_medio=p_novo)
                            else:
                                adicionar_ativo(port["id"], t_sug, p_sug, q_sug, date.today())
                            registrar_transacao(port["id"], "compra", v_total, t_sug, q_sug, p_sug, "Compra IA (Lote)", date.today())
                            caixa_restante -= v_total
                            compras_ok += 1
                        
                        atualizar_portfolio(port["id"], montante_disponivel=caixa_restante)
                        if compras_ok > 0:
                            st.toast(f"{compras_ok} compra(s) registrada(s) com sucesso. (Ordens executadas imediatamente ou marcadas como pendentes).", icon="✅")
                            st.session_state["ia_resumo_geral"] = None # Limpa para não reexibir
                            st.rerun()
        
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
                    cor_acao = "#00C851" if s['acao'] == "compra" else "#FFBB33"
                    preco_sug_inline = 0.0
                    cot = buscar_preco_atual(s["ticker"])
                    if isinstance(cot, dict) and cot.get("preco_atual", 0) > 0:
                        preco_sug_inline = float(cot["preco_atual"])
                    
                    c_nome_a, c_btns_a = st.columns([5, 2])
                    with c_nome_a:
                        st.markdown(f"**{s['ticker']}** — {nome_ativo(s['ticker'])}{novo_label}")
                        st.markdown(f"<span style='color:{cor_acao}'>{s['acao'].upper()}</span> (Score: {s['score']}/100)", unsafe_allow_html=True)
                    with c_btns_a:
                        ab1, ab2 = st.columns(2)
                        with ab1:
                            if st.button("ℹ️ Info", key=f"alc_i_{idx_s}_{s['ticker']}", use_container_width=True):
                                st.session_state.view_asset_ticker = s['ticker']
                                st.session_state.voltar_para_pagina = "pages/_7_📂_Carteira_Detalhe.py"
                                st.switch_page("pages/_8_📄_Ativo.py")
                        with ab2:
                            if st.button("👁️ Watch", key=f"alc_watch_{idx_s}_{s['ticker']}", use_container_width=True):
                                adicionar_watchlist(portfolio_id, s['ticker'])
                                st.toast(f"{s['ticker']} adicionado à watchlist!", icon="✅")
                                st.rerun()
                    
                    st.info(s['texto'])
                    
                    if preco_sug_inline > 0:
                        with st.expander("💸 Negociar", expanded=True):
                            ca1, ca2, ca3, ca4 = st.columns(4)
                            with ca1:
                                op_tipo_alg = st.selectbox("Operação", ["Compra", "Venda"], key=f"alg_tipo_{idx_s}_{s['ticker']}")
                            with ca2:
                                qtd_alg = st.number_input("Qtd", min_value=1, value=1, key=f"alg_qtd_{idx_s}_{s['ticker']}", step=1)
                            with ca3:
                                prc_alg = st.number_input("Preço (R$)", min_value=0.01, value=float(preco_sug_inline), key=f"alg_prc_{idx_s}_{s['ticker']}", step=0.1, help="Alterar cria ordem condicional.")
                                if abs(prc_alg - preco_sug_inline) >= 0.01:
                                    st.caption(f"Preço atual: R$ {preco_sug_inline:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                            with ca4:
                                vt_alg = qtd_alg * prc_alg
                                st.markdown(f"**Total:** R\\$ {vt_alg:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                                if st.button("Executar", key=f"alg_exec_{idx_s}_{s['ticker']}", type="primary", use_container_width=True):
                                    caixa_alg = port.get("montante_disponivel", 0)
                                    tipo_ord = "compra" if op_tipo_alg == "Compra" else "venda"
                                    executa_agora = deve_executar_ordem(tipo_ord, prc_alg, preco_sug_inline)
                                    if not executa_agora:
                                        criar_ordem_pendente(port["id"], s['ticker'], tipo_ord, qtd_alg, prc_alg)
                                        st.warning(f"⏳ Ordem de {tipo_ord} de {s['ticker']} a R$ {prc_alg:.2f} **ainda não foi executada**. Será executada quando o preço for atingido.")
                                    elif tipo_ord == "compra":
                                        if vt_alg > caixa_alg:
                                            st.warning(f"⚠️ Caixa insuficiente! Esta compra causará saldo negativo, sujeito a cobrança diária de juros. Clique em Executar novamente para confirmar.")
                                            if not st.session_state.get(f"conf_op_alg_{idx_s}_{s['ticker']}", False):
                                                st.session_state[f"conf_op_alg_{idx_s}_{s['ticker']}"] = True
                                                st.stop()
                                            st.session_state[f"conf_op_alg_{idx_s}_{s['ticker']}"] = False
                                            
                                        ativo_ext = next((x for x in ativos if x["ticker"] == s['ticker']), None)
                                        if ativo_ext:
                                            q_ant = ativo_ext["quantidade"]; p_ant = ativo_ext["preco_medio"]
                                            atualizar_ativo(ativo_ext["id"], quantidade=q_ant + qtd_alg, preco_medio=((q_ant * p_ant) + vt_alg) / (q_ant + qtd_alg))
                                        else:
                                            adicionar_ativo(port["id"], s['ticker'], prc_alg, qtd_alg, date.today())
                                        registrar_transacao(port["id"], "compra", vt_alg, s['ticker'], qtd_alg, prc_alg, "Compra Algoritmo", date.today())
                                        atualizar_portfolio(port["id"], montante_disponivel=caixa_alg - vt_alg)
                                        st.toast(f"{s['ticker']} comprado! 🎉", icon="✅")
                                        st.rerun()
                                    else:
                                        ativo_ext = next((x for x in ativos if x["ticker"] == s['ticker']), None)
                                        if not ativo_ext or qtd_alg > ativo_ext["quantidade"]:
                                            st.error("⚠️ Não possui essa quantidade.")
                                        else:
                                            nq = ativo_ext["quantidade"] - qtd_alg
                                            if nq <= 0: deletar_ativo(ativo_ext["id"])
                                            else: atualizar_ativo(ativo_ext["id"], quantidade=nq, preco_medio=ativo_ext["preco_medio"])
                                            registrar_transacao(port["id"], "venda", vt_alg, s['ticker'], qtd_alg, prc_alg, "Venda Algoritmo", date.today())
                                            atualizar_portfolio(port["id"], montante_disponivel=caixa_alg + vt_alg)
                                            st.toast(f"{s['ticker']} vendido! 💰", icon="✅"); st.rerun()
        else:
            st.info("Nenhuma sugestão de compra/observação encontrada pelo algoritmo técnico.")
    else:
        st.info("Nenhuma sugestão encontrada. Adicione ativos ou configure os setores preferidos da carteira para receber sugestões.")

with tab4:
    st.subheader("Sugestões de Movimentações")
    st.markdown("Avalie se é necessário **rebalancear ou vender** algum ativo da sua carteira atual.")
    
    # Tickers que já estão na carteira
    tickers_na_carteira = {a["ticker"] for a in ativos}
    
    st.markdown("#### Algoritmo Técnico — Movimentações Sugeridas")
    sugestoes_mov = gerar_sugestoes_carteira(portfolio_id)
    
    if sugestoes_mov:
        sugestoes_venda = [s for s in sugestoes_mov if s.get("acao") == "venda" and s.get("ticker") in tickers_na_carteira]
        if sugestoes_venda:
            for idx_m, s in enumerate(sugestoes_venda):
                with st.container(border=True):
                    ativo_cart = next((a for a in ativos if a["ticker"] == s["ticker"]), None)
                    qtd_cart = ativo_cart["quantidade"] if ativo_cart else 0
                    pm_cart = ativo_cart["preco_medio"] if ativo_cart else 0
                    cot = buscar_preco_atual(s["ticker"])
                    preco_atual_mov = float(cot["preco_atual"]) if isinstance(cot, dict) and cot.get("preco_atual", 0) > 0 else pm_cart
                    lucro_total = (preco_atual_mov - pm_cart) * qtd_cart
                    cor_lucro_m = "#00C851" if lucro_total >= 0 else "#FF4444"
                    
                    c_nm, c_bm = st.columns([5, 2])
                    with c_nm:
                        novo_label = " 🆕 **NOVO**" if s.get("novo") else ""
                        st.markdown(f"**{s['ticker']}** — {nome_ativo(s['ticker'])}{novo_label}  |  {qtd_cart} cotas")
                        st.markdown(f"<span style='color:#FF4444'>VENDA</span> (Score: {s['score']}/100) | PM: {formatar_moeda_md(pm_cart)} | Atual: {formatar_moeda_md(preco_atual_mov)} | L/P: <span style='color:{cor_lucro_m}'>{formatar_moeda_md(lucro_total)}</span>", unsafe_allow_html=True)
                    with c_bm:
                        bm1, bm2 = st.columns(2)
                        with bm1:
                            if st.button("ℹ️ Info", key=f"mov_i_{idx_m}_{s['ticker']}", use_container_width=True):
                                st.session_state.view_asset_ticker = s['ticker']
                                st.session_state.voltar_para_pagina = "pages/_7_📂_Carteira_Detalhe.py"
                                st.switch_page("pages/_8_📄_Ativo.py")
                        with bm2:
                            if st.button("👁️ Watch", key=f"mov_watch_{idx_m}_{s['ticker']}", use_container_width=True):
                                adicionar_watchlist(portfolio_id, s['ticker'])
                                st.toast(f"{s['ticker']} adicionado à watchlist!", icon="✅")
                                st.rerun()
                    
                    st.info(s['texto'])
                    
                    if preco_atual_mov > 0:
                        with st.expander("💸 Negociar", expanded=True):
                            cm1, cm2, cm3, cm4 = st.columns(4)
                            with cm1:
                                op_tipo_mov = st.selectbox("Operação", ["Venda", "Compra"], key=f"mov_tipo_{idx_m}_{s['ticker']}")
                            with cm2:
                                qtd_mov = st.number_input("Qtd", min_value=1, value=1, key=f"mov_qtd_{idx_m}_{s['ticker']}", step=1)
                            with cm3:
                                prc_mov = st.number_input("Preço (R$)", min_value=0.01, value=float(preco_atual_mov), key=f"mov_prc_{idx_m}_{s['ticker']}", step=0.1, help="Alterar cria ordem condicional.")
                                if abs(prc_mov - preco_atual_mov) >= 0.01:
                                    st.caption(f"Preço atual: R$ {preco_atual_mov:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                            with cm4:
                                vt_mov = qtd_mov * prc_mov
                                st.markdown(f"**Total:** R\\$ {vt_mov:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                                if st.button("Executar", key=f"mov_exec_{idx_m}_{s['ticker']}", type="primary", use_container_width=True):
                                    caixa_mov = port.get("montante_disponivel", 0)
                                    tipo_ord = "venda" if op_tipo_mov == "Venda" else "compra"
                                    executa_agora = deve_executar_ordem(tipo_ord, prc_mov, preco_atual_mov)
                                    if not executa_agora:
                                        if tipo_ord == "venda" and ativo_cart and qtd_mov > ativo_cart["quantidade"]:
                                            st.error("⚠️ Não possui essa quantidade.")
                                        else:
                                            criar_ordem_pendente(port["id"], s['ticker'], tipo_ord, qtd_mov, prc_mov)
                                            st.warning(f"⏳ Ordem de {tipo_ord} de {s['ticker']} a R$ {prc_mov:.2f} **ainda não foi executada**. Será executada quando o preço for atingido.")
                                    elif tipo_ord == "venda":
                                        if not ativo_cart or qtd_mov > ativo_cart["quantidade"]:
                                            st.error(f"⚠️ Você só tem {qtd_cart} papéis!")
                                        else:
                                            nq = ativo_cart["quantidade"] - qtd_mov
                                            if nq <= 0: deletar_ativo(ativo_cart["id"])
                                            else: atualizar_ativo(ativo_cart["id"], quantidade=nq, preco_medio=ativo_cart["preco_medio"])
                                            registrar_transacao(port["id"], "venda", vt_mov, s['ticker'], qtd_mov, prc_mov, "Venda (Mov)", date.today())
                                            atualizar_portfolio(port["id"], montante_disponivel=caixa_mov + vt_mov)
                                            st.toast(f"{s['ticker']} vendido! 💰", icon="✅"); st.rerun()
                                    else:
                                        if vt_mov > caixa_mov:
                                            st.warning(f"⚠️ Caixa insuficiente! Esta compra causará saldo negativo, sujeito a cobrança diária de juros. Clique em Executar novamente para confirmar.")
                                            if not st.session_state.get(f"conf_op_mov_{idx_m}_{s['ticker']}", False):
                                                st.session_state[f"conf_op_mov_{idx_m}_{s['ticker']}"] = True
                                                st.stop()
                                            st.session_state[f"conf_op_mov_{idx_m}_{s['ticker']}"] = False
                                            
                                        if ativo_cart:
                                            q_ant = ativo_cart["quantidade"]; p_ant = ativo_cart["preco_medio"]
                                            atualizar_ativo(ativo_cart["id"], quantidade=q_ant + qtd_mov, preco_medio=((q_ant * p_ant) + vt_mov) / (q_ant + qtd_mov))
                                        else:
                                            adicionar_ativo(port["id"], s['ticker'], prc_mov, qtd_mov, date.today())
                                        registrar_transacao(port["id"], "compra", vt_mov, s['ticker'], qtd_mov, prc_mov, "Compra (Mov)", date.today())
                                        atualizar_portfolio(port["id"], montante_disponivel=caixa_mov - vt_mov)
                                        st.toast(f"{s['ticker']} comprado! 🎉", icon="✅")
                                        st.rerun()
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

# --- ORDENS PENDENTES ---
with tab_ordens:
    st.subheader("📋 Ordens Pendentes")
    ordens = listar_ordens_pendentes(portfolio_id)
    
    if ordens:
        for o in ordens:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                with c1:
                    tipo_emoji = "🟢" if o["tipo"] == "compra" else "🔴"
                    st.markdown(f"{tipo_emoji} **{o['ticker']}** — {o['tipo'].upper()}")
                    st.caption(f"Criada em: {formatar_data_br(o['created_at'].split(' ')[0]) if o.get('created_at') else ''}")
                with c2:
                    st.markdown(f"**Preço Alvo:** R\\$ {o['preco_alvo']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                with c3:
                    st.markdown(f"**Qtd:** {o['quantidade']} | **Total:** R\\$ {(o['quantidade'] * o['preco_alvo']):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    # Preço atual para referência
                    p_orc = buscar_preco_atual(o["ticker"])
                    p_orc_val = p_orc.get("preco_atual", 0) if isinstance(p_orc, dict) else 0
                    if p_orc_val > 0:
                        diff_pct = ((o["preco_alvo"] - p_orc_val) / p_orc_val) * 100
                        st.caption(f"Atual: R$ {p_orc_val:,.2f} ({diff_pct:+.1f}%)".replace(",", "X").replace(".", ",").replace("X", "."))
                with c4:
                    cb1, cb2 = st.columns(2)
                    with cb1:
                        if st.button("✏️", key=f"edit_ord_{o['id']}", help="Editar ordem", use_container_width=True):
                            st.session_state[f"editing_order_{o['id']}"] = not st.session_state.get(f"editing_order_{o['id']}", False)
                            st.rerun()
                    with cb2:
                        if st.button("❌", key=f"del_ord_{o['id']}", help="Cancelar ordem", use_container_width=True):
                            cancelar_ordem(o["id"])
                            st.toast(f"Ordem de {o['tipo']} de {o['ticker']} cancelada.", icon="❌")
                            st.rerun()
    
                # Painel de edição inline
                if st.session_state.get(f"editing_order_{o['id']}", False):
                    with st.container(border=True):
                        st.markdown("**✏️ Editar Ordem**")
                        e1, e2, e3, e4 = st.columns(4)
                        with e1:
                            edit_tipo = st.selectbox("Tipo", ["compra", "venda"], index=0 if o["tipo"] == "compra" else 1, key=f"edit_tipo_{o['id']}")
                        with e2:
                            edit_qtd = st.number_input("Quantidade", min_value=1, value=o["quantidade"], key=f"edit_qtd_{o['id']}")
                        with e3:
                            edit_preco = st.number_input("Preço Alvo (R$)", min_value=0.01, value=float(o["preco_alvo"]), step=0.1, key=f"edit_prc_{o['id']}")
                        with e4:
                            st.markdown(f"**Total:** R\\$ {(edit_qtd * edit_preco):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                            if st.button("💾 Salvar", key=f"save_ord_{o['id']}", type="primary", use_container_width=True):
                                from database.crud import atualizar_ordem_pendente
                                atualizar_ordem_pendente(o["id"], tipo=edit_tipo, quantidade=edit_qtd, preco_alvo=edit_preco)
                                # Verificar se a ordem editada deve ser executada imediatamente
                                _p_check = buscar_preco_atual(o["ticker"])
                                _p_check_val = _p_check.get("preco_atual", 0) if isinstance(_p_check, dict) else 0
                                if _p_check_val > 0 and deve_executar_ordem(edit_tipo, edit_preco, _p_check_val):
                                    resultado_exec = executar_ordem_pendente(o["id"])
                                    if resultado_exec:
                                        st.toast(f"✅ Ordem de {o['ticker']} executada imediatamente a R$ {edit_preco:.2f}!", icon="🔔")
                                    else:
                                        st.toast(f"Ordem de {o['ticker']} atualizada! ✅", icon="✅")
                                else:
                                    st.toast(f"Ordem de {o['ticker']} atualizada! ✅", icon="✅")
                                st.session_state[f"editing_order_{o['id']}"] = False
                                st.rerun()
    else:
        st.info("Nenhuma ordem pendente.")


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
                        atualizar_status_acao(acao['id'], "executado")
                        st.toast(f"Movimento {acao['asset_ticker']} marcado como executado! Registre a transação na aba Meus Ativos se necessário.")
                        st.rerun()
                with sc2:
                    if st.button("🗑️ Ignorar", key=f"ign_{acao['id']}", use_container_width=True):
                        atualizar_status_acao(acao['id'], "ignorado")
                        st.rerun()
else:
    st.info("Nenhuma movimentação programada.")

st.markdown("---")

# --- HISTÓRICO DE MOVIMENTAÇÕES ---
with st.expander("📜 Histórico de Movimentações"):
    transacoes = listar_transacoes_portfolio(portfolio_id, limit=50)
    
    if transacoes:
        # Preparar dados para tabela
        dados_tabela = []
        for t in transacoes:
            tipo_emoji = {"aporte": "📥", "retirada": "📤", "compra": "🛒", "venda": "💰", "dividendo": "💵"}.get(t["tipo"], "📋")
            dados_tabela.append({
                "Data": formatar_data_br(t["data"]) if t.get("data") else "",
                "Tipo": f"{tipo_emoji} {t['tipo'].capitalize()}",
                "Ticker": t.get("ticker", "—"),
                "Qtd": t.get("quantidade", "—"),
                "Preço Unit.": f"R$ {t['preco_unitario']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if t.get("preco_unitario") else "—",
                "Valor": f"R$ {t['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "Descrição": t.get("descricao", ""),
                "Origem": t.get("origem", "manual")
            })
        
        df = pd.DataFrame(dados_tabela)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"Mostrando as últimas {len(transacoes)} movimentações.")
    else:
        st.info("Nenhuma movimentação registrada nesta carteira.")

st.markdown("---")
if st.button("⚠️ Excluir Carteira Inteira", type="primary"):
    deletar_portfolio(portfolio_id)
    st.session_state.view_portfolio_id = None
    st.switch_page("pages/3_💼_Carteiras.py")

