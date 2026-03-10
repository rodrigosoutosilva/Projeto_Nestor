"""
📂 Persona Detalhe - Visão detalhada da Persona e suas Carteiras
================================================================

Página oculta do sidebar (prefixo _).
Mostra detalhes da persona selecionada e suas carteiras,
equivalente à página Carteiras mas já filtrado para a persona.
"""

import streamlit as st
import sys, os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.crud import (
    buscar_persona_por_id, atualizar_persona, deletar_persona,
    listar_portfolios_persona, listar_ativos_portfolio,
    resumo_transacoes_portfolio, criar_portfolio,
    adicionar_observacao, listar_observacoes, deletar_observacao
)
from services.market_data import buscar_preco_atual
from utils.helpers import formatar_moeda, formatar_moeda_md, formatar_data_br, injetar_css_global, render_metric

st.set_page_config(page_title="Persona Detalhe", page_icon="🧑", layout="wide")
injetar_css_global()

if "user" not in st.session_state or st.session_state.user is None:
    st.warning("⚠️ Faça login.")
    st.stop()

persona_id = st.session_state.get("view_persona_id", None)
if not persona_id:
    st.error("Nenhuma persona selecionada.")
    if st.button("⬅️ Voltar para Personas"):
        st.switch_page("pages/2_🧑_Personas.py")
    st.stop()

persona = buscar_persona_por_id(persona_id)
if not persona:
    st.error("Persona não encontrada.")
    st.stop()

if st.button("⬅️ Voltar para Personas", key="btn_voltar_personas_top"):
    st.switch_page("pages/2_🧑_Personas.py")

# --- CABEÇALHO ---
if persona["tolerancia_risco"] <= 3:
    cor, perfil = "🟢", "Conservador"
elif persona["tolerancia_risco"] <= 6:
    cor, perfil = "🟡", "Moderado"
else:
    cor, perfil = "🔴", "Arrojado"

freq_label = {"diario": "📅 Diário", "semanal": "📆 Semanal", "mensal": "🗓️ Mensal"}.get(persona.get("frequencia_acao", ""), "")
estilo_label = {"dividendos": "💰 Dividendos", "crescimento": "🚀 Crescimento", "equilibrado": "⚖️ Equilibrado"}.get(persona.get("estilo", ""), "")

st.markdown(f"""
<style>.big-name {{ font-size: 1.76rem !important; font-weight: 700 !important; margin-bottom: 0.3rem; }}</style>
<div class='big-name'>{cor} {persona['nome']}</div>
""", unsafe_allow_html=True)
st.caption(f"Perfil: **{perfil}** | Risco: {persona['tolerancia_risco']}/10 | Estilo: {estilo_label} | Frequência: {freq_label}")

# --- MÉTRICAS CONSOLIDADAS DA PERSONA ---
portfolios = listar_portfolios_persona(persona_id)

caixa_total = 0
patrimonio_total = 0
total_aportado_global = 0
total_ativos = 0
data_mais_antiga = None

for port in portfolios:
    caixa_total += port.get("montante_disponivel", 0)
    ativos_port = listar_ativos_portfolio(port["id"])
    total_ativos += len(ativos_port)
    resumo = resumo_transacoes_portfolio(port["id"])
    total_aportado_global += (resumo["total_aportes"] - resumo["total_retiradas"])
    
    # Descobrir data de criação mais antiga para rendimento anual
    if port.get("created_at"):
        try:
            dt = datetime.fromisoformat(port["created_at"].replace("Z", "+00:00")) if "T" in str(port["created_at"]) else datetime.strptime(str(port["created_at"]), "%Y-%m-%d %H:%M:%S.%f")
        except Exception:
            try:
                dt = datetime.strptime(str(port["created_at"]).split(".")[0], "%Y-%m-%d %H:%M:%S")
            except Exception:
                dt = None
        if dt and (data_mais_antiga is None or dt < data_mais_antiga):
            data_mais_antiga = dt
    
    for a in ativos_port:
        dados_p = buscar_preco_atual(a["ticker"])
        if dados_p and isinstance(dados_p, dict):
            patrimonio_total += a["quantidade"] * dados_p.get("preco_atual", a["preco_medio"])
        else:
            patrimonio_total += a["quantidade"] * a["preco_medio"]

valor_total = caixa_total + patrimonio_total
lucro_acum = valor_total - total_aportado_global if total_aportado_global > 0 else 0
lucro_pct = (lucro_acum / total_aportado_global * 100) if total_aportado_global > 0 else 0

# Calcular rendimento anual projetado
rend_anual = 0.0
if data_mais_antiga and total_aportado_global > 0:
    data_mais_antiga = data_mais_antiga.replace(tzinfo=None)
    dias_desde_criacao = (datetime.utcnow() - data_mais_antiga).days
    if dias_desde_criacao <= 0:
        dias_desde_criacao = 1
    rend_anual = (lucro_pct / dias_desde_criacao) * 365

m1, m2, m3, m4, m5, m6 = st.columns(6)
with m1: render_metric("💎 Patrimônio", valor_total)
with m2: render_metric("💵 Valor Investido", total_aportado_global)
cor_lucro_h = "#00C851" if lucro_acum >= 0 else "#FF4444"
m3.markdown(
    f"<small>📈 Lucro</small><br>"
    f"<b>{formatar_moeda_md(lucro_acum)}</b> "
    f"<span style='color:{cor_lucro_h};font-size:0.8em'>({lucro_pct:+.1f}%)</span>",
    unsafe_allow_html=True
)
cor_rend = "#00C851" if rend_anual >= 0 else "#FF4444"
m4.markdown(
    f"<small>📅 Rend. Anual</small><br>"
    f"<b style='color:{cor_rend}'>{rend_anual:+.1f}% a.a.</b>",
    unsafe_allow_html=True
)
with m5: render_metric("🏦 Caixa", caixa_total)
with m6: render_metric("💼 Carteiras", len(portfolios), "numero")

# --- OBSERVAÇÕES ---
with st.expander("📝 Observações", expanded=False):
    observacoes = listar_observacoes("persona", persona_id)
    
    if observacoes:
        for obs in observacoes:
            c_obs_txt, c_obs_del = st.columns([6, 1])
            with c_obs_txt:
                data_obs = formatar_data_br(obs["created_at"].split(" ")[0]) if obs.get("created_at") else ""
                st.markdown(f"• {obs['texto']}  \n<small style='color:#888'>{data_obs}</small>", unsafe_allow_html=True)
            with c_obs_del:
                if st.button("🗑️", key=f"del_obs_{obs['id']}", help="Remover"):
                    deletar_observacao(obs["id"])
                    st.rerun()
    else:
        st.caption("Nenhuma observação registrada.")
    
    st.markdown("---")
    c_nova_obs, c_btn_obs = st.columns([5, 1])
    with c_nova_obs:
        nova_obs = st.text_input("Nova observação", placeholder="Escreva uma nota...", key="nova_obs_persona", label_visibility="collapsed")
    with c_btn_obs:
        if st.button("➕", key="btn_add_obs_persona", use_container_width=True, help="Adicionar observação"):
            if nova_obs and nova_obs.strip():
                adicionar_observacao("persona", persona_id, nova_obs.strip())
                st.rerun()

# --- EDIÇÃO DA PERSONA ---
if "persona_edit_open" not in st.session_state:
    st.session_state.persona_edit_open = False

if st.session_state.get("persona_salva_msg"):
    st.success("✅ Persona atualizada com sucesso!")
    st.session_state.persona_salva_msg = False

if st.button("✏️ Editar Persona", key="toggle_edit_persona"):
    st.session_state.persona_edit_open = not st.session_state.persona_edit_open
    st.rerun()

if st.session_state.persona_edit_open:
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            novo_nome = st.text_input("Nome:", value=persona["nome"], key="edit_pn")
            nova_freq = st.selectbox("Frequência:", ["diario", "semanal", "mensal"],
                                      index=["diario", "semanal", "mensal"].index(persona.get("frequencia_acao", "mensal")),
                                      format_func=lambda x: {"diario": "📅 Diário", "semanal": "📆 Semanal", "mensal": "🗓️ Mensal"}[x],
                                      key="edit_pf")
        with col2:
            nova_tol = st.slider("Tolerância:", 0, 10, persona["tolerancia_risco"], key="edit_pt")
            novo_estilo = st.selectbox("Estilo:", ["dividendos", "crescimento", "equilibrado"],
                                        index=["dividendos", "crescimento", "equilibrado"].index(persona.get("estilo", "dividendos")),
                                        format_func=lambda x: {"dividendos":"💰 Dividendos","crescimento":"🚀 Crescimento","equilibrado":"⚖️ Equilibrado"}[x],
                                        key="edit_pe")
        if st.button("💾 Salvar", key="save_persona", use_container_width=True):
            atualizar_persona(persona_id, nome=novo_nome, tolerancia_risco=nova_tol, frequencia_acao=nova_freq, estilo=novo_estilo)
            st.session_state.persona_edit_open = False
            st.session_state.persona_salva_msg = True
            st.rerun()

st.markdown("---")

# --- CARTEIRAS DA PERSONA ---
st.subheader(f"💼 Carteiras de {persona['nome']}")

if not portfolios:
    st.info("Nenhuma carteira nesta persona.")
else:
    cols = st.columns(2)
    for i, port in enumerate(portfolios):
        with cols[i % 2]:
            tipo_emoji = {"acoes": "📈", "fiis": "🏢", "misto": "🔀"}.get(port.get("tipo_ativo", ""), "📊")
            with st.container(border=True):
                st.markdown(f"#### {tipo_emoji} {port['nome']}")
                st.caption(f"Prazo: {port.get('objetivo_prazo', 'N/A').capitalize()}")
                
                caixa = port.get("montante_disponivel", 0)
                ativos_port = listar_ativos_portfolio(port["id"])
                resumo_port = resumo_transacoes_portfolio(port["id"])
                
                patrimonio = 0
                for a in ativos_port:
                    dados_p = buscar_preco_atual(a["ticker"])
                    if dados_p and isinstance(dados_p, dict):
                        patrimonio += a["quantidade"] * dados_p.get("preco_atual", a["preco_medio"])
                    else:
                        patrimonio += a["quantidade"] * a["preco_medio"]
                
                vt = caixa + patrimonio
                ta = resumo_port["total_aportes"] - resumo_port["total_retiradas"]
                la = vt - ta if ta > 0 else 0
                lp = (la / ta * 100) if ta > 0 else 0
                
                # Rendimento anual da carteira
                rend_anual_port = 0.0
                if port.get("created_at") and ta > 0:
                    try:
                        dt_port = datetime.fromisoformat(port["created_at"].replace("Z", "+00:00")) if "T" in str(port["created_at"]) else datetime.strptime(str(port["created_at"]).split(".")[0], "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        dt_port = None
                    if dt_port:
                        dias = (datetime.utcnow() - dt_port).days
                        if dias > 0:
                            rend_anual_port = (lp / dias) * 365
                
                st.metric("💎 Patrimônio", formatar_moeda(vt))
                mc1, mc2 = st.columns(2)
                mc1.markdown(f"💵 **Investido:** {formatar_moeda_md(ta)}", unsafe_allow_html=True)
                cor_lucro_port = "green" if la >= 0 else "red"
                mc2.markdown(f"📈 **Lucro:** <span style='color:{cor_lucro_port}'>{formatar_moeda_md(la)}</span> <small style='color:{cor_lucro_port}'>({lp:+.1f}%)</small>", unsafe_allow_html=True)
                
                mc3, mc4 = st.columns(2)
                cor_rend_p = "#00C851" if rend_anual_port >= 0 else "#FF4444"
                mc3.markdown(f"📅 **Rend. Anual:** <b style='color:{cor_rend_p}'>{rend_anual_port:+.1f}% a.a.</b>", unsafe_allow_html=True)
                mc4.markdown(f"📊 **{len(ativos_port)}** ativo(s)")
                
                if port.get('aporte_periodico', 0) > 0:
                    fl = {"semanal":"sem","quinzenal":"quinz","mensal":"mês"}.get(port.get('frequencia_aporte',''),'')
                    st.caption(f"💸 Aporte: {formatar_moeda(port['aporte_periodico'])}/{fl}".replace("$", r"\$"))
                
                st.divider()
                # Botoes de acao (Detalhes e Excluir)
                b1, b2 = st.columns([3, 1])
                with b1:
                    if st.button("➡️ Ver Detalhes", key=f"btn_prt_{port['id']}", use_container_width=True):
                        st.session_state.view_portfolio_id = port["id"]
                        st.switch_page("pages/_7_📂_Carteira_Detalhe.py")
                with b2:
                    if st.button("🗑️", key=f"btn_del_port_req_pd_{port['id']}", use_container_width=True, help="Excluir Carteira"):
                        st.session_state[f"confirmar_del_port_pd_{port['id']}"] = True
                        
                # Modal inline de confirmacao de exclusao
                if st.session_state.get(f"confirmar_del_port_pd_{port['id']}", False):
                    st.error(
                        "⚠️ **Atenção:** Destruir Carteira?\n\n"
                        "Todos os ativos, relatórios e depósitos dessa carteira serão dizimados."
                    )
                    c_conf1, c_conf2 = st.columns(2)
                    with c_conf1:
                        if st.button("❌ Cancelar", key=f"btn_cancel_del_po_pd_{port['id']}", use_container_width=True):
                            st.session_state[f"confirmar_del_port_pd_{port['id']}"] = False
                            st.rerun()
                    with c_conf2:
                        if st.button("✔️ Apagar Tudo", key=f"btn_confirm_del_po_pd_{port['id']}", type="primary", use_container_width=True):
                            from database.crud import deletar_portfolio
                            deletar_portfolio(port["id"])
                            st.session_state[f"confirmar_del_port_pd_{port['id']}"] = False
                            st.toast(f"Carteira '{port['nome']}' eliminada.", icon="💥")
                            st.rerun()

# --- CRIAR CARTEIRA ---
st.markdown("---")
with st.expander("➕ Criar Nova Carteira para esta Persona"):
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            port_nome = st.text_input("Nome da Carteira", placeholder="Ex: Mix Ações")
            tipo_ativo = st.selectbox("Tipo de Ativo", ["acoes", "fiis", "misto"],
                                       format_func=lambda x: {"acoes":"📈 Ações","fiis":"🏢 FIIs","misto":"🔀 Misto"}[x])
            montante = st.number_input(
                "💰 Aporte Inicial (R$)",
                min_value=0.0, max_value=10_000_000.0, value=1000.0, step=100.0,
                help="Dinheiro inicial em reais que você está destinando para iniciar os investimentos desta carteira."
            )
        with col2:
            prazo = st.selectbox("Objetivo Prazo", ["curto", "medio", "longo"],
                                  format_func=lambda x: {"curto":"⚡ Curto","medio":"📅 Médio","longo":"🏔️ Longo"}[x])
            meta_dy = st.number_input("Meta DY (%)", min_value=0.0, value=6.0, step=0.5)
        
        # Importar as constantes de setores
        from utils.helpers import SETORES_ACOES, SETORES_FIIS
        
        st.markdown("**Setores preferidos** *(opcional)*")
        setores_selecionados = []
        
        if tipo_ativo in ("acoes", "misto"):
            st.markdown("**Ações:**")
            cols_a = st.columns(3)
            with cols_a[0]:
                todos_a = st.checkbox("Selecionar Todos (Ações)", value=True, key="todos_a_pd", help="Se marcar esta opção, todos os setores serão incluídos de forma automática.")
            sel_a_list = []
            for i, (chave, label) in enumerate(SETORES_ACOES):
                with cols_a[(i + 1) % 3]:
                    if st.checkbox(label, value=todos_a, disabled=todos_a, key=f"setor_a_pd_{chave}"):
                        sel_a_list.append(chave)
            if todos_a or not sel_a_list:
                setores_selecionados.extend([k for k, _ in SETORES_ACOES])
            else:
                setores_selecionados.extend(sel_a_list)

        if tipo_ativo in ("fiis", "misto"):
            st.markdown("**FIIs:**")
            cols_f = st.columns(3)
            with cols_f[0]:
                todos_f = st.checkbox("Selecionar Todos (FIIs)", value=True, key="todos_f_pd", help="Se marcar esta opção, todos os setores serão incluídos de forma automática.")
            sel_f_list = []
            for i, (chave, label) in enumerate(SETORES_FIIS):
                with cols_f[(i + 1) % 3]:
                    if st.checkbox(label, value=todos_f, disabled=todos_f, key=f"setor_f_pd_{chave}"):
                        sel_f_list.append(chave)
            if todos_f or not sel_f_list:
                setores_selecionados.extend([k for k, _ in SETORES_FIIS])
            else:
                setores_selecionados.extend(sel_f_list)
                
        col_ap1, col_ap2 = st.columns(2)
        with col_ap1:
            aporte = st.number_input("Aporte periódico (R$)", min_value=0.0, value=100.0, step=50.0)
        with col_ap2:
            freq_aporte = st.selectbox("Frequência aporte", ["mensal", "quinzenal", "semanal"])
        
        if st.button("✅ Criar Carteira", key="btn_criar_carteira_px", type="primary", use_container_width=True):
            if not port_nome or not port_nome.strip():
                st.error("Nome obrigatório (não pode ser vazio ou apenas espaços)!")
            else:
                setores_str = ",".join(setores_selecionados)
                result = criar_portfolio(
                    persona_id=persona_id, nome=port_nome,
                    objetivo_prazo=prazo, meta_dividendos=meta_dy,
                    tipo_ativo=tipo_ativo, setores_preferidos=setores_str,
                    montante_disponivel=0,
                    aporte_periodico=aporte, frequencia_aporte=freq_aporte
                )
                if montante > 0:
                    from database.crud import registrar_transacao
                    registrar_transacao(
                        portfolio_id=result["id"],
                        tipo="aporte",
                        valor=montante,
                        descricao="Aporte inicial ao criar carteira"
                    )
                st.toast(f"Carteira '{port_nome}' criada! 🎉")
                st.session_state.view_portfolio_id = result["id"]
                st.switch_page("pages/_7_📂_Carteira_Detalhe.py")
