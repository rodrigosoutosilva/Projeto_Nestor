"""
📂 Persona Detalhe - Visão detalhada da Persona e suas Carteiras
================================================================

Página oculta do sidebar (prefixo _).
Mostra detalhes da persona selecionada e suas carteiras,
equivalente à página Carteiras mas já filtrado para a persona.
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.crud import (
    buscar_persona_por_id, atualizar_persona, deletar_persona,
    listar_portfolios_persona, listar_ativos_portfolio,
    resumo_transacoes_portfolio, criar_portfolio
)
from services.market_data import buscar_preco_atual
from utils.helpers import formatar_moeda, formatar_moeda_md

st.set_page_config(page_title="Persona Detalhe", page_icon="🧑", layout="wide")

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

st.button("⬅️ Voltar para Personas", on_click=lambda: st.switch_page("pages/2_🧑_Personas.py"))

# --- CABEÇALHO ---
if persona["tolerancia_risco"] <= 3:
    cor, perfil = "🟢", "Conservador"
elif persona["tolerancia_risco"] <= 6:
    cor, perfil = "🟡", "Moderado"
else:
    cor, perfil = "🔴", "Arrojado"

freq_label = {"diario": "📅 Diário", "semanal": "📆 Semanal", "mensal": "🗓️ Mensal"}.get(persona.get("frequencia_acao", ""), "")
estilo_label = {"dividendos": "💰 Dividendos", "crescimento": "🚀 Crescimento", "equilibrado": "⚖️ Equilibrado"}.get(persona.get("estilo", ""), "")

st.title(f"{cor} {persona['nome']}")
st.caption(f"Perfil: **{perfil}** | Risco: {persona['tolerancia_risco']}/10 | Estilo: {estilo_label} | Frequência: {freq_label}")

# --- MÉTRICAS CONSOLIDADAS DA PERSONA ---
portfolios = listar_portfolios_persona(persona_id)

caixa_total = 0
patrimonio_total = 0
total_aportado_global = 0
total_ativos = 0

for port in portfolios:
    caixa_total += port.get("montante_disponivel", 0)
    ativos_port = listar_ativos_portfolio(port["id"])
    total_ativos += len(ativos_port)
    resumo = resumo_transacoes_portfolio(port["id"])
    total_aportado_global += resumo["total_aportes"]
    
    for a in ativos_port:
        dados_p = buscar_preco_atual(a["ticker"])
        if dados_p and isinstance(dados_p, dict):
            patrimonio_total += a["quantidade"] * dados_p.get("preco_atual", a["preco_medio"])
        else:
            patrimonio_total += a["quantidade"] * a["preco_medio"]

valor_total = caixa_total + patrimonio_total
lucro_acum = valor_total - total_aportado_global if total_aportado_global > 0 else 0
lucro_pct = (lucro_acum / total_aportado_global * 100) if total_aportado_global > 0 else 0

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("💎 Valor Total", formatar_moeda(valor_total))
m2.metric("🏦 Caixa", formatar_moeda(caixa_total))
m3.metric("📊 Patrimônio", formatar_moeda(patrimonio_total))
m4.metric("📈 Lucro", formatar_moeda(lucro_acum))
m5.metric("📉 Rend.", f"{lucro_pct:+.1f}%")
m6.metric("📦 Ativos", total_ativos)

# --- EDIÇÃO DA PERSONA ---
with st.expander("✏️ Editar Persona"):
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
        st.toast("Persona atualizada! ✅")
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
                ta = resumo_port["total_aportes"]
                la = vt - ta if ta > 0 else 0
                lp = (la / ta * 100) if ta > 0 else 0
                
                st.metric("💎 Valor Total", formatar_moeda(vt))
                mc1, mc2 = st.columns(2)
                mc1.markdown(f"🏦 **Caixa:** {formatar_moeda_md(caixa)}", unsafe_allow_html=True)
                mc2.markdown(f"📊 **Patrimônio:** {formatar_moeda_md(patrimonio)}", unsafe_allow_html=True)
                
                mc3, mc4 = st.columns(2)
                cor_lucro = "green" if la >= 0 else "red"
                mc3.markdown(f"📈 **Lucro:** <span style='color:{cor_lucro}'>{formatar_moeda_md(la)}</span>", unsafe_allow_html=True)
                mc4.markdown(f"📉 **Rend.:** <span style='color:{cor_lucro}'>{lp:+.1f}%</span>", unsafe_allow_html=True)
                
                if port.get('aporte_periodico', 0) > 0:
                    fl = {"semanal":"sem","quinzenal":"quinz","mensal":"mês"}.get(port.get('frequencia_aporte',''),'')
                    st.caption(f"💸 Aporte: {formatar_moeda(port['aporte_periodico'])}/{fl} | 📈 {len(ativos_port)} ativo(s)")
                
                st.divider()
                if st.button("➡️ Ver Detalhes", key=f"btn_prt_{port['id']}", use_container_width=True):
                    st.session_state.view_portfolio_id = port["id"]
                    st.switch_page("pages/_7_📂_Carteira_Detalhe.py")

# --- CRIAR CARTEIRA ---
st.markdown("---")
with st.expander("➕ Criar Nova Carteira para esta Persona"):
    with st.form("form_new_port_persona"):
        col1, col2 = st.columns(2)
        with col1:
            port_nome = st.text_input("Nome da Carteira", placeholder="Ex: Mix Ações")
            tipo_ativo = st.selectbox("Tipo de Ativo", ["acoes", "fiis", "misto"],
                                       format_func=lambda x: {"acoes":"📈 Ações","fiis":"🏢 FIIs","misto":"🔀 Misto"}[x])
        with col2:
            prazo = st.selectbox("Objetivo Prazo", ["curto", "medio", "longo"],
                                  format_func=lambda x: {"curto":"⚡ Curto","medio":"📅 Médio","longo":"🏔️ Longo"}[x])
            meta_dy = st.number_input("Meta DY (%)", min_value=0.0, value=6.0, step=0.5)
        
        setores = st.text_input("Setores preferidos (separados por vírgula)", placeholder="Ex: bancos, energia")
        aporte = st.number_input("Aporte periódico (R$)", min_value=0.0, value=100.0, step=50.0)
        freq_aporte = st.selectbox("Frequência aporte", ["mensal", "quinzenal", "semanal"])
        
        if st.form_submit_button("✅ Criar Carteira", use_container_width=True):
            if not port_nome:
                st.error("Nome obrigatório!")
            else:
                criar_portfolio(
                    persona_id=persona_id, nome=port_nome,
                    objetivo_prazo=prazo, meta_dividendos=meta_dy,
                    tipo_ativo=tipo_ativo, setores_preferidos=setores,
                    montante_disponivel=0,
                    aporte_periodico=aporte, frequencia_aporte=freq_aporte
                )
                st.toast(f"Carteira '{port_nome}' criada! 🎉")
                st.rerun()
