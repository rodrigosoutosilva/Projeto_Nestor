"""
💼 Carteiras - Gestão de Portfolios e Ativos
==============================================

Melhorias v2:
- Confirmação de exclusão (carteira e ativos)
- Edição de carteira (nome, montante, setores)
- Compra/venda manual com impacto no caixa
- Export CSV dos ativos
- Navegação "Gerar Recomendações →"
- Toasts para feedback
- "Data da Posição" (renomeado de "Data da Compra")
"""

import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.crud import (
    listar_personas_usuario, listar_portfolios_persona,
    criar_portfolio, deletar_portfolio, atualizar_portfolio,
    listar_ativos_portfolio, adicionar_ativo, deletar_ativo, atualizar_ativo,
    buscar_persona_por_id, registrar_transacao, resumo_transacoes_portfolio
)
from utils.helpers import (
    parsear_csv_ativos, formatar_moeda, formatar_moeda_md, formatar_data_br,
    calcular_meta_dividendos_auto, injetar_css_global,
    SETORES_ACOES, SETORES_FIIS
)
from services.market_data import buscar_preco_atual
from datetime import date

# Mapeamento de frequência para ordenação (menor valor = mais frequente)
FREQ_ORDEM = {"diario": 1, "semanal": 2, "mensal": 3}
FREQ_LABELS = {
    "diario": "📅 Diário",
    "semanal": "📆 Semanal",
    "mensal": "🗓️ Mensal"
}

def frequencias_permitidas(freq_persona: str) -> list:
    """
    Retorna as frequências de manuseio permitidas para a carteira.
    A carteira pode ter frequência menor ou igual à da persona.
    (Menor frequência = valor maior no FREQ_ORDEM)
    """
    nivel_persona = FREQ_ORDEM.get(freq_persona, 2)
    return [f for f, n in FREQ_ORDEM.items() if n >= nivel_persona]

st.set_page_config(page_title="💼 Carteiras", page_icon="💼", layout="wide")
injetar_css_global()

# Verificar login
if "user" not in st.session_state or st.session_state.user is None:
    st.warning("⚠️ Faça login na página principal primeiro.")
    st.stop()

user = st.session_state.user

st.markdown("### 💼 Gestão de Carteiras e Ativos")
st.markdown("*Gerencie seus portfolios, registre operações e acompanhe seu caixa*")
st.markdown("---")

# Estado para confirmações
if "confirmar_excluir_port" not in st.session_state:
    st.session_state.confirmar_excluir_port = None
if "confirmar_excluir_ativo" not in st.session_state:
    st.session_state.confirmar_excluir_ativo = None

# Buscar personas
personas = listar_personas_usuario(user["id"])

if not personas:
    st.warning("Crie uma **Persona** antes de criar uma carteira. Vá para 🧑 Personas.")
    st.stop()

# ---------------------------------------------------------------------------
# Selecionar Persona
# ---------------------------------------------------------------------------
persona_nomes = [f"{p['nome']} (Risco: {p['tolerancia_risco']}/10)" for p in personas]
persona_idx = st.selectbox("Selecione a Persona:", range(len(personas)),
                           format_func=lambda i: persona_nomes[i])
persona_selecionada = personas[persona_idx]

st.markdown("---")

# ---------------------------------------------------------------------------
# Criar Nova Carteira
# ---------------------------------------------------------------------------
# Estado para controle de criação em andamento
if "criando_carteira" not in st.session_state:
    st.session_state.criando_carteira = False

_criando = st.session_state.criando_carteira

with st.expander("➕ Criar Nova Carteira", expanded=False):
    with st.container():
        col1, col2 = st.columns(2)

        with col1:
            nome_cart = st.text_input(
                "Nome da Carteira",
                placeholder="Ex: Ações Blue Chip, FIIs Renda, Long & Short...",
                disabled=_criando,
                key="nome_cart_input"
            )
            objetivo = st.selectbox(
                "Objetivo de Prazo",
                options=["curto", "medio", "longo"],
                format_func=lambda x: {
                    "curto": "🏃 Curto Prazo (< 1 ano)",
                    "medio": "🚶 Médio Prazo (1-5 anos)",
                    "longo": "🧘 Longo Prazo (> 5 anos)"
                }[x],
                index=2,
                disabled=_criando
            )

        with col2:
            tipo = st.selectbox(
                "Tipo de Ativo",
                options=["acoes", "fiis", "misto"],
                format_func=lambda x: {
                    "acoes": "📈 Ações",
                    "fiis": "🏢 FIIs",
                    "misto": "🔀 Misto (Ações + FIIs)"
                }[x],
                index=2,
                disabled=_criando
            )
            montante = st.number_input(
                "💰 Aporte Inicial (R$)",
                min_value=0.0, max_value=10_000_000.0, value=1000.0, step=100.0,
                help="Dinheiro inicial em reais que você está destinando para iniciar os investimentos desta carteira. "
                     "Este valor será seu de Caixa Livre na plataforma.",
                disabled=_criando
            )

        # --- Aportes periódicos ---
        st.markdown("**💸 Aportes Periódicos** *(opcional — configure aportes recorrentes)*")
        col_ap1, col_ap2 = st.columns(2)
        with col_ap1:
            aporte_valor = st.number_input(
                "Valor do aporte periódico (R$)",
                min_value=0.0, max_value=1_000_000.0, value=0.0, step=50.0,
                help="Valor em reais que você pretende aportar recorrentemente.",
                disabled=_criando
            )
        with col_ap2:
            freq_aporte_opcoes = ["", "semanal", "quinzenal", "mensal"]
            freq_aporte_labels = {
                "": "— Sem aporte periódico —",
                "semanal": "📆 Semanal",
                "quinzenal": "📆 Quinzenal",
                "mensal": "🗓️ Mensal"
            }
            freq_aporte = st.selectbox(
                "Frequência do aporte",
                options=freq_aporte_opcoes,
                format_func=lambda x: freq_aporte_labels[x],
                disabled=_criando
            )

        # --- Frequência de manuseio ---
        st.markdown("**⏱️ Frequência de manuseio** *(com que frequência você revisa esta carteira)*")
        freqs_permitidas = frequencias_permitidas(persona_selecionada["frequencia_acao"])
        freq_manuseio_opcoes = [""] + freqs_permitidas
        freq_manuseio_labels = {
            "": f"🔄 Herdar da persona ({FREQ_LABELS.get(persona_selecionada['frequencia_acao'], persona_selecionada['frequencia_acao'])})",
            **FREQ_LABELS
        }
        freq_manuseio = st.selectbox(
            "Frequência de revisão da carteira",
            options=freq_manuseio_opcoes,
            format_func=lambda x: freq_manuseio_labels.get(x, x),
            help=f"Deve ser igual ou menos frequente que a da persona ({persona_selecionada['frequencia_acao']}). "
                 "Ex: se a persona é diária, a carteira pode ser diária, semanal ou mensal.",
            disabled=_criando
        )

        # Setores preferidos
        st.markdown("**🏭 Setores de preferência** *(opcional — ajuda a IA a sugerir ativos)*")

        setores_selecionados = []

        if tipo in ("acoes", "misto"):
            st.markdown("**Ações (Selecione os setores desejados):**")
            cols_a = st.columns(3)
            with cols_a[0]:
                todos_a = st.checkbox("Selecionar Todos (Ações)", value=True, key="todos_a", help="Se marcar esta opção, todos os setores serão incluídos de forma automática.", disabled=_criando)
            
            sel_a_list = []
            for i, (chave, label) in enumerate(SETORES_ACOES):
                with cols_a[(i + 1) % 3]:
                    if st.checkbox(label, value=todos_a, disabled=(todos_a or _criando), key=f"setor_a_{chave}"):
                        sel_a_list.append(chave)
            
            if todos_a or not sel_a_list:
                setores_selecionados.extend([k for k, _ in SETORES_ACOES])
            else:
                setores_selecionados.extend(sel_a_list)

        if tipo in ("fiis", "misto"):
            st.markdown("**FIIs (Selecione os tipos desejados):**")
            cols_f = st.columns(3)
            with cols_f[0]:
                todos_f = st.checkbox("Selecionar Todos (FIIs)", value=True, key="todos_f", help="Se marcar esta opção, todos os setores serão incluídos de forma automática.", disabled=_criando)
            
            sel_f_list = []
            for i, (chave, label) in enumerate(SETORES_FIIS):
                with cols_f[(i + 1) % 3]:
                    if st.checkbox(label, value=todos_f, disabled=(todos_f or _criando), key=f"setor_f_{chave}"):
                        sel_f_list.append(chave)
            
            if todos_f or not sel_f_list:
                setores_selecionados.extend([k for k, _ in SETORES_FIIS])
            else:
                setores_selecionados.extend(sel_f_list)

        # Meta DY automática
        meta_dy_auto = calcular_meta_dividendos_auto(
            tolerancia_risco=persona_selecionada["tolerancia_risco"],
            estilo=persona_selecionada["estilo"],
            objetivo_prazo=objetivo
        )
        st.info(
            f"📊 **Meta de dividendos calculada automaticamente: {meta_dy_auto}% ao ano** "
            f"— baseada no seu perfil ({persona_selecionada['estilo'].capitalize()}, "
            f"risco {persona_selecionada['tolerancia_risco']}/10, prazo {objetivo})"
        )

        submitted = st.button("✅ Criar Carteira", key="btn_criar_carteira", type="primary", use_container_width=True, disabled=_criando)
        if submitted:
            if not nome_cart or not nome_cart.strip():
                st.error("O nome da carteira é obrigatório (não pode ser vazio ou apenas espaços)!")
            elif aporte_valor > 0 and not freq_aporte:
                st.error("Se definiu um valor de aporte, selecione a frequência!")
            else:
                # Verificar nome duplicado
                portfolios_existentes = listar_portfolios_persona(persona_selecionada["id"])
                nomes_existentes = [p["nome"].strip().lower() for p in portfolios_existentes]
                if nome_cart.strip().lower() in nomes_existentes:
                    st.error(f"⚠️ Já existe uma carteira com o nome **{nome_cart}** nesta persona! Escolha outro nome.")
                else:
                    # Bloquear campos
                    st.session_state.criando_carteira = True
                    with st.spinner("⏳ Criando carteira... Aguarde."):
                        setores_str = ",".join(setores_selecionados)
                        result = criar_portfolio(
                            persona_id=persona_selecionada["id"],
                            nome=nome_cart,
                            objetivo_prazo=objetivo,
                            meta_dividendos=meta_dy_auto,
                            tipo_ativo=tipo,
                            setores_preferidos=setores_str,
                            montante_disponivel=0.0,
                            aporte_periodico=aporte_valor,
                            frequencia_aporte=freq_aporte,
                            frequencia_manuseio=freq_manuseio
                        )
                        # Registrar aporte inicial se montante > 0
                        if montante > 0:
                            registrar_transacao(
                                portfolio_id=result["id"],
                                tipo="aporte",
                                valor=montante,
                                descricao="Aporte inicial ao criar carteira"
                            )
                    st.session_state.criando_carteira = False
                    st.toast(f"Carteira {nome_cart} criada com sucesso! 🎉", icon="✅")
                    # Redirecionar para a página da carteira criada
                    st.session_state.view_portfolio_id = result["id"]
                    st.switch_page("pages/_7_📂_Carteira_Detalhe.py")

st.markdown("---")

# ---------------------------------------------------------------------------
# Listar Carteiras da Persona
# ---------------------------------------------------------------------------
st.markdown(f"### 💼 Carteiras de '{persona_selecionada['nome']}'")

portfolios = listar_portfolios_persona(persona_selecionada["id"])

if not portfolios:
    st.info("Nenhuma carteira nesta persona. Crie uma acima.")
else:
    # Toggle Cards / Lista
    modo_exibicao = st.radio(
        "Modo de Exibição:",
        ["📇 Cards", "📋 Lista Expandível"],
        horizontal=True,
        label_visibility="collapsed"
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if "Cards" in modo_exibicao:
        # Modo Cards (2 colunas para dar mais espaço)
        cols = st.columns(2)
        for i, port in enumerate(portfolios):
            with cols[i % 2]:
                tipo_emoji = {"acoes": "📈", "fiis": "🏢", "misto": "🔀"}.get(port["tipo_ativo"], "📊")
                with st.container(border=True):
                    st.markdown(f"#### {tipo_emoji} {port['nome']}")
                    st.caption(f"Persona: **{persona_selecionada['nome']}** | Prazo: {port['objetivo_prazo'].capitalize()}")
                    
                    # Calcular métricas financeiras
                    caixa = port.get("montante_disponivel", 0)
                    ativos_port = listar_ativos_portfolio(port["id"])
                    resumo_port = resumo_transacoes_portfolio(port["id"])
                    
                    # Patrimônio = soma de ativos a preço de mercado
                    patrimonio = 0
                    for a in ativos_port:
                        dados_preco = buscar_preco_atual(a["ticker"])
                        if dados_preco and isinstance(dados_preco, dict):
                            patrimonio += a["quantidade"] * dados_preco.get("preco_atual", a["preco_medio"])
                        else:
                            patrimonio += a["quantidade"] * a["preco_medio"]
                    
                    valor_total = caixa + patrimonio
                    total_aportado = resumo_port["total_aportes"] - resumo_port["total_retiradas"]
                    lucro_acum = valor_total - total_aportado if total_aportado > 0 else 0
                    lucro_pct = (lucro_acum / total_aportado * 100) if total_aportado > 0 else 0
                    
                    # Exibição compacta
                    st.metric("💎 Valor Total", formatar_moeda(valor_total))
                    mc1, mc2 = st.columns(2)
                    mc1.markdown(f"🏦 **Caixa:** {formatar_moeda_md(caixa)}", unsafe_allow_html=True)
                    mc2.markdown(f"📊 **Patrimônio:** {formatar_moeda_md(patrimonio)}", unsafe_allow_html=True)
                    
                    mc3, mc4 = st.columns(2)
                    cor_lucro = "green" if lucro_acum >= 0 else "red"
                    mc3.markdown(f"📈 **Lucro:** <span style='color:{cor_lucro}'>{formatar_moeda_md(lucro_acum)}</span>", unsafe_allow_html=True)
                    mc4.markdown(f"📉 **Rend.:** <span style='color:{cor_lucro}'>{lucro_pct:+.1f}%</span>", unsafe_allow_html=True)
                    
                    if port.get('aporte_periodico', 0) > 0:
                        freq_label = {"semanal": "sem", "quinzenal": "quinz", "mensal": "mês"}.get(port.get('frequencia_aporte', ''), '')
                        st.caption(f"💸 Aporte: {formatar_moeda(port['aporte_periodico'])}/{freq_label} | 📈 {len(ativos_port)} ativo(s)".replace("$", r"\$"))
                    
                    st.divider()
                    
                    # Botoes de acao (Detalhes e Excluir)
                    b1, b2 = st.columns([3, 1])
                    with b1:
                        if st.button("➡️ Ver Detalhes", key=f"btn_card_{port['id']}", use_container_width=True):
                            st.session_state.view_portfolio_id = port["id"]
                            st.switch_page("pages/_7_📂_Carteira_Detalhe.py")
                    with b2:
                        if st.button("🗑️", key=f"btn_del_port_req_{port['id']}", use_container_width=True, help="Excluir Carteira"):
                            st.session_state[f"confirmar_del_port_{port['id']}"] = True
                            
                    # Modal inline de confirmacao de exclusao
                    if st.session_state.get(f"confirmar_del_port_{port['id']}", False):
                        st.error(
                            "⚠️ **Atenção:** Destruir Carteira?\n\n"
                            "Todos os ativos, relatórios e depósitos dessa carteira serão dizimados."
                        )
                        c_conf1, c_conf2 = st.columns(2)
                        with c_conf1:
                            if st.button("❌ Cancelar", key=f"btn_cancel_del_po_{port['id']}", use_container_width=True):
                                st.session_state[f"confirmar_del_port_{port['id']}"] = False
                                st.rerun()
                        with c_conf2:
                            if st.button("✔️ Apagar Tudo", key=f"btn_confirm_del_po_{port['id']}", type="primary", use_container_width=True):
                                from database.crud import deletar_portfolio
                                deletar_portfolio(port["id"])
                                st.session_state[f"confirmar_del_port_{port['id']}"] = False
                                st.toast(f"Carteira '{port['nome']}' eliminada.", icon="💥")
                                st.rerun()
    else:
        # Modo Lista expandível
        for port in portfolios:
            tipo_emoji = {"acoes": "📈", "fiis": "🏢", "misto": "🔀"}.get(port["tipo_ativo"], "📊")
            montante_txt = f" | 💰 {formatar_moeda(port.get('montante_disponivel', 0))}"
            
            with st.expander(f"{tipo_emoji} **{port['nome']}** — Tipo: {port['tipo_ativo'].capitalize()}{montante_txt}"):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**Prazo:** {port['objetivo_prazo'].capitalize()} | **Meta DY:** {port['meta_dividendos']}%")
                    if port.get("setores_preferidos"):
                        setores_list = port["setores_preferidos"].split(",")
                        st.markdown(f"🏭 **Setores:** {', '.join(s.capitalize() for s in setores_list)}")
                with c2:
                    # Botoes de acao (Detalhes e Excluir)
                    b1, b2 = st.columns([3, 1])
                    with b1:
                        if st.button("➡️ Ver Detalhes", key=f"btn_list_{port['id']}", use_container_width=True):
                            st.session_state.view_portfolio_id = port["id"]
                            st.switch_page("pages/_7_📂_Carteira_Detalhe.py")
                    with b2:
                        if st.button("🗑️", key=f"btn_del_port_list_{port['id']}", use_container_width=True, help="Excluir Carteira"):
                            st.session_state[f"confirmar_del_port_{port['id']}"] = True
                            
                # Modal inline de confirmacao de exclusao (acoplado fora da coluna c2 para renderizar legível no expander)
                if st.session_state.get(f"confirmar_del_port_{port['id']}", False):
                    st.error(
                        "⚠️ **Atenção:** Destruir Carteira?\n\n"
                        "Todos os ativos, relatórios e depósitos dessa carteira serão dizimados."
                    )
                    c_conf1, c_conf2 = st.columns(2)
                    with c_conf1:
                        if st.button("❌ Cancelar", key=f"btn_cancel_del_po_{port['id']}", use_container_width=True):
                            st.session_state[f"confirmar_del_port_{port['id']}"] = False
                            st.rerun()
                    with c_conf2:
                        if st.button("✔️ Apagar Tudo", key=f"btn_confirm_del_po_{port['id']}", type="primary", use_container_width=True):
                            from database.crud import deletar_portfolio
                            deletar_portfolio(port["id"])
                            st.session_state[f"confirmar_del_port_{port['id']}"] = False
                            st.toast(f"Carteira '{port['nome']}' eliminada.", icon="💥")
                            st.rerun()
