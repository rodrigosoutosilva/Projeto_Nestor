"""
🧑 Personas - Gestão de Perfis de Investimento
=================================================

Cada persona representa uma estratégia de investimento diferente.
Ex: "Aposentadoria" (conservador) e "Agressivo" (arrojado).

Melhorias v2:
- Confirmação de exclusão
- Edição completa (nome, tolerância, frequência, estilo)
- Botão "Criar Carteira →" após criação
- Toasts para feedback
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.crud import (
    listar_personas_usuario, criar_persona,
    atualizar_persona, deletar_persona
)

st.set_page_config(page_title="🧑 Personas", page_icon="🧑", layout="wide")

# Verificar login
if "user" not in st.session_state or st.session_state.user is None:
    st.warning("⚠️ Faça login na página principal primeiro.")
    st.stop()

user = st.session_state.user

st.markdown("# 🧑 Gestão de Personas")
st.markdown("*Configure perfis de investimento com diferentes estratégias*")
st.markdown("---")

# ---------------------------------------------------------------------------
# Estado para confirmação de exclusão
# ---------------------------------------------------------------------------
if "confirmar_excluir_persona" not in st.session_state:
    st.session_state.confirmar_excluir_persona = None
if "persona_criada_id" not in st.session_state:
    st.session_state.persona_criada_id = None

# ---------------------------------------------------------------------------
# Criar Nova Persona
# ---------------------------------------------------------------------------
with st.expander("➕ Criar Nova Persona", expanded=False):
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
                    "diario": "📅 Diário (day trader)",
                    "semanal": "📆 Semanal (swing trader)",
                    "mensal": "🗓️ Mensal (buy & hold)"
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
                    "dividendos": "💰 Dividendos (renda passiva)",
                    "crescimento": "🚀 Crescimento (valorização)",
                    "equilibrado": "⚖️ Equilibrado (mix de renda + valorização)"
                }[x]
            )

        # Indicador visual de perfil
        if tolerancia <= 3:
            perfil_txt = "🟢 **Conservador** — Prefere segurança e renda fixa"
        elif tolerancia <= 6:
            perfil_txt = "🟡 **Moderado** — Equilibra risco e retorno"
        else:
            perfil_txt = "🔴 **Arrojado** — Aceita volatilidade por maiores retornos"

        st.markdown(f"Perfil detectado: {perfil_txt}")

        submitted = st.form_submit_button("✅ Criar Persona", use_container_width=True)
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
                st.session_state.persona_criada_id = result["id"]
                st.toast(f"Persona **{nome}** criada com sucesso! 🎉")
                st.rerun()

# Mostrar botão de navegação se acabou de criar
if st.session_state.persona_criada_id:
    st.success("✅ Persona criada! Quer criar uma carteira para ela?")
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("💼 Criar Carteira para esta Persona →", use_container_width=True):
            st.session_state.persona_criada_id = None
            st.switch_page("pages/3_💼_Carteiras.py")
    with col_nav2:
        if st.button("Continuar aqui", use_container_width=True):
            st.session_state.persona_criada_id = None
            st.rerun()

st.markdown("---")

# ---------------------------------------------------------------------------
# Listar Personas Existentes
# ---------------------------------------------------------------------------
st.markdown("### 📋 Suas Personas")

personas = listar_personas_usuario(user["id"])

if not personas:
    st.info(
        "Nenhuma persona cadastrada ainda. "
        "Crie uma acima ou use o 📥 Onboarding para começar."
    )
else:
    for persona in personas:
        # Cores por tolerância
        if persona["tolerancia_risco"] <= 3:
            cor = "🟢"
            perfil = "Conservador"
        elif persona["tolerancia_risco"] <= 6:
            cor = "🟡"
            perfil = "Moderado"
        else:
            cor = "🔴"
            perfil = "Arrojado"

        freq_label = {
            "diario": "📅 Diário",
            "semanal": "📆 Semanal",
            "mensal": "🗓️ Mensal"
        }.get(persona["frequencia_acao"], persona["frequencia_acao"])

        estilo_label = {
            "dividendos": "💰 Dividendos",
            "crescimento": "🚀 Crescimento",
            "equilibrado": "⚖️ Equilibrado"
        }.get(persona["estilo"], persona["estilo"])

        with st.expander(
            f"{cor} **{persona['nome']}** — {perfil} | "
            f"Risco: {persona['tolerancia_risco']}/10 | "
            f"Estilo: {persona['estilo'].capitalize()}"
        ):
            st.markdown(f"""
            | Campo | Valor |
            |-------|-------|
            | **Frequência** | {freq_label} |
            | **Tolerância a Risco** | {persona['tolerancia_risco']}/10 |
            | **Estilo** | {estilo_label} |
            """)

            # Formulário de edição completa
            st.markdown("#### ✏️ Editar")
            col1, col2 = st.columns(2)

            with col1:
                novo_nome = st.text_input(
                    "Nome:",
                    value=persona["nome"],
                    key=f"edit_nome_{persona['id']}"
                )
                nova_frequencia = st.selectbox(
                    "Frequência:",
                    options=["diario", "semanal", "mensal"],
                    index=["diario", "semanal", "mensal"].index(persona["frequencia_acao"]),
                    format_func=lambda x: {
                        "diario": "📅 Diário",
                        "semanal": "📆 Semanal",
                        "mensal": "🗓️ Mensal"
                    }[x],
                    key=f"edit_freq_{persona['id']}"
                )

            with col2:
                nova_tolerancia = st.slider(
                    "Tolerância:",
                    0, 10, persona["tolerancia_risco"],
                    key=f"edit_tol_{persona['id']}"
                )
                novo_estilo = st.selectbox(
                    "Estilo:",
                    options=["dividendos", "crescimento", "equilibrado"],
                    index=["dividendos", "crescimento", "equilibrado"].index(persona["estilo"]),
                    format_func=lambda x: {
                        "dividendos": "💰 Dividendos",
                        "crescimento": "🚀 Crescimento",
                        "equilibrado": "⚖️ Equilibrado"
                    }[x],
                    key=f"edit_estilo_{persona['id']}"
                )

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button(
                    "💾 Salvar Alterações",
                    key=f"save_{persona['id']}",
                    use_container_width=True
                ):
                    atualizar_persona(
                        persona["id"],
                        nome=novo_nome,
                        tolerancia_risco=nova_tolerancia,
                        frequencia_acao=nova_frequencia,
                        estilo=novo_estilo
                    )
                    st.toast("Persona atualizada! ✅")
                    st.rerun()

            with col_btn2:
                # Confirmação de exclusão em duas etapas
                if st.session_state.confirmar_excluir_persona == persona["id"]:
                    st.error(f"⚠️ Tem certeza? Isso excluirá a persona **{persona['nome']}** e todas as suas carteiras!")
                    col_conf1, col_conf2 = st.columns(2)
                    with col_conf1:
                        if st.button("✅ Sim, excluir", key=f"conf_del_{persona['id']}", use_container_width=True):
                            deletar_persona(persona["id"])
                            st.session_state.confirmar_excluir_persona = None
                            st.toast(f"Persona {persona['nome']} excluída.")
                            st.rerun()
                    with col_conf2:
                        if st.button("❌ Cancelar", key=f"cancel_del_{persona['id']}", use_container_width=True):
                            st.session_state.confirmar_excluir_persona = None
                            st.rerun()
                else:
                    if st.button(
                        "🗑️ Excluir Persona",
                        key=f"del_{persona['id']}",
                        use_container_width=True,
                        type="secondary"
                    ):
                        st.session_state.confirmar_excluir_persona = persona["id"]
                        st.rerun()
