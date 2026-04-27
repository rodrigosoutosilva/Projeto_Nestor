"""
Personas - Gestão de Perfis de Investimento
=================================================

Cada persona representa uma estratégia de investimento diferente.
Exibição em cards com resumo e link para página de detalhe.
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.crud import (
    listar_personas_usuario, criar_persona,
    listar_portfolios_persona, listar_ativos_portfolio,
    resumo_transacoes_portfolio
)
from services.market_data import buscar_preco_atual
from utils.helpers import formatar_moeda, formatar_moeda_md, injetar_css_global

st.set_page_config(page_title="Personas", page_icon="🧑‍🔬", layout="wide")
injetar_css_global()

# Verificar login
if "user" not in st.session_state or st.session_state.user is None:
    st.warning("Faça login na página principal primeiro.")
    st.stop()

user = st.session_state.user

st.markdown("### Gestão de Personas")
st.markdown("*Configure perfis de investimento com diferentes estratégias*")
st.markdown("---")

# ---------------------------------------------------------------------------
# Criar Nova Persona
# ---------------------------------------------------------------------------
with st.expander("Criar Nova Persona", expanded=False):
    with st.form("form_nova_persona"):
        col1, col2 = st.columns(2)

        with col1:
            nome = st.text_input(
                "Nome da Persona",
                placeholder="Ex: Aposentadoria, Day Trade, Dividendos..."
            )
            frequencia = st.selectbox(
                "Frequência de Revisão",
                options=["diario", "semanal", "mensal"],
                format_func=lambda x: {
                    "diario": "Diário (day trader)",
                    "semanal": "Semanal (swing trader)",
                    "mensal": "Mensal (buy & hold)"
                }[x],
                index=1
            )

        with col2:
            tolerancia = st.slider(
                "Tolerância a Risco",
                min_value=0, max_value=10, value=5,
                help="0 = Ultra Conservador | 10 = Ultra Arrojado"
            )
            estilo = st.selectbox(
                "Estilo de Investimento",
                options=["dividendos", "crescimento", "equilibrado"],
                format_func=lambda x: {
                    "dividendos": "Dividendos (renda passiva)",
                    "crescimento": "Crescimento (valorização)",
                    "equilibrado": "Equilibrado (mix de renda + valorização)"
                }[x]
            )

        # Indicador visual de perfil
        if tolerancia <= 3:
            perfil_txt = "**Conservador** — Prefere segurança e renda fixa"
        elif tolerancia <= 6:
            perfil_txt = "**Moderado** — Equilibra risco e retorno"
        else:
            perfil_txt = "**Arrojado** — Aceita volatilidade por maiores retornos"

        st.markdown(f"Perfil detectado: {perfil_txt}")

        submitted = st.form_submit_button("Criar Persona", use_container_width=True, type="primary")
        if submitted:
            if not nome:
                st.error("O nome da persona é obrigatório!")
            else:
                result = criar_persona(
                    user_id=user["id"],
                    nome=nome,
                    frequencia=frequencia,
                    tolerancia_risco=tolerancia,
                    estilo=estilo
                )
                st.session_state.view_persona_id = result["id"]
                st.toast(f"Persona **{nome}** criada com sucesso!")
                st.switch_page("pages/_9_Persona_Detalhe.py")

st.markdown("---")

# ---------------------------------------------------------------------------
# Listar Personas em Cards
# ---------------------------------------------------------------------------
st.markdown("### Suas Personas")

personas = listar_personas_usuario(user["id"])

if not personas:
    st.info(
        "Nenhuma persona cadastrada ainda. "
        "Crie uma acima para começar."
    )
else:
    cols = st.columns(2)
    for i, persona in enumerate(personas):
        with cols[i % 2]:
            # Cores por tolerância
            if persona["tolerancia_risco"] <= 3:
                cor, perfil = "🛡️", "Conservador"
            elif persona["tolerancia_risco"] <= 6:
                cor, perfil = "⚖️", "Moderado"
            else:
                cor, perfil = "🚀", "Arrojado"

            freq_label = {
                "diario": "Diário", "semanal": "Semanal", "mensal": "Mensal"
            }.get(persona.get("frequencia_acao", ""), "")

            estilo_label = {
                "dividendos": "Dividendos", "crescimento": "Crescimento", "equilibrado": "Equilibrado"
            }.get(persona.get("estilo", ""), "")

            with st.container(border=True):
                st.markdown(f"#### {cor} {persona['nome']}")
                st.caption(f"Perfil: **{perfil}** | Risco: {persona['tolerancia_risco']}/10 | {estilo_label} | {freq_label}")

                # Métricas consolidadas
                portfolios = listar_portfolios_persona(persona["id"])
                caixa_total = 0
                patrimonio_total = 0
                total_aportado = 0
                total_ativos = 0

                for port in portfolios:
                    caixa_total += port.get("montante_disponivel", 0)
                    ativos_port = listar_ativos_portfolio(port["id"])
                    total_ativos += len(ativos_port)
                    resumo = resumo_transacoes_portfolio(port["id"])
                    total_aportado += (resumo["total_aportes"] - resumo["total_retiradas"])
                    for a in ativos_port:
                        dados_p = buscar_preco_atual(a["ticker"])
                        if dados_p and isinstance(dados_p, dict):
                            patrimonio_total += a["quantidade"] * dados_p.get("preco_atual", a["preco_medio"])
                        else:
                            patrimonio_total += a["quantidade"] * a["preco_medio"]

                valor_total = caixa_total + patrimonio_total
                lucro = valor_total - total_aportado if total_aportado > 0 else 0

                st.metric("Valor Total", formatar_moeda(valor_total))
                mc1, mc2, mc3 = st.columns(3)
                mc1.markdown(f"**{len(portfolios)}** carteira(s)")
                mc2.markdown(f"**{total_ativos}** ativo(s)")
                cor_lucro = "green" if lucro >= 0 else "red"
                mc3.markdown(f"<span style='color:{cor_lucro}'>{formatar_moeda_md(lucro)}</span>", unsafe_allow_html=True)

                st.divider()
                
                b1, b2 = st.columns([3, 1])
                with b1:
                    if st.button("Ver Detalhes", key=f"btn_persona_{persona['id']}", use_container_width=True, type="tertiary"):
                        st.session_state.view_persona_id = persona["id"]
                        st.switch_page("pages/_9_Persona_Detalhe.py")
                with b2:
                    if st.button("Excluir", key=f"btn_del_persona_req_{persona['id']}", use_container_width=True, help="Excluir Persona", type="tertiary"):
                        st.session_state[f"confirmar_del_persona_{persona['id']}"] = True
                        
                # Modal inline de confirmacao de exclusao
                if st.session_state.get(f"confirmar_del_persona_{persona['id']}", False):
                    st.error(
                        "**Atenção:** Você está prestes a apagar esta Persona.\n\n"
                        "Ao confirmar, **todas as carteiras, ativos, movimentações "
                        "e históricos** atrelados a ela serão dizimados do sistema como se nunca tivessem existido. "
                        "Esta ação não tem volta."
                    )
                    c_conf1, c_conf2 = st.columns(2)
                    with c_conf1:
                        if st.button("Cancelar", key=f"btn_cancel_del_p_{persona['id']}", use_container_width=True, type="tertiary"):
                            st.session_state[f"confirmar_del_persona_{persona['id']}"] = False
                            st.rerun()
                    with c_conf2:
                        if st.button("Confirmar Exclusão", key=f"btn_confirm_del_p_{persona['id']}", type="primary", use_container_width=True):
                            from database.crud import deletar_persona
                            deletar_persona(persona["id"])
                            st.session_state[f"confirmar_del_persona_{persona['id']}"] = False
                            st.toast(f"Persona '{persona['nome']}' eliminada das cinzas.")
                            st.rerun()
